"""AuroraPanel — the main scrollable content panel."""
from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QSizePolicy,
)

from ui.tokens import COLOR, RADIUS, SPACE, SIZE
from ui.chrome.title_bar import TitleBar
from ui.widgets.aurora_backdrop import AuroraBackdrop
from ui.widgets.warning_block import WarningBlock
from ui.sections.hero_section import HeroSection
from ui.sections.status_pills import StatusPills
from ui.sections.prob_section import ProbSection
from ui.sections.target_comp import TargetComp
from ui.sections.actions_list import ActionsList
from ui.sections.carries_section import CarriesSection
from ui.sections.augment_preview import AugmentPreview
from ui.sections.footer import Footer


class _PanelBody(QWidget):
    """Painted glass panel body — rounded rect + subtle border."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(0, 0, w, h)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS.panel, RADIUS.panel)

        r, g, b, a = COLOR.bg_panel_rgba
        p.fillPath(path, QBrush(QColor(r, g, b, a)))

        border = QColor(*COLOR.border_subtle_rgba)
        p.setPen(QPen(border, 1))
        p.drawPath(path)
        p.end()


class AuroraPanel(QWidget):
    """Full overlay panel: title bar + scrollable content sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(SIZE.panel_width)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Backdrop blob layer (absolute positioned child — sized in resizeEvent)
        self._backdrop = AuroraBackdrop(self)
        self._backdrop.lower()

        # Glass body
        self._body = _PanelBody(self)
        self._body.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar()
        body_layout.addWidget(self.title_bar)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollArea > QWidget > QWidget { background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
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
        body_layout.addWidget(scroll, 1)

        self.footer = Footer()
        body_layout.addWidget(self.footer)

        root_layout.addWidget(self._body)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._backdrop.setGeometry(0, 0, self.width(), self.height())

    # --- Public apply methods (wired by ui/bindings.py) ---

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
