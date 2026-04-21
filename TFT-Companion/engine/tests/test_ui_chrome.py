"""Phase 2 smoke tests: design tokens + chrome widgets.
PyQt6 stub is installed by conftest.py before collection.
"""
import pytest
from ui.tokens import COLOR, SPACE, RADIUS, SIZE, FONT, MOTION, SHADOW, Z


def test_tokens_has_all_required_namespaces():
    for ns in (COLOR, SPACE, RADIUS, SIZE, FONT, MOTION, SHADOW, Z):
        assert ns is not None

    assert hasattr(COLOR, "bg_panel_rgba")
    assert hasattr(COLOR, "accent_pink")
    assert hasattr(SIZE, "panel_width")
    assert hasattr(SIZE, "title_bar_height")
    assert hasattr(FONT, "size_header_title")
    assert hasattr(MOTION, "fast")
    assert hasattr(RADIUS, "panel")
    assert hasattr(Z, "modal")


def test_color_cost_tokens_present():
    for cost in range(1, 6):
        assert hasattr(COLOR, f"cost_{cost}"), f"Missing COLOR.cost_{cost}"
    assert hasattr(COLOR, "cost_hero")


def test_size_panel_width_is_500():
    assert SIZE.panel_width == 500


def test_font_weights_are_ints():
    for attr in ("weight_regular", "weight_medium", "weight_semibold", "weight_bold"):
        val = getattr(FONT, attr)
        assert isinstance(val, int), f"FONT.{attr} should be int, got {type(val)}"
