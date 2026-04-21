"""Status pill row — gold, level, streak, econ pills."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QHBoxLayout

from ui.tokens import COLOR, FONT, RADIUS, SPACE


class _Pill(QWidget):
    def __init__(self, glyph: str, color: str, parent=None):
        super().__init__(parent)
        self._glyph = glyph
        self._color = color
        self._value = "—"
        self.setFixedHeight(26)

    def set_value(self, value: str):
        self._value = value
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(max(60, len(self._value) * 8 + 30), 26)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        c = QColor(self._color)
        rect = QRectF(0, 0, w, h)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS.pill, RADIUS.pill)
        bg = QColor(c)
        bg.setAlpha(26)
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(c, 1))
        p.drawPath(path)
        p.setPen(QPen(c))
        f = QFont()
        f.setPointSize(FONT.size_body_small)
        f.setWeight(QFont.Weight.Medium)
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._glyph} {self._value}")
        p.end()


class StatusPills(QWidget):
    """Row of econ status pills."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.sm)

        self._gold = _Pill("◈", COLOR.accent_gold)
        self._level = _Pill("Lv", COLOR.accent_blue)
        self._streak = _Pill("↗", COLOR.accent_green)
        self._econ = _Pill("$", COLOR.accent_purple)

        for pill in (self._gold, self._level, self._streak, self._econ):
            layout.addWidget(pill)
        layout.addStretch()

    def apply(self, gold: int, level: int, streak: int, interest: int):
        self._gold.set_value(str(gold))
        self._level.set_value(str(level))
        streak_str = f"+{streak}" if streak > 0 else (f"{streak}" if streak < 0 else "0")
        self._streak.set_value(streak_str)
        self._econ.set_value(f"+{interest}")
