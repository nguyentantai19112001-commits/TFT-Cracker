"""Tests for logging_setup.py (Task 8 — loguru + Sentry).

Tests run without a real Sentry DSN — just verifies the module configures
cleanly and produces a log file.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_TFTROOT = Path(__file__).resolve().parents[3]
if str(_TFTROOT) not in sys.path:
    sys.path.insert(0, str(_TFTROOT))

import pytest


def test_setup_logging_no_sentry(monkeypatch):
    """Without SENTRY_DSN, setup_logging() completes without error and writes a log file."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    from loguru import logger as _logger
    from logging_setup import setup_logging, logger
    # ignore_cleanup_errors avoids PermissionError on Windows when loguru holds the file open
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        setup_logging(log_dir=Path(td))
        logger.info("test message from test_setup_logging_no_sentry")
        log_files = list(Path(td).glob("*.log"))
        _logger.remove()  # release file handle before temp dir cleanup
        assert log_files, "log file must be created in log_dir"


def test_setup_logging_with_fake_sentry(monkeypatch):
    """With a fake SENTRY_DSN, setup_logging must not raise — just warn or init."""
    monkeypatch.setenv("SENTRY_DSN", "https://fake@test.ingest.sentry.io/0")
    monkeypatch.setenv("AUGIE_ENV", "test")
    from loguru import logger as _logger
    from logging_setup import setup_logging
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        try:
            setup_logging(log_dir=Path(td))
        except Exception as exc:
            pytest.fail(f"setup_logging raised with fake DSN: {exc}")
        finally:
            _logger.remove()  # release file handle


def test_logger_importable():
    """logger must be importable and usable without calling setup_logging first."""
    from logging_setup import logger
    assert hasattr(logger, "info")
    assert hasattr(logger, "debug")
    assert hasattr(logger, "exception")


def test_sentry_rate_limit_drops_at_cap():
    """_sentry_rate_limit drops events once the daily cap is exceeded."""
    from datetime import datetime, timezone
    from logging_setup import _sentry_rate_limit
    import logging_setup as ls

    # Prime the date key so the reset branch doesn't fire during this test.
    today_key = f"_date_{datetime.now(timezone.utc).date().isoformat()}"
    setattr(_sentry_rate_limit, today_key, True)

    # Set count to cap so the next event tips it over
    ls._SENTRY_EVENT_COUNT = ls._SENTRY_DAILY_CAP
    result = _sentry_rate_limit({"test": True}, {})
    assert result is None, "event above cap must be dropped (return None)"

    # Below cap: count already at cap+1 from above call; reset manually
    ls._SENTRY_EVENT_COUNT = 0
    result = _sentry_rate_limit({"test": True}, {})
    assert result is not None, "event below cap must be forwarded"
