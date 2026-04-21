"""Item icon widget — 20px with gradient fallback by category."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QPixmap, QLinearGradient,
)
from PyQt6.QtWidgets import QWidget

from ui.tokens import COLOR, SIZE, RADIUS


_CATEGORY_GRADIENTS: dict[str, tuple[str, str]] = {
    "ad":    (COLOR.item_ad_from,    COLOR.item_ad_to),
    "ap":    (COLOR.item_ap_from,    COLOR.item_ap_to),
    "mana":  (COLOR.item_mana_from,  COLOR.item_mana_to),
    "as":    (COLOR.item_as_from,    COLOR.item_as_to),
    "armor": (COLOR.item_armor_from, COLOR.item_armor_to),
    "hp":    (COLOR.item_hp_from,    COLOR.item_hp_to),
}
_DEFAULT_GRADIENT = (_CATEGORY_GRADIENTS["ap"])


class ItemIcon(QWidget):
    """20×20 item icon with sprite or category-tinted gradient fallback."""

    def __init__(
        self,
        api_name: str = "",
        category: str = "ap",
        size: int = SIZE.icon_item,
        parent=None,
    ):
        super().__init__(parent)
        self._api_name = api_name
        self._category = category
        self._pixmap: QPixmap | None = None
        self.setFixedSize(size, size)
        if api_name:
            self._try_load()

    def set_item(self, api_name: str, category: str = "ap"):
        self._api_name = api_name
        self._category = category
        self._pixmap = None
        self._try_load()
        self.update()

    def _try_load(self):
        try:
            from engine.sprites.cache import SpriteCache
            self._pixmap = SpriteCache().get(self._api_name, self.width())
        except Exception:
            self._pixmap = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(0.5, 0.5, w - 1, h - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS.item_icon, RADIUS.item_icon)

        if self._pixmap and not self._pixmap.isNull():
            p.setClipPath(path)
            p.drawPixmap(0, 0, w, h, self._pixmap)
            p.setClipping(False)
        else:
            from_c, to_c = _CATEGORY_GRADIENTS.get(self._category, _DEFAULT_GRADIENT)
            g = QLinearGradient(rect.topLeft(), rect.bottomRight())
            c0 = QColor(from_c)
            c0.setAlpha(180)
            g.setColorAt(0, c0)
            g.setColorAt(1, QColor(to_c))
            p.fillPath(path, QBrush(g))

        border = QColor(255, 255, 255, 30)
        p.setPen(QPen(border, 1))
        p.drawPath(path)
        p.end()
