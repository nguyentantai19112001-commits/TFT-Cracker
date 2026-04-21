"""SituationalFrameStrip — 780×68 strip showing game_tag + frame sentence."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui.tokens import COLOR, FONT, RADIUS, SIZE, SPACE


_TAG_META: dict[str, tuple[str, str]] = {
    "winning": ("WIN STREAK",  COLOR.tag_winning),
    "stable":  ("STABLE",      COLOR.tag_stable),
    "losing":  ("LOSING",      COLOR.tag_losing),
    "salvage": ("SALVAGE",     COLOR.tag_salvage),
    "dying":   ("DANGER",      COLOR.tag_dying),
}


class SituationalFrameStrip(QWidget):
    """Dark glass strip with colored left-border accent keyed to game_tag."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._game_tag = "stable"
        self._ev_avg = 4.5
        self._frame_sentence = "On curve — standard play."
        self.setFixedHeight(SIZE.frame_strip_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def apply(self, game_tag: str, ev_avg: float, frame_sentence: str) -> None:
        self._game_tag = game_tag
        self._ev_avg = ev_avg
        self._frame_sentence = frame_sentence
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        label, accent_hex = _TAG_META.get(self._game_tag, ("STABLE", COLOR.tag_stable))
        accent = QColor(accent_hex)

        # Background — opaque solid fill
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.row, RADIUS.row)
        bg_c = QColor(COLOR.elev_1)
        bg_c.setAlpha(255)
        p.fillPath(bg_path, QBrush(bg_c))
        # Border stroke
        p.setPen(QPen(QColor(*COLOR.border_subtle_rgba), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0, 0, w, h).adjusted(0, 0, -1, -1), RADIUS.row, RADIUS.row)
        # Inner top highlight
        hl = QColor(*COLOR.inner_highlight_rgba)
        p.setPen(QPen(hl, 1))
        p.drawLine(RADIUS.row, 1, w - RADIUS.row, 1)

        # Left accent bar (4px)
        bar_w = 4
        bar_path = QPainterPath()
        bar_path.addRoundedRect(QRectF(0, 4, bar_w, h - 8), 2, 2)
        p.fillPath(bar_path, QBrush(accent))

        # Tag label: "WIN STREAK · EV ≈ 2.4"
        left_pad = bar_w + SPACE.lg
        tag_text = f"{label}  ·  EV ≈ {self._ev_avg:.1f}"

        p.setPen(QPen(accent))
        f_tag = QFont()
        f_tag.setPointSize(FONT.size_section_label)
        f_tag.setWeight(QFont.Weight.Bold)
        f_tag.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, FONT.letter_spacing_caps)
        p.setFont(f_tag)
        tag_rect = QRectF(left_pad, SPACE.sm, w - left_pad - SPACE.md, 18)
        p.drawText(tag_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, tag_text)

        # Frame sentence
        p.setPen(QPen(QColor(COLOR.text_secondary)))
        f_sent = QFont()
        f_sent.setPointSize(11)
        f_sent.setWeight(QFont.Weight.Medium)
        p.setFont(f_sent)
        sent_rect = QRectF(left_pad, 26, w - left_pad - SPACE.md, h - 30)
        p.drawText(sent_rect,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._frame_sentence)

        p.end()
