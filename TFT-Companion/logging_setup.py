"""Centralized observability: loguru structured logs + optional Sentry crash reporting.

Call setup_logging() once at app startup, before anything else logs.

Usage:
    from logging_setup import setup_logging, logger
    setup_logging()
    logger.info("app started")

Sentry:
    Add SENTRY_DSN to .env (copy from .env.example). Free tier: 5K errors/month.
    If SENTRY_DSN is absent, crash reporting is silently disabled — app runs normally.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger


def setup_logging(log_dir: Path | None = None) -> None:
    """Configure loguru sinks and initialize Sentry.

    - Console sink: INFO and above, colorized.
    - File sink: DEBUG and above, 10 MB rotation, 7-day retention, zipped.
    - Sentry: exceptions only, when SENTRY_DSN is set in .env.
    """
    load_dotenv()

    logger.remove()  # clear loguru's default stderr handler

    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    if log_dir is None:
        log_dir = Path.home() / ".augie" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "augie.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | {name}:{function}:{line} | {message}",
    )

    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[LoggingIntegration(level=None, event_level=None)],
                traces_sample_rate=0.0,
                profiles_sample_rate=0.0,
                send_default_pii=False,
                release=os.getenv("AUGIE_VERSION", "dev"),
                environment=os.getenv("AUGIE_ENV", "dev"),
                before_send=_sentry_rate_limit,
            )
            logger.info("Sentry initialized (env={})", os.getenv("AUGIE_ENV", "dev"))
        except Exception as exc:
            logger.warning("Sentry init failed: {}", exc)
    else:
        logger.warning("SENTRY_DSN not set — crash reporting disabled")

    logger.info("Logging initialized")


# ── Sentry daily rate cap ──────────────────────────────────────────────────────
# Free tier: 5K errors/month → ~170/day. Hard cap prevents accidental bill spikes.

_SENTRY_EVENT_COUNT: int = 0
_SENTRY_DAILY_CAP: int = 170


def _sentry_rate_limit(event: dict, hint: dict):  # type: ignore[type-arg]
    global _SENTRY_EVENT_COUNT
    from datetime import datetime, timezone

    today_key = f"_date_{datetime.now(timezone.utc).date().isoformat()}"
    if not getattr(_sentry_rate_limit, today_key, False):
        # New UTC day — reset counter and clear yesterday's marker
        for attr in list(vars(_sentry_rate_limit)):
            if attr.startswith("_date_"):
                delattr(_sentry_rate_limit, attr)
        setattr(_sentry_rate_limit, today_key, True)
        _SENTRY_EVENT_COUNT = 0

    _SENTRY_EVENT_COUNT += 1
    if _SENTRY_EVENT_COUNT > _SENTRY_DAILY_CAP:
        return None  # drop — free tier protected
    return event


__all__ = ["setup_logging", "logger"]
