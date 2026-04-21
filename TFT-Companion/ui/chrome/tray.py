"""System tray icon + menu. Minimizing the overlay hides it here."""
from __future__ import annotations
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu


class AugieTray(QObject):
    show_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, icon_path: str = "", parent=None):
        super().__init__(parent)
        self._icon = QSystemTrayIcon(QIcon(icon_path) if icon_path else QIcon())
        menu = QMenu()

        show_act = QAction("Show Augie", menu)
        show_act.triggered.connect(self.show_requested.emit)
        hide_act = QAction("Hide", menu)
        hide_act.triggered.connect(self.hide_requested.emit)
        menu.addAction(show_act)
        menu.addAction(hide_act)
        menu.addSeparator()
        quit_act = QAction("Quit Augie", menu)
        quit_act.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_act)

        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)
        self._icon.show()
        self._visible = True

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._visible:
                self.hide_requested.emit()
                self._visible = False
            else:
                self.show_requested.emit()
                self._visible = True

    def set_visible_state(self, visible: bool):
        self._visible = visible
