"""Warning block — red-tinted rounded container for urgent messages."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT, RADIUS, SPACE, SHADOW
from ui.fx import apply_shadow


class WarningBlock(QWidget):
    """Painted red-tinted pill block with icon glyph + message text."""

    def __init__(self, message: str = "", parent=None):
        super().__init__(parent)
        self._message = message
        self._glyph = "⚠"
        self.setMinimumHeight(40)
        apply_shadow(self, SHADOW.elev_card)

    def set_message(self, message: str, glyph: str = "⚠"):
        self._message = message
        self._glyph = glyph
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)

        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS.row, RADIUS.row)

        bg = QColor(*COLOR.accent_red_soft_rgba)
        p.fillPath(path, QBrush(bg))

        border = QColor(COLOR.accent_red)
        border.setAlpha(60)
        p.setPen(QPen(border, 1))
        p.drawPath(path)

        # Glyph
        p.setPen(QPen(QColor(COLOR.accent_red)))
        fg = QFont()
        fg.setPointSize(FONT.size_body)
        p.setFont(fg)
        glyph_rect = QRectF(SPACE.md, 0, 20, h)
        p.drawText(glyph_rect, Qt.AlignmentFlag.AlignCenter, self._glyph)

        # Message
        p.setPen(QPen(QColor(COLOR.text_primary)))
        fm = QFont()
        fm.setPointSize(FONT.size_body_small)
        p.setFont(fm)
        msg_rect = QRectF(SPACE.md + 22, 0, w - SPACE.md - 22 - SPACE.md, h)
        p.drawText(msg_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._message)
        p.end()
