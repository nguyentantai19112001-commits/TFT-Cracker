"""AuroraPanel — the main overlay panel.

Paints its own background (blobs + glass rect) so transparency works
correctly with the frameless window. No separate backdrop widget needed.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QPainterPath,
    QRadialGradient, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame,
)

from ui.tokens import COLOR, RADIUS, SPACE, SIZE
from ui.chrome.title_bar import TitleBar
from ui.widgets.warning_block import WarningBlock
from ui.sections.hero_section import HeroSection
from ui.sections.status_pills import StatusPills
from ui.sections.prob_section import ProbSection
from ui.sections.target_comp import TargetComp
from ui.sections.actions_list import ActionsList
from ui.sections.carries_section import CarriesSection
from ui.sections.augment_preview import AugmentPreview
from ui.sections.footer import Footer


_BLOBS = [
    (0.15, 0.10, 0.55, COLOR.accent_pink,   28),
    (0.85, 0.30, 0.50, COLOR.accent_blue,   22),
    (0.50, 0.80, 0.60, COLOR.accent_purple, 18),
]


class AuroraPanel(QWidget):
    """Full overlay panel — paints blobs + glass rect in its own paintEvent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setFixedWidth(SIZE.panel_width)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.title_bar = TitleBar()
        root.addWidget(self.title_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget"
            "{ background: transparent; border: none; }"
        )

        content = QWidget()
        content.setAutoFillBackground(False)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, SPACE.sm, 0, SPACE.lg)
        content_layout.setSpacing(SPACE.md)

        self.warning = WarningBlock()
        self.warning.setVisible(False)
        content_layout.addWidget(self.warning)

        self.hero = HeroSection()
        content_layout.addWidget(self.hero)

        self.status_pills = StatusPills()
        content_layout.addWidget(self.status_pills)

        self.prob = ProbSection()
        content_layout.addWidget(self.prob)

        self.target_comp = TargetComp()
        content_layout.addWidget(self.target_comp)

        self.actions = ActionsList()
        content_layout.addWidget(self.actions)

        self.carries = CarriesSection()
        content_layout.addWidget(self.carries)

        self.augments = AugmentPreview()
        content_layout.addWidget(self.augments)

        content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.footer = Footer()
        root.addWidget(self.footer)

    # ── Paint: blobs then glass ──────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Aurora blobs
        for cx_f, cy_f, r_f, color_hex, alpha in _BLOBS:
            cx = w * cx_f
            cy = h * cy_f
            radius = max(w, h) * r_f
            grad = QRadialGradient(QPointF(cx, cy), radius)
            c_center = QColor(color_hex)
            c_center.setAlpha(alpha)
            c_edge = QColor(color_hex)
            c_edge.setAlpha(0)
            grad.setColorAt(0, c_center)
            grad.setColorAt(1, c_edge)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        # Glass panel
        rect = QRectF(0, 0, w, h)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS.panel, RADIUS.panel)
        r, g, b, a = COLOR.bg_panel_rgba
        p.fillPath(path, QBrush(QColor(r, g, b, a)))
        border = QColor(*COLOR.border_subtle_rgba)
        p.setPen(QPen(border, 1))
        p.drawPath(path)
        p.end()

    # ── Public apply methods ─────────────────────────────────────────────────

    def apply_warning(self, message: str, visible: bool = True):
        self.warning.set_message(message)
        self.warning.setVisible(visible and bool(message))

    def apply_verdict(self, verdict: str, champ_name: str, champ_api: str,
                      cost: int, carries: list[dict]):
        self.hero.apply(verdict, champ_name, champ_api, cost, carries)

    def apply_econ(self, gold: int, level: int, streak: int, interest: int):
        self.status_pills.apply(gold, level, streak, interest)

    def apply_probability(self, prob: float, label: str = "", sublabel: str = ""):
        self.prob.apply(prob, label=label, sublabel=sublabel)

    def apply_comp(self, traits: list[dict], champions: list[dict]):
        self.target_comp.apply(traits, champions)

    def apply_actions(self, actions: list[dict]):
        self.actions.apply(actions)

    def apply_carries(self, carries: list[dict]):
        self.carries.apply(carries)

    def apply_augments(self, augments: list[dict]):
        self.augments.apply(augments)

    def apply_latency(self, ms: int | None):
        self.footer.set_latency(ms)

    def apply_stage(self, stage: str):
        self.title_bar.set_stage(stage)
