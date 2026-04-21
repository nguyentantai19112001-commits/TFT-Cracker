"""Panel-level animation helpers."""
from __future__ import annotations
from PyQt6.QtCore import (
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QPoint, pyqtProperty,
)
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget

from ui.tokens import MOTION


def panel_entrance(widget: QWidget) -> QParallelAnimationGroup:
    """Fade + slide-up entrance animation. Returns the group (not started)."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)

    fade = QPropertyAnimation(effect, b"opacity", widget)
    fade.setDuration(MOTION.slow)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)

    slide = QPropertyAnimation(widget, b"pos", widget)
    slide.setDuration(MOTION.slow)
    slide.setEasingCurve(QEasingCurve.Type.OutCubic)
    pos = widget.pos()
    slide.setStartValue(QPoint(pos.x(), pos.y() + 16))
    slide.setEndValue(pos)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(fade)
    group.addAnimation(slide)
    return group


def fade_in(widget: QWidget, duration: int = MOTION.medium) -> QPropertyAnimation:
    effect = _ensure_opacity_effect(widget)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    return anim


def fade_out(widget: QWidget, duration: int = MOTION.medium) -> QPropertyAnimation:
    effect = _ensure_opacity_effect(widget)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    return anim


def _ensure_opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect:
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    return effect
