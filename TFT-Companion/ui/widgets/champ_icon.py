"""Champion icon widget — hero (52px) and tiny (20px) variants."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QPixmap, QFont,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, SIZE, FONT, RADIUS


_COST_COLORS: dict[int, str] = {
    1: COLOR.cost_1,
    2: COLOR.cost_2,
    3: COLOR.cost_3,
    4: COLOR.cost_4,
    5: COLOR.cost_5,
}


class ChampIcon(QWidget):
    """Rounded champion portrait with cost-colored border + optional star badge."""

    def __init__(
        self,
        api_name: str = "",
        cost: int = 1,
        stars: int = 1,
        size: int = SIZE.hero_champ,
        radius: int = SIZE.hero_champ_radius,
        parent=None,
    ):
        super().__init__(parent)
        self._api_name = api_name
        self._cost = cost
        self._stars = stars
        self._radius = radius
        self._pixmap: QPixmap | None = None
        self.setFixedSize(size, size)

    def set_champion(self, api_name: str, cost: int, stars: int = 1):
        self._api_name = api_name
        self._cost = cost
        self._stars = stars
        self._pixmap = None
        self._try_load_pixmap()
        self.update()

    def _try_load_pixmap(self):
        try:
            from engine.sprites.cache import SpriteCache
            self._pixmap = SpriteCache().get(self._api_name, self.width())
        except Exception:
            self._pixmap = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        rect = QRectF(1, 1, w - 2, h - 2)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        p.setClipPath(path)

        if self._pixmap and not self._pixmap.isNull():
            p.drawPixmap(0, 0, w, h, self._pixmap)
        else:
            p.fillPath(path, QBrush(QColor(COLOR.bg_raised)))
            p.setPen(QPen(QColor(COLOR.text_muted)))
            f = QFont()
            f.setPointSize(FONT.size_body_small)
            p.setFont(f)
            p.drawText(
                QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                self._api_name[:3] or "?",
            )

        p.setClipping(False)

        border_color = QColor(_COST_COLORS.get(self._cost, COLOR.cost_1))
        p.setPen(QPen(border_color, 2))
        p.drawRoundedRect(rect, self._radius, self._radius)

        if self._stars > 1:
            self._draw_stars(p, w, h)
        p.end()

    def _draw_stars(self, p: QPainter, w: int, h: int):
        p.setPen(QPen(QColor(COLOR.accent_gold)))
        f = QFont()
        f.setPointSize(7)
        p.setFont(f)
        stars_str = "★" * min(self._stars, 3)
        p.drawText(
            QRectF(0, h - 12, w, 12), Qt.AlignmentFlag.AlignCenter, stars_str,
        )


class TinyChampIcon(ChampIcon):
    """20px variant used in inline lists."""

    def __init__(self, api_name: str = "", cost: int = 1, parent=None):
        super().__init__(
            api_name=api_name,
            cost=cost,
            stars=1,
            size=SIZE.icon_champ_tiny,
            radius=4,
            parent=parent,
        )
