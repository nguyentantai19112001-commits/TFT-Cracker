"""Section label — colored bullet + text + gradient hairline divider."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT


_LABEL_TEXT_COLOR = "#b4adcd"


class SectionLabel(QWidget):
    """Paint-based section header: bullet ■ LABEL ─────────────────"""

    def __init__(self, text: str = "", color: str = COLOR.text_muted, parent=None):
        super().__init__(parent)
        self._text = text.upper()
        self._color = color
        self.setFixedHeight(20)
        self.setAutoFillBackground(False)

    def setText(self, text: str):
        self._text = text.upper()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(200, 20)

    def minimumSizeHint(self) -> QSize:
        return QSize(80, 20)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 4×4 color bullet
        bsize = 4
        bullet_color = QColor(self._color)
        bullet_rect = QRectF(0, (h - bsize) / 2, bsize, bsize)
        p.setBrush(QBrush(bullet_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(bullet_rect, 1.5, 1.5)

        # Label text
        text_x = bsize + 6
        f = QFont()
        f.setPointSize(FONT.size_section_label)
        f.setWeight(QFont.Weight.DemiBold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.8)
        p.setFont(f)
        fm = p.fontMetrics()
        text_w = fm.horizontalAdvance(self._text)

        p.setPen(QPen(QColor(_LABEL_TEXT_COLOR)))
        p.drawText(QRectF(text_x, 0, text_w + 2, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._text)

        # Gradient hairline to the right
        line_x = text_x + text_w + 8
        if line_x < w - 4:
            ly = h / 2
            grad = QLinearGradient(QPointF(line_x, ly), QPointF(w, ly))
            s = QColor(_LABEL_TEXT_COLOR); s.setAlpha(80)
            e = QColor(_LABEL_TEXT_COLOR); e.setAlpha(0)
            grad.setColorAt(0, s)
            grad.setColorAt(1, e)
            p.setPen(QPen(QBrush(grad), 1))
            p.drawLine(QPointF(line_x, ly), QPointF(w - 2, ly))

        p.end()
