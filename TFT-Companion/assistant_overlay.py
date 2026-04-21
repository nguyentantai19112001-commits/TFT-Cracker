"""Augie — overlay-driven live TFT advisor (v2 pipeline).

Full F9 pipeline:
    capture → state_builder → validate → rules → comp_planner
    → recommender → advisor → overlay

Hotkeys:
    F9   → capture + full v2 pipeline + streamed advisor verdict
    F10  → start a new game session
    F11  → end the current game session (console prompt for placement)
    ESC  → quit

Threading:
    Main thread      — QApplication + OverlayPanel (all UI updates)
    Hotkey thread    — `keyboard` lib. F9 callback emits a Qt signal.
    Pipeline thread  — QThread per F9 press. Emits signals for each
                       stream event; overlay updates via QueuedConnection.

v2 engine lives in engine/ (formerly augie-v2/). All imports from that
package are performed AFTER the engine path is inserted at sys.path[0]
so they shadow any legacy root-level files with the same name.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

# ── v2 engine path — must precede ALL other local imports ─────────────────────
# This ensures `import rules`, `import advisor`, etc. resolve to engine/,
# not the v1 root-level files that share the same module names.
_ENGINE_DIR = Path(__file__).resolve().parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
# ─────────────────────────────────────────────────────────────────────────────

import keyboard
from anthropic import Anthropic
from dotenv import load_dotenv
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QVBoxLayout

# v2 engine modules — imported from engine/ via sys.path priority above
import advisor          # engine/advisor.py  (v2 Haiku narrator)
import comp_planner     # engine/comp_planner.py
import econ             # engine/econ.py
import knowledge        # engine/knowledge/__init__.py
import recommender      # engine/recommender.py
import rules            # engine/rules.py  (v2 — 40 deterministic rules)
from pool import PoolTracker  # engine/pool.py

# v1 infrastructure — no v2 counterparts for these
import session
from logging_setup import logger, setup_logging
from state_builder import build_state
from vision import capture_screen, release_camera

# Aurora UI (v2)
_UI_ROOT = Path(__file__).resolve().parent
if str(_UI_ROOT) not in sys.path:
    sys.path.append(str(_UI_ROOT))
from ui.chrome.frameless_window import AugieFrameless
from ui.panel import AuroraPanel
from ui.bindings import Bindings


HOTKEY_ADVISE = "f9"
HOTKEY_START  = "f10"
HOTKEY_END    = "f11"
HOTKEY_QUIT   = "esc"


# ── Pipeline worker ────────────────────────────────────────────────────────────

class PipelineWorker(QThread):
    """Runs one F9 pipeline invocation on a background thread.

    Signal contract (consumed by OverlayPanel slots via QueuedConnection):
        extractingStarted  → overlay.set_extracting()
        stateExtracted(dict) → overlay.set_extracted(state_dict)
        compPlanReady(list)  → overlay.set_comp_plan(comps_dicts)
        verdictReady(str)    → overlay.set_verdict(one_liner)
        reasoningReady(str)  → bindings.on_reasoning(text)
        finalReady(dict, dict, float, float, object)
                             → overlay.set_final(rec, meta, wall_s, vcost, game_id)
        errorOccurred(str)   → overlay.set_error(msg)
    """

    extractingStarted = pyqtSignal()
    stateExtracted    = pyqtSignal(dict)
    compPlanReady     = pyqtSignal(list)   # list of CompCandidate.model_dump()
    verdictReady      = pyqtSignal(str)
    reasoningReady    = pyqtSignal(str)
    finalReady        = pyqtSignal(dict, dict, float, float, object)
    errorOccurred     = pyqtSignal(str)

    def __init__(self, client: Anthropic) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        try:
            self.extractingStarted.emit()
            t0 = time.time()

            # ── 1. Capture + legacy state extraction ──────────────────────────
            png       = capture_screen()
            game_id   = session.current_game_id()
            state     = build_state(png, self.client, game_id=game_id, trigger="hotkey")

            if not state.sources.vision_ok:
                self.errorOccurred.emit(f"Vision failed: {state.sources.vision_error}")
                return

            # Emit the raw dict so the overlay header updates immediately
            self.stateExtracted.emit(state.to_dict())

            # ── 2. Convert to v2 schemas ───────────────────────────────────────
            # to_schemas() raises ValueError if required fields (stage/gold/hp/level)
            # are None — this means Vision returned an incomplete parse.
            try:
                v2_state = state.to_schemas()
            except ValueError as exc:
                self.errorOccurred.emit(f"State incomplete: {exc}")
                return

            # ── 3. State validation (Task 2 — inserted after to_schemas) ──────
            # Imported here (lazy) so it works before Task 2 creates validators.py.
            try:
                from validators import validate as validate_state
                validation = validate_state(v2_state)
                if not validation.ok:
                    failure_summary = "; ".join(
                        f"{f.check_name}={f.actual_value}" for f in validation.failures[:3]
                    )
                    import logging
                    logging.warning("State validation failed: %s", failure_summary)
                    self.verdictReady.emit("⚠ verifying state — press F9 again in a moment")
                    self.errorOccurred.emit("state_validation_failed")
                    return
            except ImportError:
                pass  # validators.py not yet present (pre-Task-2)

            # ── 4. v2 pipeline: rules → comp_planner → recommender ────────────
            set_  = knowledge.load_set(v2_state.set_id)
            core  = knowledge.load_core()
            pool  = PoolTracker(set_)
            pool.observe_own_board(v2_state.board, v2_state.bench)
            archetypes = comp_planner.load_archetypes()

            fires   = rules.evaluate(v2_state, econ, pool, knowledge)
            comps   = comp_planner.top_k_comps(v2_state, pool, archetypes, set_, k=3)
            actions = recommender.top_k(v2_state, fires, comps, pool, set_, core, k=3)

            # Emit comp plan so the long-term comp panel updates
            self.compPlanReady.emit([c.model_dump() for c in comps])

            # ── 5. Advisor: streams verdict tokens then emits final ────────────
            recommendation: Optional[dict] = None
            meta: Optional[dict]           = None

            for evt, payload in advisor.advise_stream(
                state=v2_state,
                fires=fires,
                actions=actions,
                comps=comps,
                client=self.client,
                capture_id=state.capture_id,
                pool=pool,
            ):
                if evt == "one_liner":
                    self.verdictReady.emit(payload)
                elif evt == "reasoning":
                    self.reasoningReady.emit(payload)
                elif evt == "final":
                    verdict       = payload.get("verdict")
                    meta          = payload.get("__meta__") or {}
                    # Always prefer the parsed AdvisorVerdict; raw recommendation
                    # from the LLM path has chosen_candidate_index (not the
                    # resolved ActionCandidate object that the overlay needs).
                    recommendation = (
                        verdict.model_dump() if verdict
                        else payload.get("recommendation") or {}
                    )
                    break

            if not meta or not meta.get("parse_ok"):
                # Advisor produced no clean JSON — still show what we have
                err = (meta or {}).get("error") or "no final event"
                self.errorOccurred.emit(f"Advisor: {err}")
                return

            wall_s       = time.time() - t0
            vision_cost  = state.to_dict()["sources"].get("vision_cost_usd") or 0
            self.finalReady.emit(
                recommendation or {},
                meta,
                wall_s,
                vision_cost,
                game_id,
            )

        except Exception as exc:
            logger.exception("F9 pipeline failed")
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")


# ── Hotkey bridge ──────────────────────────────────────────────────────────────

class HotkeyBridge(QObject):
    """Thread-safe bridge from the keyboard thread to the Qt main thread."""
    adviseRequested = pyqtSignal()
    startRequested  = pyqtSignal()
    endRequested    = pyqtSignal()


# ── App controller ─────────────────────────────────────────────────────────────

class AppController(QObject):
    def __init__(self, client: Anthropic, panel: AuroraPanel, bindings: Bindings) -> None:
        super().__init__()
        self.client   = client
        self.panel    = panel
        self.bindings = bindings
        self._worker: Optional[PipelineWorker] = None

    def on_advise(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # drop duplicate F9 while pipeline is in-flight

        w = PipelineWorker(self.client)
        # All connections use QueuedConnection so signals emitted from the
        # QThread are delivered on the Qt main thread (where the panel lives).
        w.extractingStarted.connect(
            self.bindings.on_extracting, Qt.ConnectionType.QueuedConnection)
        w.stateExtracted.connect(
            self.bindings.on_state_extracted, Qt.ConnectionType.QueuedConnection)
        w.compPlanReady.connect(
            self.bindings.on_comp_plan, Qt.ConnectionType.QueuedConnection)
        w.reasoningReady.connect(
            self.bindings.on_reasoning, Qt.ConnectionType.QueuedConnection)
        w.verdictReady.connect(
            self.bindings.on_verdict_ready, Qt.ConnectionType.QueuedConnection)
        w.finalReady.connect(
            self.bindings.on_final, Qt.ConnectionType.QueuedConnection)
        w.errorOccurred.connect(
            self.bindings.on_error, Qt.ConnectionType.QueuedConnection)
        w.finished.connect(w.deleteLater)
        self._worker = w
        w.start()

    def on_start(self) -> None:
        gid = session.start_game(queue_type="ranked")
        logger.info("Game session started (game_id={})", gid)

    def on_end(self) -> None:
        gid = session.current_game_id()
        if gid is None:
            logger.warning("on_end called with no active game session")
            return
        try:
            raw       = input("Final placement (1-8, blank to skip): ").strip()
            placement = int(raw) if raw else None
        except (ValueError, EOFError):
            placement = None
        session.end_game(final_placement=placement)
        logger.info("Game session {} closed (placement={})", gid, placement)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    setup_logging()
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.critical("ANTHROPIC_API_KEY not set — copy .env.example to .env and restart")
        return 1

    client = Anthropic(api_key=api_key)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    # Release DXcam singleton when the app exits so the Desktop Duplication
    # handle is freed cleanly (avoids "camera not released" warnings on restart).
    app.aboutToQuit.connect(release_camera)

    window = AugieFrameless()
    panel  = AuroraPanel(window)

    # Embed panel in window
    _layout = QVBoxLayout(window)
    _layout.setContentsMargins(0, 0, 0, 0)
    _layout.addWidget(panel)

    # Wire chrome buttons
    panel.title_bar.minimize_clicked.connect(window.showMinimized)
    panel.title_bar.close_clicked.connect(app.quit)
    panel.title_bar.pin_toggled.connect(window.set_pinned)

    window.show()

    bindings   = Bindings(panel)
    controller = AppController(client, panel, bindings)

    bridge = HotkeyBridge()
    bridge.adviseRequested.connect(
        controller.on_advise, Qt.ConnectionType.QueuedConnection)
    bridge.startRequested.connect(
        controller.on_start, Qt.ConnectionType.QueuedConnection)
    bridge.endRequested.connect(
        controller.on_end, Qt.ConnectionType.QueuedConnection)

    keyboard.add_hotkey(HOTKEY_ADVISE, bridge.adviseRequested.emit)
    keyboard.add_hotkey(HOTKEY_START,  bridge.startRequested.emit)
    keyboard.add_hotkey(HOTKEY_END,    bridge.endRequested.emit)
    keyboard.add_hotkey(HOTKEY_QUIT,   app.quit)

    logger.info("AUGIE v2 pipeline started")
    logger.info(
        "Hotkeys: {} advise | {} start session | {} end session | {} quit",
        HOTKEY_ADVISE.upper(), HOTKEY_START.upper(),
        HOTKEY_END.upper(), HOTKEY_QUIT.upper(),
    )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
