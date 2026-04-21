"""Base class for the Augie overlay window.

Uses PyQt6-Frameless-Window (qframelesswindow) for cross-platform
frameless + drag behavior. Adds Win11 Mica when available.
"""
from __future__ import annotations
import sys
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget
from loguru import logger

try:
    from qframelesswindow import FramelessWindow
    FRAMELESS_AVAILABLE = True
except ImportError:
    FramelessWindow = QWidget    # fallback; basic window
    FRAMELESS_AVAILABLE = False

try:
    from winmica import EnableMica, BackdropType, is_mica_supported
    MICA_AVAILABLE = True
except ImportError:
    MICA_AVAILABLE = False

from ui.tokens import SIZE, SPACE


class AugieFrameless(FramelessWindow):
    """Frameless transparent always-on-top overlay."""

    SETTINGS_ORG = "Augie"
    SETTINGS_APP = "Overlay"

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setFixedWidth(SIZE.panel_width)
        self.setMinimumHeight(SIZE.panel_min_height)
        self.resize(SIZE.panel_width, SIZE.panel_expanded_height)

        self._pinned = True
        self._apply_mica()
        self._restore_position()

        # Re-assert topmost every 5s; games can steal Z-order.
        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(self._reassert_topmost)
        self._topmost_timer.start(5000)

        self._entrance_anim = None

    # --- Mica / Acrylic backdrop ---

    def _apply_mica(self):
        if not MICA_AVAILABLE:
            logger.debug("winmica not installed; using solid fill fallback")
            return
        try:
            if is_mica_supported():
                hwnd = int(self.winId())
                EnableMica(hwnd, BackdropType.MICA)
                logger.info("Win11 Mica backdrop enabled")
        except Exception as e:
            logger.warning(f"Mica enable failed: {e}")

    # --- Pin toggle (always-on-top) ---

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = pinned
        flags = self.windowFlags()
        if pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def is_pinned(self) -> bool:
        return self._pinned

    def _reassert_topmost(self):
        if not self._pinned or not self.isVisible():
            return
        self.raise_()
        if sys.platform == "win32" and hasattr(self, "winId"):
            try:
                import ctypes
                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x2
                SWP_NOSIZE = 0x1
                ctypes.windll.user32.SetWindowPos(
                    int(self.winId()), HWND_TOPMOST, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE,
                )
            except Exception:
                pass

    # --- Position persistence ---

    def _restore_position(self):
        try:
            settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
            saved = settings.value("panel_position")
            if saved is not None:
                self.move(saved)
                return
            screen = QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self.move(geo.right() - self.width() - SPACE.xl,
                          geo.top() + SPACE.xl)
        except Exception as e:
            logger.debug(f"position restore skipped: {e}")

    def moveEvent(self, event):
        super().moveEvent(event)
        if not hasattr(self, "_save_timer"):
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._save_position)
        self._save_timer.start(500)

    def _save_position(self):
        try:
            settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
            settings.setValue("panel_position", self.pos())
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if self._entrance_anim is None:
            try:
                from ui.anim.helpers import panel_entrance
                self._entrance_anim = panel_entrance(self)
                self._entrance_anim.start()
            except Exception:
                self._entrance_anim = True  # mark as attempted so we don't retry
