"""Runtime sprite cache. Lazy QPixmap loading with memory cache."""
from __future__ import annotations
import json
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from loguru import logger

from .paths import manifest_path, sprite_for


class SpriteCache:
    """App-wide pixmap cache, indexed by apiName. Singleton."""

    _instance: Optional["SpriteCache"] = None

    def __init__(self) -> None:
        self._pixmaps: dict[str, QPixmap] = {}
        self._manifest = self._load_manifest()
        self._missing: Optional[QPixmap] = None

    @classmethod
    def instance(cls) -> "SpriteCache":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, api_name: str, size: int = 20) -> QPixmap:
        """Return a scaled QPixmap for `api_name`. Never returns None or null."""
        key = f"{api_name}@{size}"
        if key in self._pixmaps:
            return self._pixmaps[key]

        path = sprite_for(api_name)
        if not path.exists():
            logger.debug(f"sprite missing: {api_name}")
            pm = self._missing_pixmap(size)
        else:
            pm = QPixmap(str(path))
            if pm.isNull():
                logger.warning(f"sprite corrupt: {path}")
                pm = self._missing_pixmap(size)
            else:
                pm = pm.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        self._pixmaps[key] = pm
        return pm

    def has(self, api_name: str) -> bool:
        return sprite_for(api_name).exists()

    def _load_manifest(self) -> dict:
        mp = manifest_path()
        if not mp.exists():
            return {}
        try:
            return json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _missing_pixmap(self, size: int) -> QPixmap:
        """Gray square with '?' — shown when a sprite isn't in the cache."""
        if self._missing is None or self._missing.width() != size:
            from PyQt6.QtGui import QPainter, QColor, QFont, QPen
            pm = QPixmap(size, size)
            pm.fill(QColor(60, 55, 80))
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            p.setPen(QPen(QColor(160, 150, 180)))
            f = QFont()
            f.setPointSize(max(8, size // 3))
            f.setBold(True)
            p.setFont(f)
            p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "?")
            p.end()
            self._missing = pm
        return self._missing
