"""Hero section — typographic verdict + champion portrait + carry icons."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath, QLinearGradient, QFont,
)
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

from ui.tokens import COLOR, FONT, SPACE, RADIUS, SIZE
from ui.widgets.champ_icon import ChampIcon, TinyChampIcon


_VERDICT_STYLES: dict[str, dict] = {
    "strong_buy":  {"label": "Strong Buy",  "color": COLOR.accent_green,  "glyph": "↑↑"},
    "buy":         {"label": "Buy",          "color": COLOR.accent_blue,   "glyph": "↑"},
    "hold":        {"label": "Hold",         "color": COLOR.accent_gold,   "glyph": "→"},
    "sell":        {"label": "Sell",         "color": COLOR.accent_red,    "glyph": "↓"},
    "transition":  {"label": "Transition",   "color": COLOR.accent_purple, "glyph": "⇄"},
}


class VerdictBadge(QWidget):
    """Typographic verdict headline — large gradient verb, no button shape."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self._verdict = "hold"
        self._subline = ""
        self.setMinimumHeight(62)

    def set_verdict(self, verdict: str, subline: str = ""):
        self._verdict = verdict
        self._subline = subline
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(400, 62)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        style = _VERDICT_STYLES.get(self._verdict, _VERDICT_STYLES["hold"])

        # Directional glyph — muted, smaller
        glyph_color = QColor(style["color"])
        glyph_color.setAlpha(140)
        gf = QFont("Orbitron")
        gf.setPointSize(15)
        gf.setWeight(QFont.Weight.Medium)
        p.setFont(gf)
        p.setPen(QPen(glyph_color))
        glyph_h = int(h * 0.58)
        p.drawText(QRectF(0, 0, 32, glyph_h),
                   Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                   style["glyph"])

        # Main verb — gradient fill via QPainterPath
        verb = style["label"]
        vf = QFont("Orbitron")
        vf.setPointSize(FONT.size_verdict_headline)
        vf.setWeight(QFont.Weight.ExtraBold)
        vf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.6)
        p.setFont(vf)
        fm = p.fontMetrics()

        verb_x = 36
        verb_y = int(h * 0.58)
        verb_w = fm.horizontalAdvance(verb)

        path = QPainterPath()
        path.addText(verb_x, verb_y, vf, verb)

        grad = QLinearGradient(verb_x, 0, verb_x + verb_w, 0)
        grad.setColorAt(0.0, QColor(COLOR.accent_gold))
        grad.setColorAt(0.5, QColor(COLOR.accent_pink))
        grad.setColorAt(1.0, QColor(COLOR.accent_purple))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(path, QBrush(grad))

        # Sub-line
        if self._subline:
            p.setPen(QPen(QColor(COLOR.text_secondary)))
            sf = QFont()
            sf.setPointSize(FONT.size_verdict_subtitle)
            sf.setWeight(QFont.Weight.Medium)
            p.setFont(sf)
            p.drawText(QRectF(0, h * 0.64, w, h * 0.36),
                       Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                       self._subline)

        p.end()


class HeroSection(QWidget):
    """Top verdict section: VerdictBadge + main champ + carry strip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, SPACE.md, SPACE.xl, SPACE.md)
        layout.setSpacing(SPACE.md)

        self.verdict_badge = VerdictBadge()
        layout.addWidget(self.verdict_badge)

        champ_row = QWidget()
        champ_layout = QHBoxLayout(champ_row)
        champ_layout.setContentsMargins(0, 0, 0, 0)
        champ_layout.setSpacing(SPACE.md)

        self.main_champ = ChampIcon(size=SIZE.hero_champ, radius=SIZE.hero_champ_radius)
        champ_layout.addWidget(self.main_champ)

        info_col = QWidget()
        info_layout = QVBoxLayout(info_col)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(SPACE.xs)

        self.champ_name = QLabel("—")
        self.champ_name.setStyleSheet(
            f"color: {COLOR.text_primary}; font-size: {FONT.size_row_title}px;"
            f"font-weight: {FONT.weight_semibold};"
        )
        self.champ_detail = QLabel("")
        self.champ_detail.setStyleSheet(
            f"color: {COLOR.text_tertiary}; font-size: {FONT.size_body_small}px;"
        )
        info_layout.addWidget(self.champ_name)
        info_layout.addWidget(self.champ_detail)
        info_layout.addStretch()
        champ_layout.addWidget(info_col, 1)
        layout.addWidget(champ_row)

        self._carry_strip = QHBoxLayout()
        self._carry_strip.setSpacing(SPACE.xs)
        self._carry_strip.addStretch()
        strip_widget = QWidget()
        strip_widget.setLayout(self._carry_strip)
        layout.addWidget(strip_widget)

        self._carry_icons: list[TinyChampIcon] = []

    def apply(self, verdict: str, champ_name: str, champ_api: str, cost: int,
              carries: list[dict], subline: str = ""):
        self.verdict_badge.set_verdict(verdict, subline)
        self.main_champ.set_champion(champ_api, cost)
        self.champ_name.setText(champ_name)
        self.champ_detail.setText(f"Cost {cost}")
        self._set_carries(carries)

    def _set_carries(self, carries: list[dict]):
        for icon in self._carry_icons:
            self._carry_strip.removeWidget(icon)
            icon.deleteLater()
        self._carry_icons.clear()
        for c in carries[:6]:
            icon = TinyChampIcon(c.get("api_name", ""), c.get("cost", 1))
            self._carry_icons.append(icon)
            self._carry_strip.insertWidget(self._carry_strip.count() - 1, icon)
