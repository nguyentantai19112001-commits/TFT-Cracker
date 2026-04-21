"""Action row widget — icon + two-line text + score badge."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QSize, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, FONT, SIZE, SPACE, RADIUS, MOTION


_PRIORITY_COLORS = {
    "high":   (COLOR.accent_pink,   COLOR.accent_purple),
    "medium": (COLOR.accent_gold,   COLOR.accent_pink),
    "low":    (COLOR.accent_blue,   COLOR.accent_purple),
}


class ActionRow(QWidget):
    """Painted row: left icon square, headline + sub-line, right score badge."""

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

        # Row background — always solid
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, RADIUS.row, RADIUS.row)
        bg = QColor(COLOR.elev_2)
        bg.setAlpha(255)
        p.fillPath(bg_path, QBrush(bg))
        # Hover brightening
        if self._hover_t > 0:
            hover_c = QColor(255, 255, 255)
            hover_c.setAlpha(int(self._hover_t * 15))
            p.fillPath(bg_path, QBrush(hover_c))
        # Border
        p.setPen(QPen(QColor(*COLOR.border_medium_rgba), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), RADIUS.row, RADIUS.row)
        # Inner top highlight
        hl = QColor(*COLOR.inner_highlight_rgba)
        p.setPen(QPen(hl, 1))
        p.drawLine(RADIUS.row, 1, w - RADIUS.row, 1)

        # Icon square — soft glow behind it
        icon_size = SIZE.action_icon
        icon_rect = QRectF(ph, (h - icon_size) / 2, icon_size, icon_size)
        icon_path = QPainterPath()
        icon_path.addRoundedRect(icon_rect, SIZE.action_icon_radius, SIZE.action_icon_radius)

        # Soft glow behind icon
        glow_c = QColor(self._icon_color); glow_c.setAlpha(20 + int(self._hover_t * 20))
        p.fillPath(icon_path, QBrush(glow_c))

        # Icon tile gradient
        tile_g = QLinearGradient(icon_rect.topLeft(), icon_rect.bottomRight())
        c1 = QColor(self._icon_color); c1.setAlpha(60)
        c2 = QColor(self._icon_color); c2.setAlpha(30)
        tile_g.setColorAt(0, c1)
        tile_g.setColorAt(1, c2)
        p.fillPath(icon_path, QBrush(tile_g))

        p.setPen(QPen(QColor(self._icon_color)))
        f = QFont()
        f.setPointSize(14)
        p.setFont(f)
        p.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self._icon_glyph)

        # Text block
        badge_w = 52
        text_x = ph + icon_size + SPACE.md
        text_w = w - text_x - badge_w - ph

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

        # Score badge — 48×32, scaled up 5% on hover
        if self._score > 0:
            scale = 1.0 + self._hover_t * 0.05
            bw, bh = 48 * scale, 32 * scale
            bx = w - badge_w - ph + (badge_w - bw) / 2
            by = (h - bh) / 2

            badge_rect = QRectF(bx, by, bw, bh)
            badge_path = QPainterPath()
            badge_path.addRoundedRect(badge_rect, 10 * scale, 10 * scale)

            c1_hex, c2_hex = _PRIORITY_COLORS.get(self._priority,
                                                    (COLOR.accent_blue, COLOR.accent_purple))
            bg_g = QLinearGradient(badge_rect.topLeft(), badge_rect.bottomRight())
            bc1 = QColor(c1_hex); bc1.setAlpha(int(60 + self._hover_t * 40))
            bc2 = QColor(c2_hex); bc2.setAlpha(int(40 + self._hover_t * 30))
            bg_g.setColorAt(0, bc1)
            bg_g.setColorAt(1, bc2)
            p.fillPath(badge_path, QBrush(bg_g))

            # Inner highlight at top
            hl = QColor(255, 255, 255); hl.setAlpha(50)
            p.setPen(QPen(hl, 1))
            p.drawLine(int(bx + 8), int(by + 1), int(bx + bw - 8), int(by + 1))

            # Inner shadow at bottom
            sh = QColor(0, 0, 0); sh.setAlpha(40)
            p.setPen(QPen(sh, 1))
            p.drawLine(int(bx + 8), int(by + bh - 2), int(bx + bw - 8), int(by + bh - 2))

            # Score number
            p.setPen(QPen(QColor(COLOR.text_primary)))
            fp = QFont("JetBrains Mono")
            fp.setPointSize(int(FONT.size_badge + 2 + self._hover_t))
            fp.setWeight(QFont.Weight.ExtraBold)
            p.setFont(fp)
            num_rect = QRectF(bx, by, bw, bh * 0.68)
            p.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, f"{self._score:.0f}")

            # "pts" micro label
            p.setPen(QPen(QColor(COLOR.text_muted)))
            pts_f = QFont()
            pts_f.setPointSize(7)
            p.setFont(pts_f)
            pts_rect = QRectF(bx, by + bh * 0.62, bw, bh * 0.38)
            p.drawText(pts_rect, Qt.AlignmentFlag.AlignCenter, "pts")

        p.end()
