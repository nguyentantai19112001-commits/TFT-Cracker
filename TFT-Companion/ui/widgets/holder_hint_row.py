"""HolderHintRow — compact strip surfacing one item-holder recommendation."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui.tokens import COLOR, FONT, RADIUS, SPACE


class HolderHintRow(QWidget):
    """Blue-accent strip showing the highest-priority holder matrix hint."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hint_text = ""
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setVisible(False)

    def apply_hint(self, text: str) -> None:
        self._hint_text = text
        self.setVisible(bool(text))
        self.update()

    def paintEvent(self, event):
        if not self._hint_text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background — elev_1 solid fill
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.row, RADIUS.row)
        bg_c = QColor(COLOR.elev_1)
        bg_c.setAlpha(255)
        p.fillPath(bg_path, QBrush(bg_c))
        # Border
        p.setPen(QPen(QColor(*COLOR.border_subtle_rgba), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0, 0, w, h).adjusted(0, 0, -1, -1), RADIUS.row, RADIUS.row)
        # Inner top highlight
        hl = QColor(*COLOR.inner_highlight_rgba)
        p.setPen(QPen(hl, 1))
        p.drawLine(RADIUS.row, 1, w - RADIUS.row, 1)

        # Blue left accent bar
        bar_path = QPainterPath()
        bar_path.addRoundedRect(QRectF(0, 4, 4, h - 8), 2, 2)
        p.fillPath(bar_path, QBrush(QColor(COLOR.accent_blue)))

        # Hint text
        left_pad = 4 + SPACE.lg
        p.setPen(QPen(QColor(COLOR.text_secondary)))
        f = QFont()
        f.setPointSize(FONT.size_body)
        f.setWeight(QFont.Weight.Medium)
        p.setFont(f)
        p.drawText(
            QRectF(left_pad, 0, w - left_pad - SPACE.md, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._hint_text,
        )
        p.end()
