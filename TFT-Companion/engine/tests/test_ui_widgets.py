"""Phase 3 smoke tests: bespoke widgets (no display required).
PyQt6 stub is installed by conftest.py before collection.
"""
import pytest


def test_section_label_uppercases_text():
    from ui.tokens import COLOR, FONT
    assert hasattr(COLOR, "text_muted")
    assert hasattr(FONT, "size_section_label")
    assert hasattr(FONT, "letter_spacing_caps")


def test_warning_block_tokens():
    from ui.tokens import COLOR
    assert hasattr(COLOR, "accent_red")
    assert hasattr(COLOR, "accent_red_soft_rgba")
    assert isinstance(COLOR.accent_red_soft_rgba, tuple)
    assert len(COLOR.accent_red_soft_rgba) == 4


def test_aurora_backdrop_blobs_have_correct_shape():
    from ui.widgets.aurora_backdrop import _BLOBS
    assert len(_BLOBS) == 3
    for blob in _BLOBS:
        cx_f, cy_f, r_f, color_hex, alpha = blob
        assert 0.0 <= cx_f <= 1.0
        assert 0.0 <= cy_f <= 1.0
        assert r_f > 0
        assert color_hex.startswith("#")
        assert 0 <= alpha <= 255


def test_action_row_priority_colors_defined():
    from ui.widgets.action_row import _PRIORITY_COLORS
    for key in ("high", "medium", "low"):
        assert key in _PRIORITY_COLORS
        assert _PRIORITY_COLORS[key].startswith("#")


def test_item_icon_category_gradients_all_valid():
    from ui.widgets.item_icon import _CATEGORY_GRADIENTS
    assert len(_CATEGORY_GRADIENTS) >= 5
    for cat, (from_c, to_c) in _CATEGORY_GRADIENTS.items():
        assert from_c.startswith("#"), f"{cat}: from_c not a hex color"
        assert to_c.startswith("#"), f"{cat}: to_c not a hex color"
