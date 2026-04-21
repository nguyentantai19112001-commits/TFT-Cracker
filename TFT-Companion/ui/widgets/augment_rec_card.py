"""AugmentRecCard — 176×100 individual augment recommendation tile."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT, RADIUS, SHADOW, SIZE, SPACE
from ui.fx import apply_shadow


_TIER_COLORS: dict[str, tuple[str, str]] = {
    "silver":   ("#C5C0E0", "#8A86A8"),
    "gold":     ("#FFD27A", "#FF9454"),
    "prismatic":("#C090F0", "#7A4AFF"),
}


class AugmentRecCard(QWidget):
    """Self-painting card for one augment recommendation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._display_name = ""
        self._tier = "gold"
        self._fit_score = 0.0
        self._why = ""
        self.setFixedSize(SIZE.augment_card_width, SIZE.augment_card_height)
        apply_shadow(self, SHADOW.elev_chip)

    def apply(self, display_name: str, tier: str, fit_score: float, why: str = "") -> None:
        self._display_name = display_name
        self._tier = tier
        self._fit_score = fit_score
        self._why = why
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(SIZE.augment_card_width, SIZE.augment_card_height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = SPACE.sm

        c1_hex, c2_hex = _TIER_COLORS.get(self._tier, _TIER_COLORS["gold"])

        # Card background — opaque elevated fill
        card_path = QPainterPath()
        card_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.chip, RADIUS.chip)
        bg_c = QColor(COLOR.elev_3)
        bg_c.setAlpha(255)
        p.fillPath(card_path, QBrush(bg_c))
        # Border
        p.setPen(QPen(QColor(*COLOR.border_accent_gold_rgba), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0, 0, w, h).adjusted(0, 0, -1, -1), RADIUS.chip, RADIUS.chip)
        # Inner top highlight
        hl = QColor(*COLOR.inner_highlight_rgba)
        p.setPen(QPen(hl, 1))
        p.drawLine(RADIUS.chip, 1, w - RADIUS.chip, 1)

        # Top gradient accent strip (4px)
        strip_path = QPainterPath()
        strip_path.addRoundedRect(QRectF(0, 0, w, 4 + RADIUS.chip), RADIUS.chip, RADIUS.chip)
        strip_path.addRect(QRectF(0, RADIUS.chip, w, 4))
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(c1_hex))
        grad.setColorAt(1, QColor(c2_hex))
        p.fillPath(strip_path, QBrush(grad))

        # Tier badge
        p.setPen(QPen(QColor(c1_hex)))
        f_tier = QFont()
        f_tier.setPointSize(8)
        f_tier.setWeight(QFont.Weight.Bold)
        p.setFont(f_tier)
        p.drawText(QRectF(pad, 8, w - pad * 2, 14),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   f"({self._tier.upper()})")

        # Fit score badge (right)
        p.setPen(QPen(QColor(COLOR.text_muted)))
        p.drawText(QRectF(pad, 8, w - pad * 2, 14),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{int(self._fit_score * 100)}")

        # Augment name
        p.setPen(QPen(QColor(COLOR.text_primary)))
        f_name = QFont()
        f_name.setPointSize(FONT.size_body)
        f_name.setWeight(QFont.Weight.DemiBold)
        p.setFont(f_name)
        name_rect = QRectF(pad, 26, w - pad * 2, 36)
        p.drawText(name_rect,
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                   self._display_name)

        # Why hint
        if self._why:
            p.setPen(QPen(QColor(COLOR.text_muted)))
            f_why = QFont()
            f_why.setPointSize(9)
            p.setFont(f_why)
            why_rect = QRectF(pad, 66, w - pad * 2, h - 70)
            p.drawText(why_rect,
                       Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                       self._why)

        p.end()
