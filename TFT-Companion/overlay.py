"""Augie overlay widget — premium glass co-pilot panel.

Frameless, translucent, always-on-top. Nested glass cards, multi-color outer
aura, breathing indicator, staggered content fade-in, Windows acrylic blur
(via ctypes, graceful fallback).

Reactive to pipeline events (all called from Qt main thread via queued signals):
    reset()                   — idle waiting state
    set_extracting()          — vision in flight; shows thinking dots
    set_extracted(state)      — header + status row update
    set_verdict(text)         — big one-liner fades in
    set_reasoning(text)       — body text fades in
    set_final(rec, meta, …)   — chips + suggestions + warning finalize
    set_error(text)           — failure state
"""

from __future__ import annotations

import ctypes
import math
from ctypes.wintypes import HWND
from typing import List, Optional

from PyQt6.QtCore import (
    QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QTimer, Qt,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFontDatabase, QLinearGradient, QPainter, QPainterPath,
    QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)


# ---------- design tokens ----------

# Card fill — semi-transparent so the aura bleeds in subtly, opaque enough
# for body text to stay legible over any game background.
CARD_FILL_RGBA   = (14, 16, 26, 225)
GLASS_TINT_RGBA  = (14, 16, 26, 200)          # used by acrylic fallback
BORDER_COOL      = "rgba(120, 150, 240, 0.28)"
DIVIDER          = "rgba(255, 255, 255, 0.08)"

# Sub-card tints (nested verdict card, suggestion rows, warning block)
SUBCARD_FILL     = "rgba(255, 255, 255, 0.035)"
SUBCARD_BORDER   = "rgba(255, 255, 255, 0.07)"
WARN_FILL        = "rgba(255, 165, 48, 0.08)"
WARN_BORDER      = "rgba(255, 175, 60, 0.35)"
WARN_ACCENT      = "#FFB24A"

TEXT_PRIMARY     = "#F4F4F8"
TEXT_SECOND      = "#A8A8B5"
TEXT_MUTED       = "#6A6A76"
TEXT_DIM         = "#50505A"

SEV_RED          = "#FF5C52"
SEV_AMBER        = "#FFB020"
SEV_GREEN        = "#32D74B"
SEV_INDIGO       = "#8B88FF"
SEV_CYAN         = "#5BCCFF"
SEV_GRAY         = "#7E7E86"

FONT_STACK       = "'Inter', 'Segoe UI Variable', 'Segoe UI', sans-serif"
FONT_MONO        = "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace"


SEVERITY_MAP = {
    "HIGH": SEV_AMBER, "MEDIUM": SEV_CYAN, "LOW": SEV_GREEN,
    "CRITICAL": SEV_RED, "BEHIND": SEV_AMBER, "ON_PACE": SEV_CYAN, "AHEAD": SEV_GREEN,
    "ROLL_DOWN": SEV_RED, "LEVEL_UP": SEV_AMBER, "HOLD_ECON": SEV_INDIGO,
    "COMMIT_DIRECTION": SEV_INDIGO, "PLAN_GOD_PICK": SEV_INDIGO,
    "SCOUT": SEV_CYAN, "POSITION": SEV_INDIGO, "OTHER": SEV_GRAY,
    "HIGH PRIORITY": SEV_AMBER, "OPTIONAL": SEV_GRAY,
}

GLOWING_SEVERITIES = {"HIGH", "CRITICAL", "ROLL_DOWN", "HIGH PRIORITY"}


def _sev_color(text: str) -> str:
    return SEVERITY_MAP.get(text.upper(), SEV_GRAY)


# ---------- Windows blur-behind ----------

def _enable_win_acrylic(hwnd: int) -> bool:
    try:
        user32 = ctypes.windll.user32
        if not hasattr(user32, "SetWindowCompositionAttribute"):
            return False

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.POINTER(ACCENT_POLICY)),
                ("SizeOfData", ctypes.c_size_t),
            ]

        accent = ACCENT_POLICY()
        accent.AccentState = 4
        accent.AccentFlags = 2
        r, g, b, a = GLASS_TINT_RGBA
        accent.GradientColor = (a << 24) | (b << 16) | (g << 8) | r

        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.pointer(accent)

        res = user32.SetWindowCompositionAttribute(HWND(hwnd), ctypes.pointer(data))
        if res == 0:
            accent.AccentState = 3
            res = user32.SetWindowCompositionAttribute(HWND(hwnd), ctypes.pointer(data))
        return bool(res)
    except Exception:
        return False


# ---------- chip with glow ----------

class Chip(QLabel):
    """Pill label with a tinted border. Urgent severities get a bolder border."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text.upper(), parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._color = SEV_GRAY
        self.set_severity(text)

    def set_severity(self, severity_text: str) -> None:
        self._color = _sev_color(severity_text)
        self.setText(severity_text.upper())
        # Urgent severities get a thicker border instead of an animated glow.
        # QGraphicsEffects are unreliable on frameless translucent windows.
        border = "2px" if severity_text.upper() in GLOWING_SEVERITIES else "1px"
        self.setStyleSheet(f"""
            QLabel {{
                color: {self._color};
                background-color: rgba(255, 255, 255, 0.05);
                border: {border} solid {self._color};
                border-radius: 11px;
                padding: 4px 12px;
                font-family: {FONT_STACK};
                font-size: 9pt;
                font-weight: 700;
                letter-spacing: 0.1em;
            }}
        """)


# ---------- breathing dot ----------

class BreathingDot(QLabel):
    """Breathing indicator — animates via QTimer + stylesheet alpha (no QGraphicsEffect).

    QGraphicsEffects on frameless WA_TranslucentBackground windows with a custom
    paintEvent fight Qt's paint pipeline on Windows. Timer-driven restyling is
    slower-refresh but rock-solid.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("●", parent)
        self._color = SEV_GREEN
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)
        self._apply_style()

    def set_color(self, color: str) -> None:
        self._color = color
        self._apply_style()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.04) % 1.0
        self._apply_style()

    def _apply_style(self) -> None:
        # Smooth 0.35 -> 1.0 breathing via sine wave.
        t = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
        alpha = int(90 + 165 * t)  # 90..255
        c = QColor(self._color)
        r, g, b = c.red(), c.green(), c.blue()
        self.setStyleSheet(f"color: rgba({r},{g},{b},{alpha}); font-size: 11pt;")


# ---------- thinking dots ----------

class ThinkingDots(QWidget):
    """Three dots rippling left-to-right via QTimer + stylesheet alpha."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        self._dots: list[QLabel] = []
        for _ in range(3):
            d = QLabel("●")
            lay.addWidget(d)
            self._dots.append(d)
        lay.addStretch(1)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(70)
        self._apply()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.03) % 1.0
        self._apply()

    def _apply(self) -> None:
        c = QColor(SEV_CYAN)
        r, g, b = c.red(), c.green(), c.blue()
        for i, d in enumerate(self._dots):
            # Each dot lags the next by ~33% of cycle.
            p = (self._phase + i * 0.33) % 1.0
            t = 0.5 + 0.5 * math.sin(p * 2 * math.pi)
            alpha = int(60 + 195 * t)  # 60..255
            d.setStyleSheet(f"color: rgba({r},{g},{b},{alpha}); font-size: 11pt;")


# ---------- AI avatar gem ----------

class AIAvatar(QWidget):
    """Cyan gradient gem with inner highlight and a slow shimmer."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def _tick(self) -> None:
        self._phase = (self._phase + 0.015) % 1.0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            shimmer = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)

            # Outer disc — radial gradient (cyan/teal)
            outer = QRadialGradient(rect.center(), rect.width() / 2.0)
            outer.setColorAt(0.0, QColor(80, 210, 255, 255))
            outer.setColorAt(0.75, QColor(40, 140, 220, 240))
            outer.setColorAt(1.0, QColor(30, 80, 140, 230))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(outer))
            p.drawEllipse(rect)

            # Inner highlight (moves slightly with shimmer)
            hl_w = rect.width() * 0.48
            hl_h = rect.height() * 0.36
            cx = rect.center().x() - rect.width() * 0.12
            cy = rect.center().y() - rect.height() * 0.18 - shimmer * 0.5
            hl_rect = QRectF(cx - hl_w / 2, cy - hl_h / 2, hl_w, hl_h)
            hl = QRadialGradient(hl_rect.center(), hl_rect.width() / 2.0)
            hl.setColorAt(0.0, QColor(255, 255, 255, int(170 + 40 * shimmer)))
            hl.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(hl))
            p.drawEllipse(hl_rect)

            # Thin ring border
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(160, 220, 255, 120))
            pen.setWidthF(1.0)
            p.setPen(pen)
            p.drawEllipse(rect)
        finally:
            p.end()


# ---------- overlay panel ----------

class OverlayPanel(QWidget):
    """Top-right floating glass panel with outer aura."""

    # Widget is bigger than the card so we have room to paint the aura glow.
    CARD_INSET       = 24
    CARD_WIDTH       = 390
    CARD_HEIGHT      = 600
    WIDTH_DEFAULT    = CARD_WIDTH + 2 * CARD_INSET
    HEIGHT_DEFAULT   = CARD_HEIGHT + 2 * CARD_INSET
    WIDTH_MIN        = 360
    WIDTH_MAX        = 720
    HEIGHT_MIN       = 180     # collapsed header-only
    HEIGHT_MAX       = 900
    RESIZE_GRIP_PX   = 18      # bottom-right corner zone for resizing
    EDGE_MARGIN      = 18
    CARD_RADIUS      = 22
    CONTENT_WIDTH    = 332

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(self.WIDTH_MIN, self.HEIGHT_MIN)
        self.setMaximumSize(self.WIDTH_MAX, self.HEIGHT_MAX)
        self.resize(self.WIDTH_DEFAULT, self.HEIGHT_DEFAULT)

        QFontDatabase.addApplicationFont(":/fonts/Inter.ttf")

        self._drag_offset: Optional[QPoint] = None
        self._final_pos: Optional[QPoint] = None
        self._resize_origin: Optional[QPoint] = None
        self._resize_start_size = None
        self._collapsed = False
        self._expanded_size = None  # remembered so we can restore on expand
        # NOTE: do NOT attach a QGraphicsOpacityEffect to `self`. Combined with
        # our custom paintEvent it causes "Painter not active" — the effect
        # renders the widget to an offscreen pixmap while paintEvent is already
        # holding a QPainter on the same device. Use setWindowOpacity() for the
        # top-level fade; effects on inner widgets are fine.
        self.setWindowOpacity(0.0)

        self._blur_enabled = False
        self._build_ui()
        self._apply_stylesheet()
        self._position_top_right()
        self.reset()

    # ---------- layout ----------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            self.CARD_INSET, self.CARD_INSET,
            self.CARD_INSET, self.CARD_INSET,
        )
        root.setSpacing(0)

        self.card = QFrame(self)
        self.card.setObjectName("card")
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.card)

        body = QVBoxLayout(self.card)
        body.setContentsMargins(20, 16, 20, 18)
        body.setSpacing(12)

        # ---- header ----
        self.titlebar = QWidget()
        tb = QHBoxLayout(self.titlebar)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(12)

        self.avatar = AIAvatar()
        tb.addWidget(self.avatar)

        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(0)
        self.title = QLabel("Augie")
        self.title.setObjectName("title")
        self.stage_meta = QLabel("Ready")
        self.stage_meta.setObjectName("stageMeta")
        header_text.addWidget(self.title)
        header_text.addWidget(self.stage_meta)
        tb.addLayout(header_text)

        tb.addStretch(1)
        self.dot = BreathingDot()
        tb.addWidget(self.dot)

        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("btnMin")
        self.btn_min.setFixedSize(26, 26)
        self.btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_min.setToolTip("Collapse / expand")
        self.btn_min.clicked.connect(self.toggle_collapsed)
        tb.addWidget(self.btn_min)

        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(QApplication.instance().quit)
        tb.addWidget(self.btn_close)
        body.addWidget(self.titlebar)

        # ---- status line / thinking dots ----
        self.status_line = QLabel("Press F9 when in planning phase.")
        self.status_line.setObjectName("statusLine")
        self.status_line.setWordWrap(True)
        self.status_line.setMaximumWidth(self.CONTENT_WIDTH)
        body.addWidget(self.status_line)

        self.thinking = ThinkingDots()
        self.thinking.hide()
        body.addWidget(self.thinking)

        # ---- hero: verdict in its own sub-card ----
        self.verdict_card = QFrame()
        self.verdict_card.setObjectName("verdictCard")
        vl = QVBoxLayout(self.verdict_card)
        vl.setContentsMargins(16, 14, 16, 14)
        vl.setSpacing(12)

        self.verdict = QLabel("")
        self.verdict.setObjectName("verdict")
        self.verdict.setWordWrap(True)
        self.verdict.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        vl.addWidget(self.verdict)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        chip_row.setContentsMargins(0, 0, 0, 0)
        self.chip_confidence = Chip("—")
        self.chip_tempo = Chip("—")
        self.chip_action = Chip("—")
        for c in (self.chip_confidence, self.chip_tempo, self.chip_action):
            chip_row.addWidget(c)
        chip_row.addStretch(1)
        self.chip_row_wrap = QWidget()
        self.chip_row_wrap.setLayout(chip_row)
        vl.addWidget(self.chip_row_wrap)

        body.addWidget(self.verdict_card)

        # ---- scroll region for reasoning / suggestions / warning ----
        self.scroll = QScrollArea()
        self.scroll.setObjectName("scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_inner = QWidget()
        scroll_inner.setObjectName("scrollInner")
        inner = QVBoxLayout(scroll_inner)
        inner.setContentsMargins(0, 6, 0, 6)
        inner.setSpacing(8)

        # Reasoning
        self.reasoning_header = self._section_header("REASONING")
        inner.addWidget(self.reasoning_header)
        self.reasoning = QLabel("")
        self.reasoning.setObjectName("reasoning")
        self.reasoning.setWordWrap(True)
        self.reasoning.setMaximumWidth(self.CONTENT_WIDTH)
        self.reasoning.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        inner.addWidget(self.reasoning)

        # Suggestions (icon rows)
        self.consider_header = self._section_header(
            "▲  SUGGESTIONS", color=SEV_INDIGO, spacing=True)
        inner.addWidget(self.consider_header)
        self.consider_list = QWidget()
        self.consider_list_layout = QVBoxLayout(self.consider_list)
        self.consider_list_layout.setContentsMargins(0, 0, 0, 0)
        self.consider_list_layout.setSpacing(4)
        inner.addWidget(self.consider_list)

        # Warning (own sub-card)
        self.warn_card = QFrame()
        self.warn_card.setObjectName("warnCard")
        wl = QVBoxLayout(self.warn_card)
        wl.setContentsMargins(14, 10, 14, 12)
        wl.setSpacing(4)
        self.warn_header = QLabel("⚠  WARNING")
        self.warn_header.setObjectName("warnHeader")
        wl.addWidget(self.warn_header)
        self.warn_body = QLabel("")
        self.warn_body.setObjectName("warnings")
        self.warn_body.setWordWrap(True)
        self.warn_body.setMaximumWidth(self.CONTENT_WIDTH - 20)
        wl.addWidget(self.warn_body)
        inner.addWidget(self.warn_card)

        self.data_note = QLabel("")
        self.data_note.setObjectName("dataNote")
        self.data_note.setWordWrap(True)
        self.data_note.setMaximumWidth(self.CONTENT_WIDTH)
        inner.addWidget(self.data_note)

        inner.addStretch(1)
        self.scroll.setWidget(scroll_inner)
        body.addWidget(self.scroll, 1)

        # meta bar
        self.meta = QLabel("")
        self.meta.setObjectName("meta")
        body.addWidget(self.meta)

    def _section_header(self, text: str, color: str = TEXT_MUTED,
                        spacing: bool = False) -> QLabel:
        lbl = QLabel(text)
        top = "10px" if spacing else "2px"
        lbl.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-family: {FONT_STACK};
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 0.18em;
                padding-top: {top};
                padding-bottom: 4px;
            }}
        """)
        return lbl

    # ---------- suggestion rows ----------

    def _clear_consider_rows(self) -> None:
        while self.consider_list_layout.count():
            item = self.consider_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _suggestion_icon(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ("scout", "bait", "watch", "check")):
            return "⌕"
        if any(k in t for k in ("preserve", "hold", "save", "protect")):
            return "◇"
        if any(k in t for k in ("roll", "reroll")):
            return "↻"
        if any(k in t for k in ("level", "xp")):
            return "▲"
        if any(k in t for k in ("slam", "item", "component")):
            return "◆"
        return "◆"

    def _make_consider_row(self, text: str, tag: Optional[str] = None) -> QWidget:
        row = QFrame()
        row.setObjectName("suggestRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(10)

        icon = QLabel(self._suggestion_icon(text))
        icon.setObjectName("suggestIcon")
        icon.setFixedWidth(18)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        title = QLabel(text)
        title.setObjectName("suggestTitle")
        title.setWordWrap(True)
        title.setMaximumWidth(self.CONTENT_WIDTH - 80)
        text_col.addWidget(title)
        if tag:
            tag_lbl = QLabel(tag.upper())
            tag_lbl.setObjectName("suggestTag")
            tag_lbl.setStyleSheet(f"""
                QLabel#suggestTag {{
                    color: {_sev_color(tag)};
                    background-color: rgba(255, 255, 255, 0.04);
                    border: 1px solid {_sev_color(tag)};
                    border-radius: 7px;
                    padding: 2px 8px;
                    font-family: {FONT_STACK};
                    font-size: 7pt;
                    font-weight: 700;
                    letter-spacing: 0.1em;
                }}
            """)
            tag_row = QHBoxLayout()
            tag_row.setContentsMargins(0, 2, 0, 0)
            tag_row.addWidget(tag_lbl)
            tag_row.addStretch(1)
            text_col.addLayout(tag_row)
        lay.addLayout(text_col)
        lay.addStretch(1)

        chev = QLabel("›")
        chev.setObjectName("suggestChev")
        lay.addWidget(chev)
        return row

    # ---------- stylesheet ----------

    def _apply_stylesheet(self) -> None:
        r, g, b, a = CARD_FILL_RGBA
        card_bg = f"rgba({r},{g},{b},{a/255:.2f})"
        qss = f"""
            QFrame#card {{
                background-color: {card_bg};
                border-radius: {self.CARD_RADIUS}px;
                border: 1px solid {BORDER_COOL};
            }}
            QFrame#verdictCard {{
                background-color: {SUBCARD_FILL};
                border: 1px solid {SUBCARD_BORDER};
                border-radius: 14px;
            }}
            QFrame#suggestRow {{
                background-color: {SUBCARD_FILL};
                border: 1px solid {SUBCARD_BORDER};
                border-radius: 12px;
            }}
            QFrame#warnCard {{
                background-color: {WARN_FILL};
                border: 1px solid {WARN_BORDER};
                border-radius: 12px;
            }}
            QLabel#title {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_STACK};
                font-size: 14pt;
                font-weight: 700;
                letter-spacing: 0.01em;
            }}
            QLabel#stageMeta {{
                color: {TEXT_SECOND};
                font-family: {FONT_STACK};
                font-size: 9pt;
                font-weight: 500;
            }}
            QPushButton#btnClose, QPushButton#btnMin {{
                color: {TEXT_MUTED};
                background-color: transparent;
                border: none;
                border-radius: 13px;
                font-family: {FONT_STACK};
                font-size: 15pt;
                font-weight: 400;
                padding: 0;
            }}
            QPushButton#btnClose {{
                font-size: 17pt;
                font-weight: 300;
            }}
            QPushButton#btnClose:hover, QPushButton#btnMin:hover {{
                color: {TEXT_PRIMARY};
                background-color: rgba(255,255,255,0.08);
            }}
            QLabel#statusLine {{
                color: {TEXT_SECOND};
                font-family: {FONT_MONO};
                font-size: 9pt;
                font-weight: 400;
                padding: 0;
            }}
            QLabel#verdict {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_STACK};
                font-size: 15pt;
                font-weight: 600;
                line-height: 1.32em;
            }}
            QLabel#reasoning {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_STACK};
                font-size: 10pt;
                font-weight: 400;
                line-height: 1.6em;
            }}
            QLabel#suggestIcon {{
                color: {SEV_CYAN};
                font-family: {FONT_STACK};
                font-size: 14pt;
                font-weight: 700;
            }}
            QLabel#suggestTitle {{
                color: {TEXT_PRIMARY};
                font-family: {FONT_STACK};
                font-size: 10pt;
                font-weight: 600;
            }}
            QLabel#suggestChev {{
                color: {TEXT_MUTED};
                font-family: {FONT_STACK};
                font-size: 14pt;
                font-weight: 500;
            }}
            QLabel#warnHeader {{
                color: {WARN_ACCENT};
                font-family: {FONT_STACK};
                font-size: 9pt;
                font-weight: 700;
                letter-spacing: 0.16em;
            }}
            QLabel#warnings {{
                color: #F4E2C8;
                font-family: {FONT_STACK};
                font-size: 10pt;
                font-weight: 400;
                line-height: 1.6em;
            }}
            QLabel#dataNote {{
                color: {TEXT_MUTED};
                font-family: {FONT_STACK};
                font-size: 8pt;
                font-style: italic;
                padding-top: 6px;
            }}
            QLabel#meta {{
                color: {TEXT_MUTED};
                font-family: {FONT_MONO};
                font-size: 8pt;
                font-weight: 400;
                padding-top: 6px;
                letter-spacing: 0.02em;
            }}
            QScrollArea#scroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#scroll > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 2px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.18);
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255,255,255,0.34);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """
        self.setStyleSheet(qss)

    # ---------- painting: outer multi-color aura ----------

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            card_rect = QRectF(
                self.CARD_INSET, self.CARD_INSET,
                self.width() - 2 * self.CARD_INSET,
                self.height() - 2 * self.CARD_INSET,
            )

            # Four corner radial glows — different hues, soft falloff.
            glow_reach = self.CARD_INSET * 3.2
            corners = [
                (QPointF(card_rect.right(), card_rect.top()),
                 QColor(90, 200, 255, 140)),   # cyan top-right
                (QPointF(card_rect.right(), card_rect.bottom()),
                 QColor(255, 150, 80, 130)),   # amber bottom-right
                (QPointF(card_rect.left(), card_rect.bottom()),
                 QColor(200, 100, 255, 120)),  # magenta bottom-left
                (QPointF(card_rect.left(), card_rect.top()),
                 QColor(120, 120, 240, 110)),  # indigo top-left
            ]
            p.setPen(Qt.PenStyle.NoPen)
            for center, color in corners:
                grad = QRadialGradient(center, glow_reach)
                grad.setColorAt(0.0, color)
                fade = QColor(color); fade.setAlpha(0)
                grad.setColorAt(1.0, fade)
                p.setBrush(QBrush(grad))
                p.drawRect(self.rect())

            # A subtle inner cool-tone rim OUTSIDE the card edge, sharper than the glow.
            rim_path = QPainterPath()
            rim_path.addRoundedRect(card_rect.adjusted(-2, -2, 2, 2),
                                     self.CARD_RADIUS + 2, self.CARD_RADIUS + 2)
            rim_path.addRoundedRect(card_rect,
                                     self.CARD_RADIUS, self.CARD_RADIUS)
            p.setBrush(QColor(255, 255, 255, 22))
            p.drawPath(rim_path)

            # Bottom-right resize grip: three short diagonal dashes.
            if not self._collapsed:
                grip_pen = QPen(QColor(255, 255, 255, 70))
                grip_pen.setWidthF(1.4)
                grip_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(grip_pen)
                gx = card_rect.right() - 6
                gy = card_rect.bottom() - 6
                for i in range(3):
                    off = 4 + i * 4
                    p.drawLine(QPointF(gx - off, gy), QPointF(gx, gy - off))
        finally:
            # CRITICAL: end the painter before super() runs, or Qt refuses
            # to hand the paint device to the child widget painters.
            p.end()
        super().paintEvent(event)

    # ---------- window behavior ----------

    def _position_top_right(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - self.EDGE_MARGIN
        y = screen.top() + self.EDGE_MARGIN
        self.move(x, y)
        self._final_pos = QPoint(x, y)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            self._blur_enabled = _enable_win_acrylic(hwnd)
        except Exception:
            self._blur_enabled = False

        if self._final_pos is None:
            self._position_top_right()
        start_pos = QPoint(self._final_pos.x() + 50, self._final_pos.y())
        self.move(start_pos)

        self.setWindowOpacity(0.0)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setStartValue(0.0); fade.setEndValue(1.0)
        fade.setDuration(520); fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        slide = QPropertyAnimation(self, b"pos", self)
        slide.setStartValue(start_pos); slide.setEndValue(self._final_pos)
        slide.setDuration(560); slide.setEasingCurve(QEasingCurve.Type.OutExpo)

        fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        slide.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _is_over_titlebar(self, global_pos: QPoint) -> bool:
        local = self.mapFromGlobal(global_pos)
        if not self.titlebar.isVisible():
            return False
        tb_top_left = self.titlebar.mapTo(self, QPoint(0, 0))
        tb_rect = self.titlebar.rect().translated(tb_top_left)
        return tb_rect.contains(local)

    def _is_over_resize_grip(self, local_pos: QPoint) -> bool:
        # Bottom-right corner of the card (not the widget — aura inset doesn't resize).
        card_right  = self.width()  - self.CARD_INSET
        card_bottom = self.height() - self.CARD_INSET
        zone = self.RESIZE_GRIP_PX
        return (card_right - zone <= local_pos.x() <= card_right
                and card_bottom - zone <= local_pos.y() <= card_bottom)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            gp = event.globalPosition().toPoint()
            local = self.mapFromGlobal(gp)

            if self._is_over_resize_grip(local) and not self._collapsed:
                self._resize_origin = gp
                self._resize_start_size = self.size()
                event.accept()
                return

            if self._is_over_titlebar(gp):
                self._drag_offset = gp - self.pos()
                event.accept()
                return
        event.ignore()

    def mouseMoveEvent(self, event) -> None:
        gp = event.globalPosition().toPoint()
        local = self.mapFromGlobal(gp)

        if self._resize_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = gp - self._resize_origin
            new_w = max(self.WIDTH_MIN,  min(self.WIDTH_MAX,
                         self._resize_start_size.width()  + delta.x()))
            new_h = max(self.HEIGHT_MIN, min(self.HEIGHT_MAX,
                         self._resize_start_size.height() + delta.y()))
            self.resize(new_w, new_h)
            self.update()  # repaint aura at new size
            event.accept()
            return

        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = gp - self._drag_offset
            self.move(new_pos)
            self._final_pos = new_pos
            event.accept()
            return

        # Hover: show resize cursor when over grip
        if not self._collapsed and self._is_over_resize_grip(local):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        self._resize_origin = None
        self._resize_start_size = None
        self.unsetCursor()

    # ---------- collapse / expand ----------

    def toggle_collapsed(self) -> None:
        if self._collapsed:
            self._expand()
        else:
            self._collapse()

    def _collapse(self) -> None:
        if self._collapsed:
            return
        self._expanded_size = self.size()
        self._collapsed = True
        # Hide everything except the titlebar.
        self.status_line.hide()
        self.thinking.hide()
        self.verdict_card.hide()
        self.scroll.hide()
        self.meta.hide()
        self.btn_min.setText("▢")
        # Shrink to just header height + insets + body padding.
        collapsed_h = 2 * self.CARD_INSET + self.titlebar.sizeHint().height() + 36
        self.setMinimumHeight(collapsed_h)
        self.resize(self.width(), collapsed_h)
        self.update()

    def _expand(self) -> None:
        if not self._collapsed:
            return
        self._collapsed = False
        self.status_line.show()
        self.scroll.show()
        # verdict_card / meta visibility is driven by state; leave to set_*.
        if self.verdict.text():
            self.verdict_card.show()
        if self.meta.text():
            self.meta.show()
        self.btn_min.setText("—")
        self.setMinimumHeight(self.HEIGHT_MIN)
        target_h = (self._expanded_size.height()
                    if self._expanded_size else self.HEIGHT_DEFAULT)
        self.resize(self.width(), target_h)
        self.update()

    # ---------- state updates ----------

    def reset(self) -> None:
        self.dot.set_color(SEV_GREEN)
        self.stage_meta.setText("Ready")
        self.status_line.setText("Press F9 when in planning phase.")
        self.thinking.hide()
        self.verdict_card.hide()
        self.verdict.setText("")
        self.chip_row_wrap.hide()
        self.reasoning.setText("")
        self.reasoning.hide()
        self.reasoning_header.hide()
        self._clear_consider_rows()
        self.consider_list.hide()
        self.consider_header.hide()
        self.warn_body.setText("")
        self.warn_card.hide()
        self.data_note.setText("")
        self.data_note.hide()
        self.meta.setText("")

    def set_extracting(self) -> None:
        self.dot.set_color(SEV_CYAN)
        self.stage_meta.setText("Reading…")
        self.status_line.setText("Capturing the board")
        self.thinking.show()
        self.verdict_card.hide()
        self.reasoning.hide()
        self.reasoning_header.hide()
        self.consider_list.hide()
        self.consider_header.hide()
        self.warn_card.hide()
        self.data_note.hide()
        self.meta.setText("")

    def set_extracted(self, state: dict) -> None:
        self.dot.set_color(SEV_INDIGO)
        self.thinking.hide()
        stage = state.get('stage') or '—'
        self.stage_meta.setText(f"Stage {stage}")
        bits = [
            f"hp {state.get('hp') if state.get('hp') is not None else '—'}",
            f"gold {state.get('gold') if state.get('gold') is not None else '—'}",
            f"lvl {state.get('level') or '—'}",
            f"streak {state.get('streak', 0):+d}" if state.get('streak') is not None else "streak —",
        ]
        self.status_line.setText("  ·  ".join(bits))

    def set_verdict(self, text: str) -> None:
        self.verdict.setText(text)
        self.verdict_card.show()
        self.dot.set_color(SEV_AMBER)

    def set_reasoning(self, text: str) -> None:
        self.reasoning.setText(text)
        self.reasoning.show()
        self.reasoning_header.show()

    def set_final(self, rec: dict, meta: dict, wall_s: float,
                  vision_cost: float, game_id: Optional[int]) -> None:
        self.dot.set_color(SEV_GREEN)

        conf = (rec.get("confidence") or "—").upper()
        tempo = (rec.get("tempo_read") or "—").upper()
        action = (rec.get("primary_action") or "—").upper()
        self.chip_confidence.set_severity(conf)
        self.chip_tempo.set_severity(tempo)
        self.chip_action.set_severity(action)
        self.chip_row_wrap.show()

        cons = rec.get("considerations") or []
        self._clear_consider_rows()
        if cons:
            for i, c_text in enumerate(cons):
                tag = "HIGH PRIORITY" if i == 0 and conf == "HIGH" else (
                    "OPTIONAL" if i >= 2 else None
                )
                self.consider_list_layout.addWidget(self._make_consider_row(c_text, tag))
            self.consider_list.show()
            self.consider_header.show()
        else:
            self.consider_list.hide()
            self.consider_header.hide()

        warns = rec.get("warnings") or []
        if warns:
            self.warn_body.setText("\n".join(warns))
            self.warn_card.show()
        else:
            self.warn_card.hide()

        dq = rec.get("data_quality_note")
        if dq:
            self.data_note.setText(f"ℹ  {dq}")
            self.data_note.show()
        else:
            self.data_note.hide()

        total_cost = (vision_cost or 0) + (meta.get("cost_usd") or 0)
        gid = f"game {game_id}" if game_id is not None else "no session"
        self.meta.setText(f"{wall_s:>4.1f}s  ·  ${total_cost:.4f}  ·  {gid}")

    def set_error(self, text: str) -> None:
        self.dot.set_color(SEV_RED)
        self.thinking.hide()
        self.status_line.setText(f"Error: {text}")
        self.stage_meta.setText("Error")
        self.verdict_card.hide()
        self.reasoning.hide()
        self.reasoning_header.hide()
        self.consider_list.hide()
        self.consider_header.hide()
        self.warn_card.hide()
        self.data_note.hide()


# ---------- standalone preview ----------

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    panel = OverlayPanel()
    panel.show()

    def step1():
        panel.set_extracting()
    def step2():
        panel.set_extracted({"stage": "1-2", "hp": 70, "gold": 2, "level": 2, "streak": 0})
    def step3():
        panel.set_verdict("Hold all gold, lose naturally, and scout for a lose-streak — you're 1-2 on 1-2 with nothing to buy.")
    def step4():
        panel.set_reasoning(
            "It's a weird early game and no augments yet — there's literally nothing "
            "to spend on that advances your game plan. The Space Gods look away for now."
        )
    def step5():
        panel.set_final(
            rec={
                "confidence": "HIGH", "tempo_read": "ON_PACE",
                "primary_action": "HOLD_ECON",
                "considerations": [
                    "Scout 1-3 | Bait carousel",
                    "Preserve streak options",
                    "Plan Stage 2 augment direction",
                ],
                "warnings": [
                    "An augment is incoming soon — be extra careful, it should be full but verify after carousel.",
                    "No augment yet is expected at this stage, but it's a tricky way to get direction.",
                ],
                "data_quality_note": None,
            },
            meta={"cost_usd": 0.0083},
            wall_s=10.4, vision_cost=0.0114, game_id=None,
        )

    QTimer.singleShot(  800, step1)
    QTimer.singleShot( 2800, step2)
    QTimer.singleShot( 4400, step3)
    QTimer.singleShot( 9000, step4)
    QTimer.singleShot(14000, step5)

    sys.exit(app.exec())
