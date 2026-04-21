"""Augie — overlay-driven live TFT advisor (v3 pipeline).

Full F9 pipeline:
    capture → state_builder → validate → CoachOrchestrator (8 agents)
    → CoachResult → bindings.on_coach_result → AuroraPanel

Hotkeys:
    F9   → capture + v3 8-agent pipeline
    F10  → start a new game session
    F11  → end the current game session (console prompt for placement)
    ESC  → quit

Threading:
    Main thread      — QApplication + AuroraPanel (all UI updates)
    Hotkey thread    — `keyboard` lib. F9 callback emits a Qt signal.
    Pipeline thread  — QThread per F9 press. Emits signals for each
                       stage; overlay updates via QueuedConnection.

v3 engine lives in engine/agents/. All imports from the engine package
are performed AFTER the engine path is inserted at sys.path[0].
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

# v3 orchestrator — 8-agent system
from engine.agents.orchestrator import CoachOrchestrator, AgentContext

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

# Singleton — agents have startup cost (YAML loading); don't recreate per F9.
_ORCHESTRATOR = CoachOrchestrator()


# ── Pipeline worker ────────────────────────────────────────────────────────────

class PipelineWorker(QThread):
    """Runs one F9 pipeline invocation on a background thread.

    Signal contract (consumed by Bindings slots via QueuedConnection):
        extractingStarted   → bindings.on_extracting()
        stateExtracted(dict) → bindings.on_state_extracted(state_dict)  [fast header update]
        coachResultReady(object) → bindings.on_coach_result(CoachResult)
        errorOccurred(str)  → bindings.on_error(msg)
    """

    extractingStarted  = pyqtSignal()
    stateExtracted     = pyqtSignal(dict)
    coachResultReady   = pyqtSignal(object)  # CoachResult instance
    errorOccurred      = pyqtSignal(str)

    def __init__(self, client: Anthropic) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        try:
            self.extractingStarted.emit()

            # ── 1. Capture + state extraction ─────────────────────────────────
            png     = capture_screen()
            game_id = session.current_game_id()
            state   = build_state(png, self.client, game_id=game_id, trigger="hotkey")

            if not state.sources.vision_ok:
                self.errorOccurred.emit(f"Vision failed: {state.sources.vision_error}")
                return

            # Fast header update — happens before the 8 agents run.
            self.stateExtracted.emit(state.to_dict())

            # ── 2. Parse to v2 schema ──────────────────────────────────────────
            try:
                v2_state = state.to_schemas()
            except ValueError as exc:
                self.errorOccurred.emit(f"State incomplete: {exc}")
                return

            # ── 3. State validation ────────────────────────────────────────────
            try:
                from validators import validate as validate_state
                validation = validate_state(v2_state)
                if not validation.ok:
                    import logging
                    failure_summary = "; ".join(
                        f"{f.check_name}={f.actual_value}" for f in validation.failures[:3]
                    )
                    logging.warning("State validation failed: %s", failure_summary)
                    self.errorOccurred.emit("state_validation_failed")
                    return
            except ImportError:
                pass

            # ── 4. v3 orchestrator — 8 agents in parallel ─────────────────────
            ctx    = _build_agent_context(v2_state)
            result = _ORCHESTRATOR.run_sync(ctx)
            self.coachResultReady.emit(result)

        except Exception as exc:
            logger.exception("F9 pipeline failed")
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")


# ── State conversion helper ────────────────────────────────────────────────────

def _build_agent_context(v2_state) -> AgentContext:
    """Convert engine.schemas.GameState → AgentContext for the orchestrator."""
    stage_str = str(v2_state.stage or "2-1")
    parts = stage_str.split("-")
    stage = (int(parts[0]), int(parts[1])) if len(parts) == 2 else (2, 1)

    board_slots = []
    for unit in (v2_state.board or []):
        champ = unit.champion or ""
        board_slots.append({
            "api_name": champ,
            "display_name": champ.split("_")[-1] if "_" in champ else champ,
            "cost": 1,
            "star": int(unit.star or 1),
            "items_held": list(unit.items or []),
            "bis_trios": [],
            "value_class": "B",
        })

    return AgentContext(
        hp=int(v2_state.hp or 100),
        gold=int(v2_state.gold or 0),
        level=int(v2_state.level or 4),
        stage=stage,
        streak=int(v2_state.streak or 0),
        interest_tier=min(5, int(v2_state.gold or 0) // 10),
        board_strength=0.5,
        board_slots=board_slots,
        bench_components=list(v2_state.item_components_on_bench or []),
        augments_picked=list(v2_state.augments or []),
        augment_tiers=[],
        target_comp_apis=[],
        active_items={},
    )


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
        w.extractingStarted.connect(
            self.bindings.on_extracting, Qt.ConnectionType.QueuedConnection)
        w.stateExtracted.connect(
            self.bindings.on_state_extracted, Qt.ConnectionType.QueuedConnection)
        w.coachResultReady.connect(
            self.bindings.on_coach_result, Qt.ConnectionType.QueuedConnection)
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

    logger.info("AUGIE v3 pipeline started (8-agent orchestrator)")
    logger.info(
        "Hotkeys: {} advise | {} start session | {} end session | {} quit",
        HOTKEY_ADVISE.upper(), HOTKEY_START.upper(),
        HOTKEY_END.upper(), HOTKEY_QUIT.upper(),
    )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
