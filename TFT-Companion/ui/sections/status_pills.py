"""Status pill row — neumorphic econ chips."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QFont, QLinearGradient,
)
from PyQt6.QtWidgets import QWidget, QHBoxLayout

from ui.tokens import COLOR, FONT, SIZE, SPACE


class _Chip(QWidget):
    """Neumorphic econ chip: colored icon tile + value + label."""

    def __init__(self, glyph: str, label: str,
                 color_from: str, color_to: str, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self._glyph = glyph
        self._label = label
        self._color_from = color_from
        self._color_to = color_to
        self._value = "—"
        self.setFixedHeight(SIZE.econ_chip_height)

    def set_value(self, value: str):
        self._value = value
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(max(96, len(self._value) * 10 + 64), SIZE.econ_chip_height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Chip body
        rect = QRectF(0, 0, w, h)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        # Base fill
        p.fillPath(path, QBrush(QColor(COLOR.bg_raised)))

        # Inner gradient sheen
        sheen = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        c1 = QColor(255, 255, 255); c1.setAlpha(10)
        c2 = QColor(255, 255, 255); c2.setAlpha(4)
        sheen.setColorAt(0, c1)
        sheen.setColorAt(1, c2)
        p.fillPath(path, QBrush(sheen))

        # Border
        border = QColor(255, 255, 255); border.setAlpha(15)
        p.setPen(QPen(border, 1))
        p.drawPath(path)

        # Inset top highlight
        hl = QColor(255, 255, 255); hl.setAlpha(28)
        p.fillRect(QRectF(14, 1, w - 28, 1), QBrush(hl))

        # Inset bottom shadow smear
        sh = QColor(0, 0, 0); sh.setAlpha(30)
        p.fillRect(QRectF(14, h - 2, w - 28, 2), QBrush(sh))

        # Icon tile
        ts = SIZE.econ_icon_tile
        tx, ty = 8.0, (h - ts) / 2
        tile_rect = QRectF(tx, ty, ts, ts)
        tile_path = QPainterPath()
        tile_path.addRoundedRect(tile_rect, 7, 7)

        tile_g = QLinearGradient(tile_rect.topLeft(), tile_rect.bottomRight())
        tile_g.setColorAt(0, QColor(self._color_from))
        tile_g.setColorAt(1, QColor(self._color_to))
        p.fillPath(tile_path, QBrush(tile_g))

        # Tile top highlight
        th = QColor(255, 255, 255); th.setAlpha(60)
        p.setPen(QPen(th, 1))
        p.drawLine(int(tx + 4), int(ty + 1), int(tx + ts - 4), int(ty + 1))

        # Tile bottom shadow
        td = QColor(0, 0, 0); td.setAlpha(40)
        p.setPen(QPen(td, 1))
        p.drawLine(int(tx + 4), int(ty + ts - 2), int(tx + ts - 4), int(ty + ts - 2))

        # Glyph on tile
        p.setPen(QPen(QColor(255, 255, 255)))
        gf = QFont()
        gf.setPointSize(11)
        gf.setWeight(QFont.Weight.Bold)
        p.setFont(gf)
        p.drawText(tile_rect, Qt.AlignmentFlag.AlignCenter, self._glyph)

        # Value text
        val_x = tx + ts + 8
        val_w = w - val_x - 6
        p.setPen(QPen(QColor(COLOR.text_primary)))
        vf = QFont("JetBrains Mono")
        vf.setPointSize(13)
        vf.setWeight(QFont.Weight.Bold)
        p.setFont(vf)
        p.drawText(QRectF(val_x, 0, val_w, h * 0.6),
                   Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                   self._value)

        # Label text
        p.setPen(QPen(QColor(COLOR.text_muted)))
        lf = QFont()
        lf.setPointSize(8)
        lf.setWeight(QFont.Weight.Medium)
        lf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(lf)
        p.drawText(QRectF(val_x, h * 0.6, val_w, h * 0.4),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                   self._label)

        p.end()


class StatusPills(QWidget):
    """Row of neumorphic econ chips."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, 0, SPACE.xl, 0)
        layout.setSpacing(SPACE.sm)

        self._gold = _Chip("◈", "gold", COLOR.econ_gold_from, COLOR.econ_gold_to)
        self._level = _Chip("Lv", "level", COLOR.econ_level_from, COLOR.econ_level_to)
        self._streak = _Chip("↗", "streak", COLOR.econ_streak_from, COLOR.econ_streak_to)
        self._econ = _Chip("$", "interest", COLOR.econ_interest_from, COLOR.econ_interest_to)

        for chip in (self._gold, self._level, self._streak, self._econ):
            layout.addWidget(chip)
        layout.addStretch()

    def apply(self, gold: int, level: int, streak: int, interest: int):
        self._gold.set_value(str(gold))
        self._level.set_value(str(level))
        streak_str = f"+{streak}" if streak > 0 else (f"{streak}" if streak < 0 else "0")
        self._streak.set_value(streak_str)
        self._econ.set_value(f"+{interest}")
