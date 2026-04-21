"""Target comp section — trait chips + champion icon strip."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from ui.tokens import SPACE
from ui.widgets.section_label import SectionLabel
from ui.widgets.trait_chip import TraitChip
from ui.widgets.champ_icon import TinyChampIcon


class TargetComp(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.sm)

        layout.addWidget(SectionLabel("Target Comp"))

        self._trait_row = QHBoxLayout()
        self._trait_row.setSpacing(SPACE.xs)
        trait_widget = QWidget()
        trait_widget.setLayout(self._trait_row)
        layout.addWidget(trait_widget)

        self._champ_row = QHBoxLayout()
        self._champ_row.setSpacing(SPACE.xs)
        champ_widget = QWidget()
        champ_widget.setLayout(self._champ_row)
        layout.addWidget(champ_widget)

        self._trait_chips: list[TraitChip] = []
        self._champ_icons: list[TinyChampIcon] = []

    def apply(self, traits: list[dict], champions: list[dict]):
        self._clear_layout(self._trait_row, self._trait_chips)
        self._clear_layout(self._champ_row, self._champ_icons)

        for t in traits[:6]:
            chip = TraitChip(t.get("name", ""), t.get("tier", "default"), t.get("active", True))
            self._trait_chips.append(chip)
            self._trait_row.addWidget(chip)
        self._trait_row.addStretch()

        for c in champions[:9]:
            icon = TinyChampIcon(c.get("api_name", ""), c.get("cost", 1))
            self._champ_icons.append(icon)
            self._champ_row.addWidget(icon)
        self._champ_row.addStretch()

    def _clear_layout(self, layout: QHBoxLayout, store: list):
        for w in store:
            layout.removeWidget(w)
            w.deleteLater()
        store.clear()
