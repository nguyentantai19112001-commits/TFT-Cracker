"""Custom title bar for the Augie panel."""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QLinearGradient, QFont, QPainterPath,
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
)

from ui.tokens import COLOR, SIZE, SPACE, FONT, RADIUS


class LogoTile(QWidget):
    """36×36 rounded-square with pink→blue gradient + ✦ glyph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtCore import QRectF
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        g = QLinearGradient(rect.topLeft(), rect.bottomRight())
        g.setColorAt(0, QColor(COLOR.accent_pink))
        g.setColorAt(1, QColor(COLOR.accent_blue))
        p.fillPath(path, QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255)))
        f = QFont()
        f.setPointSize(18)
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "✦")
        p.end()


class HPPill(QWidget):
    """HP readout pill — color shifts by threshold."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self._hp: int = 100
        self._fg = QColor(COLOR.accent_green)
        self._bg_alpha = 25

    def set_hp(self, hp: int):
        hp = max(0, min(100, hp))
        self._hp = hp
        self._update_color()
        self.update()
        self.setVisible(hp < 100)

    def _update_color(self):
        if self._hp >= 50:
            self._fg = QColor(COLOR.accent_green)
            self._bg_alpha = 25
        elif self._hp >= 25:
            self._fg = QColor(COLOR.accent_gold)
            self._bg_alpha = 36
        else:
            self._fg = QColor(COLOR.accent_red)
            self._bg_alpha = 46

    def sizeHint(self) -> QSize:
        return QSize(64, 26)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtCore import QRectF
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0, 0, -1, -1), 13, 13)

        bg = QColor(self._fg)
        bg.setAlpha(self._bg_alpha)
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(self._fg, 1))
        p.drawPath(path)

        p.setPen(QPen(self._fg))
        f = QFont()
        f.setPointSize(FONT.size_body_small)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"HP  {self._hp}")
        p.end()


class ChromeButton(QPushButton):
    """24×24 rounded hover button for pin/min/close."""

    def __init__(self, glyph: str, parent=None):
        super().__init__(glyph, parent)
        self.setFixedSize(SIZE.chrome_btn, SIZE.chrome_btn)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,13);
                color: {COLOR.text_tertiary};
                border: none;
                border-radius: {SIZE.chrome_btn_radius}px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,31);
                color: {COLOR.text_primary};
            }}
        """)


class TitleBar(QWidget):
    pin_toggled = pyqtSignal(bool)
    minimize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(SIZE.title_bar_height)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.xl, SPACE.md, SPACE.md, SPACE.sm)
        layout.setSpacing(SPACE.md)

        self.logo = LogoTile()
        layout.addWidget(self.logo)

        title_col = QWidget()
        title_layout = QVBoxLayout(title_col)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)

        self.title_label = QLabel("Augie")
        self.title_label.setStyleSheet(
            f"color: {COLOR.text_primary}; "
            f"font-size: {FONT.size_header_title}px; "
            f"font-weight: {FONT.weight_semibold}; "
            f"letter-spacing: -0.3px;"
        )
        self.subtitle_label = QLabel("Stage —")
        self.subtitle_label.setStyleSheet(
            f"color: {COLOR.text_tertiary}; "
            f"font-size: {FONT.size_header_subtitle}px;"
        )
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.subtitle_label)
        layout.addWidget(title_col)

        layout.addStretch(1)

        self.hp_pill = HPPill()
        self.hp_pill.setVisible(False)
        layout.addWidget(self.hp_pill)

        self.pin_btn = ChromeButton("◉")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(True)
        self.pin_btn.toggled.connect(self.pin_toggled.emit)

        self.min_btn = ChromeButton("−")
        self.min_btn.clicked.connect(self.minimize_clicked.emit)

        self.close_btn = ChromeButton("×")
        self.close_btn.clicked.connect(self.close_clicked.emit)

        layout.addWidget(self.pin_btn)
        layout.addWidget(self.min_btn)
        layout.addWidget(self.close_btn)

    def set_stage(self, stage: str):
        self.subtitle_label.setText(f"Stage {stage}")

    def set_hp(self, hp: int):
        self.hp_pill.set_hp(hp)
