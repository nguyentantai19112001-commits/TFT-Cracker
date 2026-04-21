"""Probability section — hit-rate card for the key unit."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ui.tokens import COLOR, SPACE
from ui.widgets.prob_card import ProbCard
from ui.widgets.section_label import SectionLabel


class ProbSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.sm)

        layout.addWidget(SectionLabel("Roll Probability", COLOR.accent_pink))
        self.card = ProbCard()
        layout.addWidget(self.card)

    def apply(self, prob: float, label: str = "", sublabel: str = ""):
        self.card.set_probability(prob, label=label, sublabel=sublabel)
