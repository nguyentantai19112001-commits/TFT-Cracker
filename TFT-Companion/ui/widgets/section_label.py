"""Section label — uppercase spaced caps divider."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from ui.tokens import COLOR, FONT


class SectionLabel(QLabel):
    """Uppercase, letter-spaced, muted section header."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(
            f"color: {COLOR.text_muted};"
            f"font-size: {FONT.size_section_label}px;"
            f"font-weight: {FONT.weight_semibold};"
            f"letter-spacing: {FONT.letter_spacing_caps}px;"
            f"text-transform: uppercase;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def setText(self, text: str):
        super().setText(text.upper())
