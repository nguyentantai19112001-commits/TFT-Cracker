"""CompOptionRow — section holding 3 CompOptionCards in a horizontal row."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt

from ui.tokens import SPACE
from ui.widgets.section_label import SectionLabel
from ui.widgets.comp_option_card import CompOptionCard


class CompOptionRow(QWidget):
    """Shows top comp + 2 alternates as three 240×320 cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE.md, 0, SPACE.md, 0)
        root.setSpacing(SPACE.sm)

        self._label = SectionLabel("TARGET COMP")
        root.addWidget(self._label)

        card_row = QHBoxLayout()
        card_row.setSpacing(SPACE.sm)
        card_row.setContentsMargins(0, 0, 0, 0)

        self._cards: list[CompOptionCard] = [
            CompOptionCard(is_primary=(i == 0))
            for i in range(3)
        ]
        for card in self._cards:
            card_row.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)

        card_row.addStretch()
        root.addLayout(card_row)

    def apply(self, top_comp: dict, alternates: list[dict]) -> None:
        options = [top_comp] + list(alternates[:2])
        for i, card in enumerate(self._cards):
            if i < len(options):
                opt = options[i]
                card.setVisible(True)
                card.apply(
                    tier=opt.get("tier", "B"),
                    display_name=opt.get("display_name", "—"),
                    fit_score=opt.get("fit_score", 0.0),
                    primary_carry=opt.get("primary_carry", ""),
                    why_this_fits=opt.get("why_this_fits", ""),
                    missing_units=[u.get("api_name", "") for u in opt.get("missing_units", [])],
                    core_held=len(opt.get("core_units_held", [])),
                    core_total=len(opt.get("core_units_held", [])) + len(opt.get("missing_units", [])),
                )
            else:
                card.setVisible(False)
