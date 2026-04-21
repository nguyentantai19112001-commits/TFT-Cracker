"""Action row widget — icon + two-line text + priority score badge."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QSize, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT, SIZE, SPACE, RADIUS, MOTION


_PRIORITY_COLORS = {
    "high":   COLOR.accent_pink,
    "medium": COLOR.accent_gold,
    "low":    COLOR.accent_blue,
}


class ActionRow(QWidget):
    """Painted row: left icon square, headline + sub-line, right score pill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon_glyph = "→"
        self._icon_color = COLOR.accent_blue
        self._headline = ""
        self._subline = ""
        self._score: float = 0.0
        self._priority = "medium"
        self._hover_t: float = 0.0
        self._anim: QPropertyAnimation | None = None
        self.setMinimumHeight(SIZE.action_row_min_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # pyqtProperty for hover animation (Phase 5 attaches the animation)
    def _get_hover_t(self) -> float:
        return self._hover_t

    def _set_hover_t(self, v: float):
        self._hover_t = v
        self.update()

    hover_t = pyqtProperty(float, _get_hover_t, _set_hover_t)

    def set_action(
        self,
        headline: str,
        subline: str = "",
        score: float = 0.0,
        priority: str = "medium",
        icon_glyph: str = "→",
        icon_color: str = COLOR.accent_blue,
    ):
        self._headline = headline
        self._subline = subline
        self._score = score
        self._priority = priority
        self._icon_glyph = icon_glyph
        self._icon_color = icon_color
        self.update()

    def enterEvent(self, event):
        self._animate_hover(1.0)

    def leaveEvent(self, event):
        self._animate_hover(0.0)

    def _animate_hover(self, target: float):
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"hover_t", self)
        self._anim.setDuration(MOTION.fast)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(self._hover_t)
        self._anim.setEndValue(target)
        self._anim.start()

    def sizeHint(self) -> QSize:
        return QSize(400, SIZE.action_row_min_height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        ph, pv = SIZE.action_row_padding_h, SIZE.action_row_padding_v
        rect = QRectF(0, 0, w, h)

        # Hover background blend
        if self._hover_t > 0:
            bg = QColor(COLOR.bg_raised)
            bg.setAlpha(int(self._hover_t * 80))
            path = QPainterPath()
            path.addRoundedRect(rect, RADIUS.row, RADIUS.row)
            p.fillPath(path, QBrush(bg))

        # Icon square
        icon_size = SIZE.action_icon
        icon_rect = QRectF(ph, (h - icon_size) / 2, icon_size, icon_size)
        icon_path = QPainterPath()
        icon_path.addRoundedRect(icon_rect, SIZE.action_icon_radius, SIZE.action_icon_radius)
        icon_bg = QColor(self._icon_color)
        icon_bg.setAlpha(36)
        p.fillPath(icon_path, QBrush(icon_bg))
        p.setPen(QPen(QColor(self._icon_color)))
        f = QFont()
        f.setPointSize(14)
        p.setFont(f)
        p.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self._icon_glyph)

        # Text block
        text_x = ph + icon_size + SPACE.md
        score_w = 44
        text_w = w - text_x - score_w - ph

        p.setPen(QPen(QColor(COLOR.text_primary)))
        fh = QFont()
        fh.setPointSize(FONT.size_row_title)
        fh.setWeight(QFont.Weight.Medium)
        p.setFont(fh)
        headline_rect = QRectF(text_x, pv, text_w, h / 2 - pv / 2)
        p.drawText(headline_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                   self._headline)

        if self._subline:
            p.setPen(QPen(QColor(COLOR.text_tertiary)))
            fs = QFont()
            fs.setPointSize(FONT.size_row_subtitle)
            p.setFont(fs)
            sub_rect = QRectF(text_x, h / 2 + 2, text_w, h / 2 - pv)
            p.drawText(sub_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                       self._subline)

        # Score pill
        if self._score > 0:
            pc = QColor(_PRIORITY_COLORS.get(self._priority, COLOR.accent_blue))
            pill_rect = QRectF(w - score_w - ph + 4, (h - 20) / 2, score_w - 4, 20)
            pill_path = QPainterPath()
            pill_path.addRoundedRect(pill_rect, 10, 10)
            pill_bg = QColor(pc)
            pill_bg.setAlpha(36)
            p.fillPath(pill_path, QBrush(pill_bg))
            p.setPen(QPen(pc))
            fp = QFont()
            fp.setPointSize(FONT.size_badge)
            fp.setWeight(QFont.Weight.DemiBold)
            p.setFont(fp)
            p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, f"{self._score:.0f}")

        p.end()
