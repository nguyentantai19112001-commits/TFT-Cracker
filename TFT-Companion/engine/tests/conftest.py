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
