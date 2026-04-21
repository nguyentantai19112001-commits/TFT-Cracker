"""Actions list section — ranked ActionRow widgets."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ui.tokens import COLOR, FONT, SPACE
from ui.widgets.section_label import SectionLabel
from ui.widgets.action_row import ActionRow


class ActionsList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.xs)

        layout.addWidget(SectionLabel("Recommended Actions", COLOR.accent_gold))

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(SPACE.xs)
        layout.addWidget(self._rows_container)

        self._placeholder = QLabel("Waiting for pipeline…")
        self._placeholder.setStyleSheet(
            f"color: {COLOR.text_disabled}; font-size: {FONT.size_body_small}px;"
            f"font-style: italic; padding: 8px 0;"
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rows_layout.addWidget(self._placeholder)
        self._placeholder.setVisible(True)

        self._rows: list[ActionRow] = []

    def apply(self, actions: list[dict]):
        for row in self._rows:
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        if not actions:
            self._placeholder.setVisible(True)
            return

        self._placeholder.setVisible(False)
        for action in actions[:1]:
            row = ActionRow()
            row.set_action(
                headline=action.get("headline", ""),
                subline=action.get("subline", ""),
                score=action.get("score", 0.0),
                priority=action.get("priority", "medium"),
                icon_glyph=action.get("glyph", "→"),
                icon_color=action.get("color", ""),
            )
            self._rows.append(row)
            self._rows_layout.addWidget(row)
