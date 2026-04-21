"""pytest configuration for engine/tests/.

Adds engine/ to sys.path before any test module is imported, so test
files that lack their own sys.path guard still resolve engine modules.
Also registers custom marks.
"""
import sys
from pathlib import Path

import pytest

# engine/ root — must be sys.path[0] for direct module imports (e.g. schemas, econ).
_ENGINE = Path(__file__).resolve().parent.parent
if sys.path[0] != str(_ENGINE):
    sys.path.insert(0, str(_ENGINE))

# Project root (TFT-Companion/) — needed for `from engine.X import ...` and `from ui.X import ...`
_ROOT = _ENGINE.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (requires live API key or live game)"
    )


# ---------------------------------------------------------------------------
# Shared PyQt6 stub — installed once for all UI tests.
# Each sub-module (QtCore, QtGui, QtWidgets) auto-creates class stubs for
# any attribute access so widget code can be imported without a display.
# ---------------------------------------------------------------------------
import types as _types


class _StubBase:
    """Absorbs all constructor args; attribute access returns a new stub."""
    def __init__(self, *a, **kw): pass
    def __call__(self, *a, **kw): return self
    def __set_name__(self, owner, name): pass
    def __getattr__(self, name): return _StubBase()
    def __iter__(self): return iter([])
    def __class_getitem__(cls, item): return cls


def _make_qt_class(name: str) -> type:
    return type(name, (_StubBase,), {})


class _QtSubModule(_types.ModuleType):
    _cache: dict[str, type] = {}

    def __init__(self, name: str):
        super().__init__(name)
        self.__file__ = ""          # hypothesis iterates __file__ as string
        self.__spec__ = None

    def __getattr__(self, name: str):
        if name not in _QtSubModule._cache:
            _QtSubModule._cache[name] = _make_qt_class(name)
        return _QtSubModule._cache[name]


def _install_pyqt6_stub():
    if "PyQt6" in sys.modules:
        # Replace bare stub if it's not our class-based one
        existing = sys.modules["PyQt6"]
        if not isinstance(existing, _QtSubModule) and not hasattr(existing, "_qt_stubbed"):
            pass  # fall through to reinstall
        else:
            return  # already our stub

    qt = _QtSubModule("PyQt6")
    qt._qt_stubbed = True  # type: ignore[attr-defined]
    for sub in ("QtCore", "QtGui", "QtWidgets", "QtNetwork"):
        m = _QtSubModule(f"PyQt6.{sub}")
        sys.modules[f"PyQt6.{sub}"] = m
        setattr(qt, sub, m)
    sys.modules["PyQt6"] = qt

    for dep in ("qframelesswindow", "winmica"):
        if dep not in sys.modules:
            sys.modules[dep] = _QtSubModule(dep)

    if "loguru" not in sys.modules:
        try:
            import loguru as _loguru_real
            sys.modules["loguru"] = _loguru_real
        except ImportError:
            import logging as _logging
            lm = _types.ModuleType("loguru")
            lm.logger = _logging.getLogger("loguru")  # type: ignore[attr-defined]
            sys.modules["loguru"] = lm


_install_pyqt6_stub()
