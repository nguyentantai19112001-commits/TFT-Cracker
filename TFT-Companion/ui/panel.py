"""AuroraPanel — v3 main overlay panel (780px).

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
from ui.sections.prob_section import ProbSection
from ui.sections.comp_option_row import CompOptionRow
from ui.sections.actions_list import ActionsList
from ui.sections.carries_section import CarriesSection
from ui.widgets.holder_hint_row import HolderHintRow
from ui.sections.augment_preview_v3 import AugmentPreviewV3


_BLOBS = [
    (0.15, 0.10, 0.55, COLOR.accent_pink,   28),
    (0.85, 0.30, 0.50, COLOR.accent_blue,   22),
    (0.50, 0.80, 0.60, COLOR.accent_purple, 18),
]


_FRAME_SUBLINE: dict[str, str] = {
    "winning": "Winning — press and buy levels",
    "stable":  "Stable — stay consistent",
    "losing":  "Losing — econ sack or pivot",
    "salvage": "Salvage — cut losses, pivot fast",
    "dying":   "Dying — go 8 and pray",
}


class AuroraPanel(QWidget):
    """Full v3 overlay panel — 620px, 7 sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setFixedWidth(SIZE.panel_width)

        # State for merging frame tag into verdict subline
        self._frame_tag = "stable"
        self._frame_sentence = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Title bar
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
        cl = QVBoxLayout(content)
        cl.setContentsMargins(SPACE.sm, SPACE.sm, SPACE.sm, SPACE.lg)
        cl.setSpacing(SPACE.md)

        # Warning block (floats above content)
        self.warning = WarningBlock()
        self.warning.setVisible(False)
        cl.addWidget(self.warning)

        # 2. Verdict hero (frame tag merged into subline)
        self.hero = HeroSection()
        cl.addWidget(self.hero)

        # 3. Roll probability (conditionally shown)
        self.prob = ProbSection()
        cl.addWidget(self.prob)

        # 4. Target comp — 2 cards
        self.comp_options = CompOptionRow()
        cl.addWidget(self.comp_options)

        # 5. Top recommended action
        self.actions = ActionsList()
        cl.addWidget(self.actions)

        # 6. Carry items + holder hint
        self.carries = CarriesSection()
        cl.addWidget(self.carries)

        self.holder_hint = HolderHintRow()
        cl.addWidget(self.holder_hint)

        # 7. Priority augments
        self.augments_v3 = AugmentPreviewV3()
        cl.addWidget(self.augments_v3)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    # ── Paint: blobs then glass ──────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

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

        rect = QRectF(0, 0, w, h)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS.panel, RADIUS.panel)
        r, g, b, a = COLOR.bg_panel_rgba
        p.fillPath(path, QBrush(QColor(r, g, b, a)))
        border = QColor(*COLOR.border_subtle_rgba)
        p.setPen(QPen(border, 1))
        p.drawPath(path)
        p.end()

    # ── Public apply methods — v3 ─────────────────────────────────────────────

    def apply_warning(self, message: str, visible: bool = True):
        self.warning.set_message(message)
        self.warning.setVisible(visible and bool(message))

    def apply_frame(self, game_tag: str, ev_avg: float, frame_sentence: str) -> None:
        """Store frame context — merged into verdict subline on next apply_verdict."""
        self._frame_tag = game_tag
        self._frame_sentence = (
            frame_sentence or _FRAME_SUBLINE.get(game_tag, "")
        )

    def apply_verdict(self, verdict: str, champ_name: str, champ_api: str,
                      cost: int, carries: list[dict]):
        """Section 2 — Verdict hero; subline carries the situational frame."""
        subline = self._frame_sentence or _FRAME_SUBLINE.get(self._frame_tag, "")
        self.hero.apply(verdict, champ_name, champ_api, cost, carries, subline=subline)

    def apply_econ(self, gold: int, level: int, streak: int, interest: int):
        """No-op — econ row removed in density pass."""
        pass

    def apply_probability(self, prob: float, label: str = "", sublabel: str = ""):
        """Section 5 — Roll probability."""
        self.prob.apply(prob, label=label, sublabel=sublabel)

    def apply_comp_options(self, top_comp: dict, alternates: list[dict]) -> None:
        """Section 6 — Target comp 3-card row."""
        self.comp_options.apply(top_comp, alternates)

    def apply_actions(self, actions: list[dict]):
        """Section 7 — Recommended actions (3 rows)."""
        self.actions.apply(actions)

    def apply_carries(self, carries: list[dict]):
        """Section 8 — Carry items (CarriesSection, upgrading to v3 rows in future pass)."""
        self.carries.apply(carries)

    def apply_holders(self, result) -> None:
        """Section 8b — Holder matrix: show one hint (highest-conflict or best advice)."""
        hint = ""
        if result.conflicts:
            hint = f"HOLDER: {result.conflicts[0]}"
        elif result.assignments:
            for a in result.assignments:
                if not a.current_holding_good and a.stage_role in ("primary", "secondary"):
                    items = " / ".join(a.preferred_items_given_components[:2])
                    hint = f"HOLDER: {a.unit_display} wants {items or a.preferred_family}"
                    break
        self.holder_hint.apply_hint(hint)

    def apply_augments_v3(
        self,
        silver: float = 0.28,
        gold: float = 0.62,
        prismatic: float = 0.10,
        conditional_text: str = "",
        augment_recs: list[dict] | None = None,
    ) -> None:
        """Section 9 — Priority augments with tier bar + rec cards."""
        self.augments_v3.apply(silver, gold, prismatic, conditional_text, augment_recs)

    def apply_latency(self, ms: int | None):
        """No-op — footer removed in density pass."""
        pass

    def apply_stage(self, stage: str):
        self.title_bar.set_stage(stage)

    # ── Legacy shims (keep bindings.py working during transition) ─────────────

    def apply_comp(self, traits: list[dict], champions: list[dict]):
        """Legacy: route to CompOptionRow with minimal data."""
        pass  # v3 uses apply_comp_options; old path no longer primary

    def apply_augments(self, augments: list[dict]):
        """Legacy: augments list without tier data — show name/tier only."""
        recs = [
            {"display_name": a.get("name", "?"), "tier": a.get("tier", "gold"),
             "fit_score": 0.5, "why": ""}
            for a in augments
        ]
        self.augments_v3.apply(augment_recs=recs)
