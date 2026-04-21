"""Custom title bar for the Augie panel."""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QLinearGradient, QFont, QPainterPath,
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
)

from ui.tokens import COLOR, SIZE, SPACE, FONT, RADIUS


class LogoTile(QWidget):
    """40×40 rounded-square with pink→blue gradient + ✦ glyph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)

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
    """HP readout pill — color shifts by threshold, glow at critical."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self._hp: int = 100
        self._fg = QColor(COLOR.accent_green)
        self._bg_alpha = 25

    def set_hp(self, hp: int):
        from ui.fx import apply_shadow
        from ui.tokens import SHADOW
        hp = max(0, min(100, hp))
        self._hp = hp
        self._update_color()
        self.update()
        self.setVisible(hp < 100)
        if hp < 25:
            apply_shadow(self, SHADOW.glow_pink)
        else:
            self.setGraphicsEffect(None)

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
        return QSize(80, 30)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtCore import QRectF
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0, 0, -1, -1), 15, 15)

        bg = QColor(self._fg)
        bg.setAlpha(self._bg_alpha)
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(self._fg, 1))
        p.drawPath(path)

        # Inner highlight at top
        hl = QColor(255, 255, 255); hl.setAlpha(30)
        p.setPen(QPen(hl, 1))
        p.drawLine(int(rect.x() + 12), int(rect.y() + 1),
                   int(rect.right() - 12), int(rect.y() + 1))

        label = f"♥ HP  {self._hp}" if self._hp < 25 else f"HP  {self._hp}"
        p.setPen(QPen(self._fg))
        f = QFont()
        f.setPointSize(FONT.size_body_small)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
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

        from ui.fx import apply_shadow
        from ui.tokens import SHADOW as _SH
        self.logo = LogoTile()
        apply_shadow(self.logo, _SH.glow_pink)
        layout.addWidget(self.logo)

        title_col = QWidget()
        title_layout = QVBoxLayout(title_col)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        self.title_label = QLabel("Augie")
        self.title_label.setStyleSheet(
            f"color: {COLOR.text_primary}; "
            f"font-size: {FONT.size_header_title}px; "
            f"font-weight: {FONT.weight_bold}; "
            f"letter-spacing: -0.3px;"
        )
        self.subtitle_label = QLabel("STAGE —")
        self.subtitle_label.setStyleSheet(
            f"color: {COLOR.accent_gold};"
            f"font-size: {FONT.size_header_subtitle}px;"
            f"font-weight: {FONT.weight_bold};"
            f"background: rgba(255,210,122,0.12);"
            f"border: 1px solid rgba(255,210,122,0.3);"
            f"border-radius: 8px;"
            f"padding: 2px 8px;"
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
        self.subtitle_label.setText(f"STAGE {stage}")

    def set_hp(self, hp: int):
        self.hp_pill.set_hp(hp)

    # ── Drag to move window ──────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_start'):
            self.window().move(event.globalPosition().toPoint() - self._drag_start)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = QPoint()
        super().mouseReleaseEvent(event)
