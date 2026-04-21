"""Trait chip — pill with gradient dot + label."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT, RADIUS, SPACE


_TIER_COLORS: dict[str, tuple[str, str]] = {
    "bronze":   (COLOR.accent_gold,    COLOR.cost_1),
    "silver":   (COLOR.text_secondary, COLOR.text_tertiary),
    "gold":     (COLOR.accent_gold,    COLOR.accent_pink),
    "chromatic":(COLOR.accent_pink,    COLOR.accent_blue),
    "default":  (COLOR.accent_blue,    COLOR.accent_purple),
}


class TraitChip(QWidget):
    """Pill: colored dot + trait name, optionally dim if inactive."""

    def __init__(self, trait_name: str = "", tier: str = "default", active: bool = True, parent=None):
        super().__init__(parent)
        self._trait = trait_name
        self._tier = tier
        self._active = active
        self.setAutoFillBackground(False)
        self.setMinimumHeight(24)

    def set_trait(self, trait_name: str, tier: str = "default", active: bool = True):
        self._trait = trait_name
        self._tier = tier
        self._active = active
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(len(self._trait) * 7 + 28, 22)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)

        # Pill background — slightly lighter than panel bg so chips read as distinct elements
        bg = QColor(47, 44, 72, 235 if self._active else 130)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS.chip, RADIUS.chip)
        p.fillPath(path, QBrush(bg))

        # Border — use tier accent color so each chip has clear visual identity
        c1, _ = _TIER_COLORS.get(self._tier, _TIER_COLORS["default"])
        border_color = QColor(c1)
        border_color.setAlpha(200 if self._active else 70)
        p.setPen(QPen(border_color, 1.5))
        p.drawPath(path)

        # Gradient dot
        dot_r = 5
        dot_x = SPACE.sm + dot_r
        dot_y = h / 2
        c1, c2 = _TIER_COLORS.get(self._tier, _TIER_COLORS["default"])
        g = QLinearGradient(dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r)
        g.setColorAt(0, QColor(c1))
        g.setColorAt(1, QColor(c2))
        dot_path = QPainterPath()
        dot_path.addEllipse(QRectF(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2))
        p.fillPath(dot_path, QBrush(g))

        # Label
        text_color = QColor(COLOR.text_primary if self._active else COLOR.text_muted)
        p.setPen(QPen(text_color))
        f = QFont()
        f.setPointSize(FONT.size_body_small)
        f.setWeight(QFont.Weight.Medium)
        p.setFont(f)
        text_rect = QRectF(dot_x + dot_r + SPACE.xs, 0, w - dot_x - dot_r - SPACE.xs - SPACE.sm, h)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._trait)
        p.end()
