"""AugmentPreviewV3 — tier probability bar + augment rec cards."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt

from ui.tokens import SPACE
from ui.widgets.section_label import SectionLabel
from ui.widgets.augment_tier_bar import AugmentTierBar
from ui.widgets.augment_rec_card import AugmentRecCard


class AugmentPreviewV3(QWidget):
    """Shows AugmentQuality output: tier bar + up to 4 rec cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE.md, 0, SPACE.md, 0)
        root.setSpacing(SPACE.sm)

        self._label = SectionLabel("PRIORITY AUGMENTS")
        root.addWidget(self._label)

        self._tier_bar = AugmentTierBar()
        root.addWidget(self._tier_bar)

        card_row = QHBoxLayout()
        card_row.setSpacing(SPACE.sm)
        card_row.setContentsMargins(0, 0, 0, 0)
        self._cards: list[AugmentRecCard] = [AugmentRecCard() for _ in range(4)]
        for card in self._cards:
            card.setVisible(False)
            card_row.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        card_row.addStretch()
        root.addLayout(card_row)

    def apply(
        self,
        silver: float = 0.28,
        gold: float = 0.62,
        prismatic: float = 0.10,
        conditional_text: str = "",
        augment_recs: list[dict] | None = None,
    ) -> None:
        self._tier_bar.apply(silver, gold, prismatic, conditional_text)

        recs = augment_recs or []
        for i, card in enumerate(self._cards):
            if i < len(recs):
                rec = recs[i]
                card.setVisible(True)
                card.apply(
                    display_name=rec.get("display_name", "—"),
                    tier=rec.get("tier", "gold"),
                    fit_score=rec.get("fit_score", 0.0),
                    why=rec.get("why", ""),
                )
            else:
                card.setVisible(False)
