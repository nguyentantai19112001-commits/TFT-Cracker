"""CompOptionCard — 240×320 card showing a single comp option."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath,
    QLinearGradient, QFont,
)
from PyQt6.QtWidgets import QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout

from ui.tokens import COLOR, FONT, RADIUS, SIZE, SPACE


_TIER_COLORS: dict[str, tuple[str, str]] = {
    "S": ("#FFD27A", "#FF9454"),  # gold gradient
    "A": ("#C5C0E0", "#8A86A8"),  # silver gradient
    "B": ("#C090F0", "#8A60C8"),  # purple gradient
    "C": ("#9AA3B0", "#6A7380"),  # gray gradient
}

_TIER_LABEL: dict[str, str] = {
    "S": "S · TOP",
    "A": "A · ALT",
    "B": "B · FLEX",
    "C": "C · LAST",
}


class CompOptionCard(QWidget):
    """Self-painting card for a single CompOption."""

    def __init__(self, is_primary: bool = False, parent=None):
        super().__init__(parent)
        self._is_primary = is_primary
        self._tier = "B"
        self._display_name = ""
        self._fit_score = 0.0
        self._primary_carry = ""
        self._why_this_fits = ""
        self._missing_units: list[str] = []
        self._core_units_held: int = 0
        self._core_units_total: int = 0

        self.setFixedSize(SIZE.comp_card_width, SIZE.comp_card_height)

    def apply(
        self,
        tier: str,
        display_name: str,
        fit_score: float,
        primary_carry: str,
        why_this_fits: str,
        missing_units: list[str],
        core_held: int,
        core_total: int,
    ) -> None:
        self._tier = tier
        self._display_name = display_name
        self._fit_score = fit_score
        self._primary_carry = primary_carry
        self._why_this_fits = why_this_fits
        self._missing_units = missing_units
        self._core_units_held = core_held
        self._core_units_total = core_total
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        c1_hex, c2_hex = _TIER_COLORS.get(self._tier, ("#9AA3B0", "#6A7380"))
        tier_label = _TIER_LABEL.get(self._tier, self._tier)

        # Card background — solid elevated fill
        card_path = QPainterPath()
        card_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.card, RADIUS.card)

        bg_c = QColor(COLOR.elev_4 if self._is_primary else COLOR.elev_3)
        bg_c.setAlpha(255)
        p.fillPath(card_path, QBrush(bg_c))
        # Border
        border_rgba = COLOR.border_accent_pink_rgba if self._is_primary else COLOR.border_strong_rgba
        p.setPen(QPen(QColor(*border_rgba), 2 if self._is_primary else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(card_path)
        # Inner top highlight
        hl = QColor(*COLOR.inner_highlight_rgba)
        p.setPen(QPen(hl, 1))
        p.drawLine(RADIUS.card, 1, w - RADIUS.card, 1)

        # Top accent gradient strip (24px)
        top_strip = QRectF(0, 0, w, 24)
        strip_path = QPainterPath()
        strip_path.addRoundedRect(QRectF(0, 0, w, 24 + RADIUS.card), RADIUS.card, RADIUS.card)
        strip_path.addRect(QRectF(0, RADIUS.card, w, 24))
        grad = QLinearGradient(top_strip.topLeft(), top_strip.topRight())
        c1 = QColor(c1_hex); c1.setAlpha(180)
        c2 = QColor(c2_hex); c2.setAlpha(100)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillPath(strip_path, QBrush(grad))

        pad = SPACE.md

        # Tier badge (top-left of strip)
        p.setPen(QPen(QColor(c1_hex)))
        f_tier = QFont()
        f_tier.setPointSize(FONT.size_body_small)
        f_tier.setWeight(QFont.Weight.Bold)
        f_tier.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        p.setFont(f_tier)
        p.drawText(QRectF(pad, 4, w - pad * 2, 18),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   tier_label)

        # Fit score badge (top-right)
        p.setPen(QPen(QColor(c2_hex)))
        f_fit = QFont()
        f_fit.setPointSize(FONT.size_body_small)
        p.setFont(f_fit)
        p.drawText(QRectF(0, 4, w - pad, 18),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"fit {self._fit_score:.2f}")

        y = 32

        # Display name
        p.setPen(QPen(QColor(COLOR.text_primary)))
        f_name = QFont()
        f_name.setPointSize(FONT.comp_name_size)
        f_name.setWeight(QFont.Weight.DemiBold)
        p.setFont(f_name)
        name_rect = QRectF(pad, y, w - pad * 2, 28)
        p.drawText(name_rect,
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                   self._display_name)
        y += 32

        # Primary carry
        if self._primary_carry:
            carry_name = self._primary_carry.split("_")[-1] if "_" in self._primary_carry else self._primary_carry
            p.setPen(QPen(QColor(COLOR.accent_pink)))
            f_carry = QFont()
            f_carry.setPointSize(FONT.size_body_small)
            p.setFont(f_carry)
            p.drawText(QRectF(pad, y, w - pad * 2, 16),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       f"Carry: {carry_name}")
            y += 20

        # Core progress bar
        if self._core_units_total > 0:
            bar_w = w - pad * 2
            bar_h = 6
            p.setPen(Qt.PenStyle.NoPen)
            bar_bg = QColor(COLOR.bg_input)
            p.setBrush(QBrush(bar_bg))
            p.drawRoundedRect(QRectF(pad, y, bar_w, bar_h), 3, 3)

            fill_frac = self._core_units_held / self._core_units_total
            if fill_frac > 0:
                fill_grad = QLinearGradient(pad, y, pad + bar_w * fill_frac, y)
                fill_grad.setColorAt(0, QColor(c1_hex))
                fill_grad.setColorAt(1, QColor(c2_hex))
                p.setBrush(QBrush(fill_grad))
                p.drawRoundedRect(QRectF(pad, y, bar_w * fill_frac, bar_h), 3, 3)

            y += 10
            p.setPen(QPen(QColor(COLOR.text_muted)))
            f_core = QFont()
            f_core.setPointSize(FONT.size_body_small)
            p.setFont(f_core)
            p.drawText(QRectF(pad, y, bar_w, 14),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       f"Core: {self._core_units_held}/{self._core_units_total}")
            y += 18

        # Divider
        p.setPen(QPen(QColor(*COLOR.border_subtle_rgba), 1))
        p.drawLine(int(pad), int(y), int(w - pad), int(y))
        y += 8

        # Why this fits
        p.setPen(QPen(QColor(COLOR.text_muted)))
        f_label = QFont()
        f_label.setPointSize(9)
        f_label.setWeight(QFont.Weight.DemiBold)
        f_label.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(f_label)
        p.drawText(QRectF(pad, y, w - pad * 2, 14),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   "WHY THIS FITS")
        y += 16

        p.setPen(QPen(QColor(COLOR.text_secondary)))
        f_why = QFont()
        f_why.setPointSize(FONT.size_body_small)
        p.setFont(f_why)
        f_why.setPointSize(FONT.comp_why_size)
        p.setFont(f_why)
        why_rect = QRectF(pad, y, w - pad * 2, 44)
        p.drawText(why_rect,
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                   self._why_this_fits or "—")

        p.end()
