"""Visual effects helpers — shadow, glow."""
from __future__ import annotations
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget
from PyQt6.QtGui import QColor


def apply_shadow(widget: QWidget, spec: dict) -> QGraphicsDropShadowEffect:
    """Apply a QGraphicsDropShadowEffect from a SHADOW spec dict."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(spec["blur"])
    eff.setOffset(0, spec["dy"])
    c = QColor(spec["color"])
    c.setAlpha(spec["alpha"])
    eff.setColor(c)
    widget.setGraphicsEffect(eff)
    return eff
