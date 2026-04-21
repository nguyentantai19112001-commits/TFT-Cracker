"""Attach hover animation to any widget that exposes a `hover_t` pyqtProperty."""
from __future__ import annotations
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget

from ui.tokens import MOTION


def attach_hover_anim(widget: QWidget, duration: int = MOTION.fast) -> None:
    """Patch widget so enter/leave events drive the `hover_t` property [0→1]."""
    _anim_ref: list[QPropertyAnimation] = []

    def _animate(target: float):
        if _anim_ref:
            _anim_ref[0].stop()
        anim = QPropertyAnimation(widget, b"hover_t", widget)
        anim.setDuration(duration)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(widget.hover_t)
        anim.setEndValue(target)
        anim.start()
        if _anim_ref:
            _anim_ref[0] = anim
        else:
            _anim_ref.append(anim)

    _orig_enter = widget.enterEvent
    _orig_leave = widget.leaveEvent

    def _enter(event):
        _orig_enter(event)
        _animate(1.0)

    def _leave(event):
        _orig_leave(event)
        _animate(0.0)

    widget.enterEvent = _enter  # type: ignore[method-assign]
    widget.leaveEvent = _leave  # type: ignore[method-assign]
