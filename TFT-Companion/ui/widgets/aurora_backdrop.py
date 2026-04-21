"""Aurora backdrop — 3 soft radial gradient blobs painted behind content."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QBrush
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR


_BLOBS = [
    # (cx_frac, cy_frac, radius_frac, color_hex, alpha)
    (0.15, 0.10, 0.55, COLOR.accent_pink,   28),
    (0.85, 0.30, 0.50, COLOR.accent_blue,   22),
    (0.50, 0.80, 0.60, COLOR.accent_purple, 18),
]


class AuroraBackdrop(QWidget):
    """Full-panel blob layer; place behind all content, WA_TransparentForMouseEvents."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        for cx_f, cy_f, r_f, color_hex, alpha in _BLOBS:
            cx = w * cx_f
            cy = h * cy_f
            radius = max(w, h) * r_f
            grad = QRadialGradient(QPointF(cx, cy), radius)
            c_center = QColor(color_hex)
            c_center.setAlpha(alpha)
            c_edge = QColor(color_hex)
            c_edge.setAlpha(0)
            grad.setColorAt(0, c_center)
            grad.setColorAt(1, c_edge)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
        p.end()
