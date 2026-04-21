"""Probability card — animated bar showing roll probability."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT, SIZE, SPACE, RADIUS, MOTION


class ProbCard(QWidget):
    """Card showing roll probability with an animated fill bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = "Roll probability"
        self._sublabel = ""
        self._prob: float = 0.0          # 0.0–1.0
        self._displayed_prob: float = 0.0
        self._anim: QPropertyAnimation | None = None

    def _get_displayed_prob(self) -> float:
        return self._displayed_prob

    def _set_displayed_prob(self, v: float):
        self._displayed_prob = v
        self.update()

    displayed_prob = pyqtProperty(float, _get_displayed_prob, _set_displayed_prob)

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

        # Card bg
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.card, RADIUS.card)
        p.fillPath(bg_path, QBrush(QColor(COLOR.bg_raised)))
        p.setPen(QPen(QColor(*COLOR.border_subtle_rgba), 1))
        p.drawPath(bg_path)

        # Label
        p.setPen(QPen(QColor(COLOR.text_primary)))
        f = QFont()
        f.setPointSize(FONT.size_body)
        f.setWeight(QFont.Weight.Medium)
        p.setFont(f)
        label_rect = QRectF(ph, pv, w - ph * 2 - 60, 20)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._label)

        # Percent readout
        pct_text = f"{self._displayed_prob * 100:.1f}%"
        pct_color = self._pct_color(self._displayed_prob)
        p.setPen(QPen(pct_color))
        fm = QFont()
        fm.setPointSize(FONT.size_metric)
        fm.setWeight(QFont.Weight.Bold)
        p.setFont(fm)
        pct_rect = QRectF(w - ph - 70, pv - 4, 70, 32)
        p.drawText(pct_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, pct_text)

        # Sub-label
        if self._sublabel:
            p.setPen(QPen(QColor(COLOR.text_tertiary)))
            fs = QFont()
            fs.setPointSize(FONT.size_body_small)
            p.setFont(fs)
            sub_rect = QRectF(ph, pv + 22, w - ph * 2, 16)
            p.drawText(sub_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._sublabel)

        # Bar track
        bar_y = h - pv - SIZE.prob_bar_height
        bar_w = w - ph * 2
        track_rect = QRectF(ph, bar_y, bar_w, SIZE.prob_bar_height)
        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, 3, 3)
        p.fillPath(track_path, QBrush(QColor(COLOR.bg_input)))

        # Bar fill
        fill_w = bar_w * self._displayed_prob
        if fill_w > 0:
            fill_rect = QRectF(ph, bar_y, fill_w, SIZE.prob_bar_height)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, 3, 3)
            g = QLinearGradient(fill_rect.left(), 0, fill_rect.right(), 0)
            g.setColorAt(0, QColor(COLOR.accent_blue))
            g.setColorAt(1, pct_color)
            p.fillPath(fill_path, QBrush(g))

        p.end()

    def _pct_color(self, prob: float) -> QColor:
        if prob >= 0.5:
            return QColor(COLOR.accent_green)
        if prob >= 0.2:
            return QColor(COLOR.accent_gold)
        return QColor(COLOR.accent_red)
