"""Footer — latency indicator + disclaimer."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ui.tokens import COLOR, FONT, SPACE


class Footer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.sm)

        self._latency_label = QLabel("●  —ms")
        self._latency_label.setStyleSheet(
            f"color: {COLOR.text_muted}; font-size: {FONT.size_footer}px;"
            f"font-family: 'JetBrains Mono', Consolas, monospace;"
        )
        layout.addWidget(self._latency_label)
        layout.addStretch()

        disclaimer = QLabel("Educational use only")
        disclaimer.setStyleSheet(
            f"color: {COLOR.text_disabled}; font-size: {FONT.size_footer}px;"
        )
        disclaimer.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(disclaimer)

    def set_latency(self, ms: int | None):
        if ms is None:
            self._latency_label.setText("●  —ms")
            self._latency_label.setStyleSheet(
                f"color: {COLOR.text_muted}; font-size: {FONT.size_footer}px;"
            )
        else:
            color = (COLOR.accent_green if ms < 500
                     else COLOR.accent_gold if ms < 1500
                     else COLOR.accent_red)
            self._latency_label.setText(f"●  {ms}ms")
            self._latency_label.setStyleSheet(
                f"color: {color}; font-size: {FONT.size_footer}px;"
            )
