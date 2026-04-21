"""pytest configuration for engine/tests/.

Registers custom marks so pytest doesn't warn about unknown markers.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (requires live API key or live game)"
    )
