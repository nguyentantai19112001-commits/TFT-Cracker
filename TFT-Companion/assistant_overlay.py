"""Augie — overlay-driven live TFT advisor (Phase B4).

Same pipeline as assistant.py but renders into a frameless always-on-top
PyQt6 panel instead of the console. You never tab out of the game.

    F9   → capture + extract + rules + scoring + streamed advisor
    F10  → start a new game session
    F11  → end the current game session (console prompt for placement)
    ESC  → quit

Threading:
    Main thread          — QApplication + OverlayPanel (all UI updates)
    Hotkey thread        — `keyboard` lib. F9 callback emits a Qt signal.
    Pipeline thread      — QThread per F9 press. Emits signals for each
                           stream event; overlay updates via QueuedConnection.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

import keyboard
from anthropic import Anthropic
from dotenv import load_dotenv
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication

import advisor
import rules
import scoring
import session
from overlay import OverlayPanel
from state_builder import build_state
from vision import capture_screen


HOTKEY_ADVISE = "f9"
HOTKEY_START = "f10"
HOTKEY_END = "f11"
HOTKEY_QUIT = "esc"


# ---------- pipeline worker ----------

class PipelineWorker(QThread):
    """Runs one F9 pipeline invocation on a background thread."""

    extractingStarted = pyqtSignal()
    stateExtracted = pyqtSignal(dict)
    verdictReady = pyqtSignal(str)
    reasoningReady = pyqtSignal(str)
    finalReady = pyqtSignal(dict, dict, float, float, object)  # rec, meta, wall_s, vision_cost, game_id
    errorOccurred = pyqtSignal(str)

    def __init__(self, client: Anthropic) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        try:
            self.extractingStarted.emit()
            t0 = time.time()
            png = capture_screen()
            game_id = session.current_game_id()

            state = build_state(png, self.client, game_id=game_id, trigger="hotkey")
            d = state.to_dict()
            if not state.sources.vision_ok:
                self.errorOccurred.emit(f"Vision failed: {state.sources.vision_error}")
                return
            self.stateExtracted.emit(d)

            fires = rules.evaluate(d)
            bs = scoring.compute_board_strength(d)

            recommendation = None
            meta = None
            for evt, payload in advisor.advise_stream(
                d, fires, bs, self.client, capture_id=state.capture_id
            ):
                if evt == "one_liner":
                    self.verdictReady.emit(payload)
                elif evt == "reasoning":
                    self.reasoningReady.emit(payload)
                elif evt == "final":
                    recommendation = payload.get("recommendation")
                    meta = payload.get("__meta__")
                    break

            if not meta or not meta.get("parse_ok"):
                err = meta.get("error") if meta else "no final event"
                self.errorOccurred.emit(f"Advisor failed: {err}")
                return

            wall_s = time.time() - t0
            vision_cost = d["sources"]["vision_cost_usd"] or 0
            self.finalReady.emit(
                recommendation or {}, meta, wall_s, vision_cost, game_id
            )
        except Exception as e:  # surface any crash into the overlay
            self.errorOccurred.emit(f"{type(e).__name__}: {e}")


# ---------- hotkey bridge ----------

class HotkeyBridge(QObject):
    """Emitted from the keyboard thread; consumed on the Qt main thread."""
    adviseRequested = pyqtSignal()
    startRequested = pyqtSignal()
    endRequested = pyqtSignal()


# ---------- controller ----------

class AppController(QObject):
    def __init__(self, client: Anthropic, overlay: OverlayPanel) -> None:
        super().__init__()
        self.client = client
        self.overlay = overlay
        self._worker: Optional[PipelineWorker] = None

    def on_advise(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # ignore duplicate F9 while pipeline is in-flight
        self.overlay.reset()

        w = PipelineWorker(self.client)
        # QueuedConnection: signals emitted from the QThread are delivered
        # on the Qt main thread where the overlay lives.
        w.extractingStarted.connect(self.overlay.set_extracting, Qt.ConnectionType.QueuedConnection)
        w.stateExtracted.connect(self.overlay.set_extracted, Qt.ConnectionType.QueuedConnection)
        w.verdictReady.connect(self.overlay.set_verdict, Qt.ConnectionType.QueuedConnection)
        w.reasoningReady.connect(self.overlay.set_reasoning, Qt.ConnectionType.QueuedConnection)
        w.finalReady.connect(self._on_final, Qt.ConnectionType.QueuedConnection)
        w.errorOccurred.connect(self.overlay.set_error, Qt.ConnectionType.QueuedConnection)
        w.finished.connect(w.deleteLater)
        self._worker = w
        w.start()

    def _on_final(self, rec, meta, wall_s, vision_cost, game_id) -> None:
        self.overlay.set_final(rec, meta, wall_s, vision_cost, game_id)

    def on_start(self) -> None:
        gid = session.start_game(queue_type="ranked")
        print(f">>> Game session started (game_id={gid})")

    def on_end(self) -> None:
        gid = session.current_game_id()
        if gid is None:
            print(">>> No active game session.")
            return
        try:
            raw = input("Final placement (1-8, blank to skip): ").strip()
            placement = int(raw) if raw else None
        except (ValueError, EOFError):
            placement = None
        session.end_game(final_placement=placement)
        print(f">>> Game session {gid} closed (placement={placement}).")


# ---------- main ----------

def main() -> int:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Copy .env.example to .env.")
        return 1

    client = Anthropic(api_key=api_key)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    overlay = OverlayPanel()
    overlay.show()

    controller = AppController(client, overlay)

    # Bridge keyboard-thread events to the Qt main thread via signals.
    bridge = HotkeyBridge()
    bridge.adviseRequested.connect(controller.on_advise, Qt.ConnectionType.QueuedConnection)
    bridge.startRequested.connect(controller.on_start, Qt.ConnectionType.QueuedConnection)
    bridge.endRequested.connect(controller.on_end, Qt.ConnectionType.QueuedConnection)

    keyboard.add_hotkey(HOTKEY_ADVISE, bridge.adviseRequested.emit)
    keyboard.add_hotkey(HOTKEY_START, bridge.startRequested.emit)
    keyboard.add_hotkey(HOTKEY_END, bridge.endRequested.emit)
    keyboard.add_hotkey(HOTKEY_QUIT, app.quit)

    print("=" * 72)
    print("  AUGIE  —  Phase B4 (overlay)")
    print("=" * 72)
    print(f"  {HOTKEY_ADVISE.upper()}   advise on current state")
    print(f"  {HOTKEY_START.upper()}  start a game session")
    print(f"  {HOTKEY_END.upper()}  end game session (prompts for placement in this console)")
    print(f"  {HOTKEY_QUIT.upper()}  quit")
    print("\nOverlay floats top-right. Drag by the title bar.\n")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
