"""Probability card — animated bar showing roll probability."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT, SIZE, SPACE, RADIUS, MOTION
from ui.fx import apply_shadow
from ui.tokens import SHADOW


class ProbCard(QWidget):
    """Card showing roll probability with an animated fill bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = "Roll probability"
        self._sublabel = ""
        self._prob: float = 0.0
        self._displayed_prob: float = 0.0
        self._anim: QPropertyAnimation | None = None
        apply_shadow(self, SHADOW.elev_card)

    def _get_displayed_prob(self) -> float:
        return self._displayed_prob

    def _set_displayed_prob(self, v: float):
        self._displayed_prob = v
        self.update()

    displayed_prob = pyqtProperty(float, _get_displayed_prob, _set_displayed_prob)

    def sizeHint(self) -> QSize:
        return QSize(460, 92)

    def minimumSizeHint(self) -> QSize:
        return QSize(460, 92)

    def set_probability(self, prob: float, label: str = "", sublabel: str = ""):
        prob = max(0.0, min(1.0, prob))
        self._prob = prob
        if label:
            self._label = label
        if sublabel:
            self._sublabel = sublabel

        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"displayed_prob", self)
        self._anim.setDuration(MOTION.medium)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(self._displayed_prob)
        self._anim.setEndValue(prob)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        ph = SIZE.prob_card_padding_h
        pv = SIZE.prob_card_padding_v

        # Card bg — elevated opaque fill
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.card, RADIUS.card)
        bg = QColor(COLOR.elev_3)
        bg.setAlpha(255)
        p.fillPath(bg_path, QBrush(bg))
        p.setPen(QPen(QColor(*COLOR.border_strong_rgba), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bg_path)

        # Inner top highlight (glassmorphic signature)
        hl = QColor(255, 255, 255); hl.setAlpha(30)
        p.setPen(QPen(hl, 1))
        p.drawLine(int(RADIUS.card), 1, int(w - RADIUS.card), 1)

        # Label
        p.setPen(QPen(QColor(COLOR.text_primary)))
        f = QFont()
        f.setPointSize(FONT.size_body)
        f.setWeight(QFont.Weight.Medium)
        p.setFont(f)
        label_rect = QRectF(ph, pv, w - ph * 2 - 120, 20)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._label)

        # Percent readout — gradient fill via QPainterPath
        pct_text = f"{self._displayed_prob * 100:.1f}%"
        pct_color, pct_color2 = self._bar_colors(self._displayed_prob)
        fm_font = QFont("JetBrains Mono")
        fm_font.setPointSize(FONT.size_metric)
        fm_font.setWeight(QFont.Weight.Bold)
        p.setFont(fm_font)
        fm = p.fontMetrics()
        pct_w = fm.horizontalAdvance(pct_text)
        pct_x = w - ph - 120
        pct_y = pv + fm.ascent() - 4

        pct_path = QPainterPath()
        pct_path.addText(pct_x + (120 - pct_w), pct_y, fm_font, pct_text)
        g = QLinearGradient(pct_x, 0, pct_x + 120, 0)
        g.setColorAt(0, pct_color)
        g.setColorAt(1, pct_color2)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(pct_path, QBrush(g))

        # Sub-label with pool icon prefix
        if self._sublabel:
            p.setPen(QPen(QColor(COLOR.text_tertiary)))
            fs = QFont()
            fs.setPointSize(FONT.size_body_small)
            p.setFont(fs)
            sub_rect = QRectF(ph, pv + 22, w - ph * 2, 16)
            p.drawText(sub_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       f"◉ {self._sublabel}")

        # Bar track
        bar_y = h - pv - SIZE.prob_bar_height
        bar_w = w - ph * 2
        track_rect = QRectF(ph, bar_y, bar_w, SIZE.prob_bar_height)
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, 3, 3)
        p.fillPath(track_path, QBrush(QColor(COLOR.bg_input)))

        # Bar fill + glow
        fill_w = bar_w * self._displayed_prob
        if fill_w > 0:
            fill_rect = QRectF(ph, bar_y, fill_w, SIZE.prob_bar_height)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, 3, 3)

            # Glow under the fill (radial, below the fill rect)
            glow_cx = ph + fill_w / 2
            glow = QRadialGradient(glow_cx, bar_y + SIZE.prob_bar_height, fill_w * 0.6)
            gc = QColor(pct_color); gc.setAlpha(60)
            ge = QColor(pct_color); ge.setAlpha(0)
            glow.setColorAt(0, gc)
            glow.setColorAt(1, ge)
            glow_rect = QRectF(ph, bar_y - 4, fill_w, SIZE.prob_bar_height + 8)
            p.fillRect(glow_rect, QBrush(glow))

            # Fill gradient
            fg = QLinearGradient(fill_rect.left(), 0, fill_rect.right(), 0)
            fg.setColorAt(0, pct_color)
            fg.setColorAt(1, pct_color2)
            p.fillPath(fill_path, QBrush(fg))

        p.end()

    def _bar_colors(self, prob: float) -> tuple[QColor, QColor]:
        if prob >= 0.70:
            return QColor(COLOR.accent_green), QColor("#4ACEB0")
        if prob >= 0.40:
            return QColor(COLOR.accent_gold), QColor(COLOR.accent_pink)
        return QColor(COLOR.accent_pink), QColor(COLOR.accent_red)
