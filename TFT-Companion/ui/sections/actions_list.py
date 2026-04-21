"""Actions list section — ranked ActionRow widgets."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ui.tokens import SPACE
from ui.widgets.section_label import SectionLabel
from ui.widgets.action_row import ActionRow


class ActionsList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.xs)

        layout.addWidget(SectionLabel("Recommended Actions"))

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(SPACE.xs)
        layout.addWidget(self._rows_container)

        self._rows: list[ActionRow] = []

    def apply(self, actions: list[dict]):
        for row in self._rows:
            self._rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        for action in actions[:5]:
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
