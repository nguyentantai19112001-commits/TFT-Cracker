"""AugmentTierBar — horizontal probability bar for augment tier distribution."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui.tokens import COLOR, FONT, RADIUS, SIZE, SPACE


_TIER_COLORS: dict[str, tuple[str, str]] = {
    "silver":   ("#C5C0E0", "#8A86A8"),
    "gold":     ("#FFD27A", "#FF9454"),
    "prismatic":("#C090F0", "#7A4AFF"),
}


class AugmentTierBar(QWidget):
    """Shows silver/gold/prismatic probability bars with labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._silver = 0.28
        self._gold = 0.62
        self._prismatic = 0.10
        self._conditional_text = ""
        self.setFixedHeight(SIZE.augment_tier_bar_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def apply(self, silver: float, gold: float, prismatic: float, conditional_text: str = "") -> None:
        self._silver = silver
        self._gold = gold
        self._prismatic = prismatic
        self._conditional_text = conditional_text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = SPACE.md

        # Background
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.row, RADIUS.row)
        bg_c = QColor(COLOR.bg_raised)
        p.fillPath(bg_path, QBrush(bg_c))

        bar_y = 10
        bar_h = 12
        bar_w = w - pad * 2
        bar_total = bar_w

        # Draw probability labels at top
        f_label = QFont()
        f_label.setPointSize(FONT.size_body_small)
        f_label.setWeight(QFont.Weight.Medium)
        p.setFont(f_label)

        probs = [
            ("Silver", self._silver, _TIER_COLORS["silver"][0]),
            ("Gold",   self._gold,   _TIER_COLORS["gold"][0]),
            ("Prismatic", self._prismatic, _TIER_COLORS["prismatic"][0]),
        ]

        label_section_w = bar_w / 3
        for i, (name, prob, color_hex) in enumerate(probs):
            p.setPen(QPen(QColor(color_hex)))
            lx = pad + i * label_section_w
            label_rect = QRectF(lx, 2, label_section_w, 12)
            align = (Qt.AlignmentFlag.AlignLeft if i == 0 else
                     Qt.AlignmentFlag.AlignCenter if i == 1 else
                     Qt.AlignmentFlag.AlignRight)
            p.drawText(label_rect, align | Qt.AlignmentFlag.AlignVCenter,
                       f"{name} {prob:.0%}")

        bar_y = 20
        # Silver bar
        x = pad
        silver_w = bar_total * self._silver
        _draw_prob_bar(p, x, bar_y, max(silver_w, 4), bar_h, *_TIER_COLORS["silver"])
        x += bar_total * self._silver + 2

        # Gold bar
        gold_w = bar_total * self._gold
        _draw_prob_bar(p, x, bar_y, max(gold_w, 4), bar_h, *_TIER_COLORS["gold"])
        x += bar_total * self._gold + 2

        # Prismatic bar
        pris_w = bar_total * self._prismatic
        _draw_prob_bar(p, x, bar_y, max(pris_w, 4), bar_h, *_TIER_COLORS["prismatic"])

        # Conditional text
        if self._conditional_text:
            p.setPen(QPen(QColor(COLOR.text_muted)))
            f_cond = QFont()
            f_cond.setPointSize(9)
            p.setFont(f_cond)
            cond_rect = QRectF(pad, bar_y + bar_h + 4, w - pad * 2, 14)
            p.drawText(cond_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self._conditional_text)

        p.end()


def _draw_prob_bar(p: QPainter, x: float, y: float, w: float, h: float,
                   c1_hex: str, c2_hex: str) -> None:
    grad = QLinearGradient(x, y, x + w, y)
    grad.setColorAt(0, QColor(c1_hex))
    grad.setColorAt(1, QColor(c2_hex))
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)
    p.fillPath(path, QBrush(grad))
