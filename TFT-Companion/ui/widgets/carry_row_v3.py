"""CarryRowV3 — 56px carry row with BIS delta display."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QSizePolicy

from ui.tokens import COLOR, FONT, RADIUS, SHADOW, SIZE, SPACE
from ui.fx import apply_shadow


_COST_COLORS = {
    1: COLOR.cost_1, 2: COLOR.cost_2, 3: COLOR.cost_3,
    4: COLOR.cost_4, 5: COLOR.cost_5,
}


class CarryRowV3(QWidget):
    """Row: champ icon + name + cost/star | current items | BIS items | delta indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._display_name = ""
        self._cost = 1
        self._star = 1
        self._items_current: list[str] = []
        self._items_bis: list[str] = []
        self._delta_count = 0
        self._delta_components: list[str] = []
        self._stage_role = "hold_only"
        self.setFixedHeight(SIZE.carry_row_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        apply_shadow(self, SHADOW.elev_row)

    def apply(
        self,
        display_name: str,
        cost: int,
        star: int,
        items_current: list[str],
        items_bis: list[str],
        delta_count: int,
        delta_components: list[str],
        stage_role: str = "primary",
    ) -> None:
        self._display_name = display_name
        self._cost = cost
        self._star = star
        self._items_current = items_current
        self._items_bis = items_bis
        self._delta_count = delta_count
        self._delta_components = delta_components
        self._stage_role = stage_role
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(780, SIZE.carry_row_height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = SPACE.sm

        # Row background — opaque elevated fill
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), RADIUS.row, RADIUS.row)
        bg_c = QColor(COLOR.elev_1)
        bg_c.setAlpha(255)
        p.fillPath(bg_path, QBrush(bg_c))
        # Border
        p.setPen(QPen(QColor(*COLOR.border_subtle_rgba), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0, 0, w, h).adjusted(0, 0, -1, -1), RADIUS.row, RADIUS.row)
        # Inner top highlight
        hl = QColor(*COLOR.inner_highlight_rgba)
        p.setPen(QPen(hl, 1))
        p.drawLine(RADIUS.row, 1, w - RADIUS.row, 1)

        cost_hex = _COST_COLORS.get(self._cost, COLOR.cost_1)
        icon_size = 40

        # Champion color block (left)
        icon_path = QPainterPath()
        icon_path.addRoundedRect(QRectF(pad, (h - icon_size) / 2, icon_size, icon_size),
                                  RADIUS.champ_icon, RADIUS.champ_icon)
        icon_c = QColor(cost_hex)
        icon_c.setAlpha(60)
        p.fillPath(icon_path, QBrush(icon_c))

        # Champion initial
        p.setPen(QPen(QColor(cost_hex)))
        f_init = QFont()
        f_init.setPointSize(14)
        f_init.setWeight(QFont.Weight.Bold)
        p.setFont(f_init)
        p.drawText(QRectF(pad, (h - icon_size) / 2, icon_size, icon_size),
                   Qt.AlignmentFlag.AlignCenter, self._display_name[:1])

        # Champion name + star
        x_text = pad + icon_size + SPACE.sm
        p.setPen(QPen(QColor(COLOR.text_primary)))
        f_name = QFont()
        f_name.setPointSize(FONT.size_body)
        f_name.setWeight(QFont.Weight.DemiBold)
        p.setFont(f_name)
        star_str = "★" * self._star
        p.drawText(QRectF(x_text, 4, 100, h // 2),
                   Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                   f"{self._display_name} {star_str}")

        # Role sub-label
        p.setPen(QPen(QColor(COLOR.text_muted)))
        f_role = QFont()
        f_role.setPointSize(9)
        p.setFont(f_role)
        p.drawText(QRectF(x_text, h // 2 + 2, 100, h // 2 - 4),
                   Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                   self._stage_role.replace("_", " "))

        # Items area (center)
        item_x = x_text + 108
        item_size = SIZE.icon_mini_item
        item_gap = 4

        # Current items (top row)
        p.setPen(QPen(QColor(COLOR.text_muted)))
        f_small = QFont(); f_small.setPointSize(8); p.setFont(f_small)
        p.drawText(QRectF(item_x - 30, 2, 30, 14),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "Now:")
        for i, item in enumerate(self._items_current[:3]):
            ix = item_x + i * (item_size + item_gap)
            iy = (h // 2 - item_size) // 2
            item_c = QColor(COLOR.accent_blue); item_c.setAlpha(60)
            p.setBrush(QBrush(item_c))
            p.setPen(QPen(QColor(COLOR.border_hover_rgba[0], COLOR.border_hover_rgba[1],
                                  COLOR.border_hover_rgba[2], COLOR.border_hover_rgba[3])))
            p.drawRoundedRect(QRectF(ix, iy, item_size, item_size), 3, 3)
            p.setPen(QPen(QColor(COLOR.text_tertiary)))
            p.drawText(QRectF(ix, iy, item_size, item_size),
                       Qt.AlignmentFlag.AlignCenter, item[:2])

        # BIS items (bottom row)
        p.setPen(QPen(QColor(COLOR.text_muted)))
        p.setFont(f_small)
        p.drawText(QRectF(item_x - 30, h // 2, 30, 14),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "BIS:")
        for i, item in enumerate(self._items_bis[:3]):
            ix = item_x + i * (item_size + item_gap)
            iy = h // 2 + (h // 2 - item_size) // 2
            held = item in self._items_current
            item_c = QColor(COLOR.accent_gold if held else COLOR.bg_input)
            item_c.setAlpha(80 if held else 40)
            p.setBrush(QBrush(item_c))
            border = QColor(COLOR.accent_gold if held else COLOR.text_disabled)
            border.setAlpha(120 if held else 60)
            p.setPen(QPen(border, 1))
            p.drawRoundedRect(QRectF(ix, iy, item_size, item_size), 3, 3)
            p.setPen(QPen(QColor(COLOR.text_tertiary if held else COLOR.text_disabled)))
            p.drawText(QRectF(ix, iy, item_size, item_size),
                       Qt.AlignmentFlag.AlignCenter, item[:2])

        # Delta badge (right)
        badge_w = 80
        bx = w - badge_w - pad
        if self._delta_count == 0:
            badge_c = QColor(COLOR.accent_green); badge_c.setAlpha(80)
            p.setBrush(QBrush(badge_c))
            p.setPen(QPen(QColor(COLOR.accent_green), 1))
            p.drawRoundedRect(QRectF(bx, (h - 24) / 2, badge_w, 24), 6, 6)
            p.setPen(QPen(QColor(COLOR.accent_green)))
            f_badge = QFont(); f_badge.setPointSize(FONT.size_body_small); f_badge.setWeight(QFont.Weight.Bold)
            p.setFont(f_badge)
            p.drawText(QRectF(bx, (h - 24) / 2, badge_w, 24),
                       Qt.AlignmentFlag.AlignCenter, "✓ PERFECT")
        else:
            badge_c = QColor(COLOR.accent_gold); badge_c.setAlpha(40)
            p.setBrush(QBrush(badge_c))
            p.setPen(QPen(QColor(COLOR.accent_gold), 1))
            p.drawRoundedRect(QRectF(bx, (h - 24) / 2, badge_w, 24), 6, 6)
            p.setPen(QPen(QColor(COLOR.accent_gold)))
            f_badge = QFont(); f_badge.setPointSize(FONT.size_body_small); p.setFont(f_badge)
            need_str = ", ".join(self._delta_components[:2])
            p.drawText(QRectF(bx, (h - 24) / 2, badge_w, 24),
                       Qt.AlignmentFlag.AlignCenter, f"Δ{self._delta_count}")

        p.end()
