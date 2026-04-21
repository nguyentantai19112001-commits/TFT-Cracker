"""Carries section — item recommendations per carry."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from ui.tokens import COLOR, FONT, SPACE
from ui.widgets.section_label import SectionLabel
from ui.widgets.champ_icon import TinyChampIcon
from ui.widgets.item_icon import ItemIcon


class _CarryRow(QWidget):
    def __init__(self, champ: dict, items: list[dict], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE.xs, 0, SPACE.xs)
        layout.setSpacing(SPACE.sm)

        icon = TinyChampIcon(champ.get("api_name", ""), champ.get("cost", 1))
        layout.addWidget(icon)

        name = QLabel(champ.get("name", ""))
        name.setStyleSheet(
            f"color: {COLOR.text_secondary}; font-size: {FONT.size_body_small}px;"
        )
        layout.addWidget(name)
        layout.addStretch()

        for item in items[:3]:
            item_icon = ItemIcon(item.get("api_name", ""), item.get("category", "ap"))
            layout.addWidget(item_icon)


class CarriesSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.xs)

        layout.addWidget(SectionLabel("Carry Items"))

        self._container = QVBoxLayout()
        container_widget = QWidget()
        container_widget.setLayout(self._container)
        layout.addWidget(container_widget)

        self._rows: list[_CarryRow] = []

    def apply(self, carries: list[dict]):
        for row in self._rows:
            self._container.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        for carry in carries[:3]:
            row = _CarryRow(carry, carry.get("items", []))
            self._rows.append(row)
            self._container.addWidget(row)
