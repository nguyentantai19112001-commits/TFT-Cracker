"""Phase 2 smoke tests: design tokens + chrome widgets."""
import sys
import types
import pytest

# Stub PyQt6 before any ui import so tests run without a display
_qt_stub = types.ModuleType("PyQt6")
for _sub in ("QtCore", "QtGui", "QtWidgets"):
    _mod = types.ModuleType(f"PyQt6.{_sub}")
    setattr(_qt_stub, _sub.replace("Qt", "").lower(), _mod)
    sys.modules[f"PyQt6.{_sub}"] = _mod
sys.modules["PyQt6"] = _qt_stub

# Stub optional deps
for _dep in ("qframelesswindow", "winmica", "loguru"):
    if _dep not in sys.modules:
        _m = types.ModuleType(_dep)
        if _dep == "loguru":
            import logging
            _logger = logging.getLogger("loguru")
            _m.logger = _logger  # type: ignore[attr-defined]
        sys.modules[_dep] = _m

from ui.tokens import COLOR, SPACE, RADIUS, SIZE, FONT, MOTION, SHADOW, Z  # noqa: E402


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
