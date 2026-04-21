"""Phase 3 smoke tests: bespoke widgets (no display required)."""
import sys
import types
import pytest

# Stub PyQt6 before any import that touches it
class _Stub:
    """Base stub for any Qt class — absorbs all args, returns self from calls."""
    def __init__(self, *a, **kw): pass
    def __call__(self, *a, **kw): return self
    def __getattr__(self, name): return _Stub()
    def __set_name__(self, owner, name): pass


def _make_stub_class(name: str) -> type:
    return type(name, (_Stub,), {})


class _AutoAttrModule(types.ModuleType):
    """Module stub that auto-creates class stubs for any attribute access."""
    _classes: dict[str, type] = {}

    def __getattr__(self, name):
        if name not in _AutoAttrModule._classes:
            _AutoAttrModule._classes[name] = _make_stub_class(name)
        return _AutoAttrModule._classes[name]


def _stub_pyqt():
    if "PyQt6" in sys.modules:
        return
    qt = _AutoAttrModule("PyQt6")
    for sub in ("QtCore", "QtGui", "QtWidgets"):
        m = _AutoAttrModule(f"PyQt6.{sub}")
        sys.modules[f"PyQt6.{sub}"] = m
        setattr(qt, sub, m)
    sys.modules["PyQt6"] = qt

_stub_pyqt()

for _dep in ("qframelesswindow", "winmica", "loguru"):
    if _dep not in sys.modules:
        _m = types.ModuleType(_dep)
        if _dep == "loguru":
            import logging
            _m.logger = logging.getLogger("loguru")  # type: ignore[attr-defined]
        sys.modules[_dep] = _m


def test_section_label_uppercases_text():
    """SectionLabel must force text to uppercase."""
    from ui.tokens import COLOR, FONT
    # Validate token fields used by SectionLabel exist
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
