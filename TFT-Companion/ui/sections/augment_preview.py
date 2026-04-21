"""Augment preview section — top augment picks with tier badges."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from ui.tokens import COLOR, FONT, RADIUS, SPACE
from ui.widgets.section_label import SectionLabel
from ui.widgets.item_icon import ItemIcon


_TIER_COLORS = {
    "silver":    COLOR.text_secondary,
    "gold":      COLOR.accent_gold,
    "prismatic": COLOR.accent_pink,
}


class _AugmentRow(QWidget):
    def __init__(self, augment: dict, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE.xs, 0, SPACE.xs)
        layout.setSpacing(SPACE.sm)

        icon = ItemIcon(augment.get("api_name", ""), "ap")
        layout.addWidget(icon)

        name = QLabel(augment.get("name", ""))
        name.setStyleSheet(
            f"color: {COLOR.text_primary}; font-size: {FONT.size_body_small}px;"
        )
        layout.addWidget(name, 1)

        tier = augment.get("tier", "silver").lower()
        tier_color = _TIER_COLORS.get(tier, COLOR.text_tertiary)
        tier_label = QLabel(tier.capitalize())
        tier_label.setStyleSheet(
            f"color: {tier_color}; font-size: {FONT.size_badge}px;"
            f"font-weight: {FONT.weight_semibold};"
        )
        layout.addWidget(tier_label)


class AugmentPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.xs)

        layout.addWidget(SectionLabel("Top Augments"))
        self._container = QVBoxLayout()
        container_widget = QWidget()
        container_widget.setLayout(self._container)
        layout.addWidget(container_widget)
        self._rows: list[_AugmentRow] = []

    def apply(self, augments: list[dict]):
        for row in self._rows:
            self._container.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        for aug in augments[:3]:
            row = _AugmentRow(aug)
            self._rows.append(row)
            self._container.addWidget(row)
