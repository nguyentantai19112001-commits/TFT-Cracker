# TASK_08_SENTRY.md — Sentry + loguru observability

> Wire up proper logging and crash reporting. Free tier; one-time setup.
> Makes every future bug 10× easier to diagnose.

---

## Prereq checks

```bash
pytest -q                          # current count green
grep -rn "import logging\|print(" *.py | wc -l
    # baseline: how much legacy logging exists
```

User must have a Sentry account (free tier: 5K errors/month). They need
to create a project and share the DSN. If they haven't:
  1. Stop here
  2. Tell user: "You need to create a free Sentry account at
     https://sentry.io, create a Python project, and share the DSN.
     Free tier gives 5,000 errors/month which is plenty."
  3. Wait for DSN before proceeding.

Store the DSN in a `.env` file (gitignored), not in code.

## Files you may edit

- `logging_setup.py` (new — centralized loguru + sentry config)
- `assistant_overlay.py` (call setup_logging at app init)
- Any file using `print()` or `logging.basicConfig()` — migrate to loguru
- `.env.example` (new — template with SENTRY_DSN placeholder)
- `.gitignore` (add `.env` if not already ignored)
- `requirements.txt` (add `loguru`, `sentry-sdk`, `python-dotenv`)
- `STATE.md`

## Dependencies

```bash
pip install loguru sentry-sdk python-dotenv
```

## The setup module

```python
# logging_setup.py
"""Centralized observability: loguru for structured logs + Sentry for crash reports.

Call setup_logging() once at app startup, before anything else logs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger
from dotenv import load_dotenv


def setup_logging(log_dir: Path | None = None) -> None:
    """Configure loguru sinks and initialize Sentry.

    - Console sink at INFO level with colorized output
    - File sink at DEBUG level with 7-day rotation to log_dir/augie.log
    - Sentry for exceptions (if SENTRY_DSN is in env)
    """
    load_dotenv()

    # Remove default loguru handler
    logger.remove()

    # Console: INFO and above, colored
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
        colorize=True,
    )

    # File: DEBUG and above, rotating
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

    # Sentry
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_logging = LoggingIntegration(
            level=None,         # don't capture breadcrumbs from logs
            event_level=None,   # don't auto-capture ERROR logs as Sentry events;
                                # use capture_exception() explicitly
        )
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[sentry_logging],
            traces_sample_rate=0.0,   # no perf monitoring (free tier is tight)
            profiles_sample_rate=0.0,
            send_default_pii=False,   # personal tool; no user data
            release=os.getenv("AUGIE_VERSION", "dev"),
            environment=os.getenv("AUGIE_ENV", "dev"),
            # Rate limiting: free tier is 5K errors/month, stay well under
            before_send=_sentry_rate_limit,
        )
        logger.info("Sentry initialized")
    else:
        logger.warning("SENTRY_DSN not set — crash reporting disabled")

    logger.info("Logging initialized")


# --- Rate limiting for Sentry ---

_SENTRY_EVENT_COUNT = 0
_SENTRY_DAILY_CAP = 170   # ~5000/month / 30 days


def _sentry_rate_limit(event, hint):
    """Hard cap at 170 events/day to protect the free tier."""
    global _SENTRY_EVENT_COUNT
    from datetime import datetime

    today = datetime.utcnow().date()
    last_date_key = f"_sentry_date_{today.isoformat()}"
    if not hasattr(_sentry_rate_limit, last_date_key):
        # New day; reset counter
        for attr in list(vars(_sentry_rate_limit)):
            if attr.startswith("_sentry_date_"):
                delattr(_sentry_rate_limit, attr)
        setattr(_sentry_rate_limit, last_date_key, True)
        _SENTRY_EVENT_COUNT = 0

    _SENTRY_EVENT_COUNT += 1
    if _SENTRY_EVENT_COUNT > _SENTRY_DAILY_CAP:
        return None   # drop this event
    return event


# --- Convenience re-export ---

__all__ = ["setup_logging", "logger"]
```

### `.env.example`

```
# Copy to .env and fill in real values. .env is gitignored.
SENTRY_DSN=https://YOUR_KEY@o123.ingest.sentry.io/456
AUGIE_VERSION=dev
AUGIE_ENV=dev
```

### Migrate existing logging

Find every `print(` or `logging.` call in production code (not tests).
Replace:

```python
# BEFORE
import logging
logging.info("F9 pressed")
print(f"State: {state}")

# AFTER
from logging_setup import logger
logger.info("F9 pressed")
logger.debug("state: {}", state)  # loguru uses {} not f-strings for lazy eval
```

Key logging points to add (if not already there):

```python
logger.info("F9 pipeline starting", extra={"trigger": "hotkey"})
logger.debug("state extracted: {stage} L{level} {gold}g {hp}HP",
             stage=state.stage, level=state.level, gold=state.gold, hp=state.hp)
logger.info("advisor verdict: {action}", action=verdict.primary_action.value)

# On exceptions in PipelineWorker:
try:
    ...
except Exception:
    logger.exception("pipeline failed")
    import sentry_sdk
    sentry_sdk.capture_exception()
    self.errorOccurred.emit("pipeline_error")
```

## Tests

```python
# tests/test_logging_setup.py
import os
from pathlib import Path
import tempfile

from logging_setup import setup_logging, logger


def test_setup_logging_no_sentry(monkeypatch):
    """Without SENTRY_DSN, setup still works (just no crash reporting)."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    with tempfile.TemporaryDirectory() as td:
        setup_logging(log_dir=Path(td))
        logger.info("test message")
        # Log file should exist
        assert any(Path(td).glob("*.log"))


def test_setup_logging_with_sentry(monkeypatch):
    """With SENTRY_DSN set, sentry_sdk gets initialized."""
    monkeypatch.setenv("SENTRY_DSN", "https://fake@test.sentry.io/1")
    monkeypatch.setenv("AUGIE_ENV", "test")
    with tempfile.TemporaryDirectory() as td:
        setup_logging(log_dir=Path(td))
        # We can't verify sentry init without monkeypatching further;
        # just confirm no exception thrown
```

## Acceptance gate

1. `pytest -q` shows +2 tests passing.
2. Running the app produces a log file at `~/.augie/logs/augie.log`.
3. Forcing an uncaught exception (manually, not automated) shows up in
   the Sentry dashboard.
4. `grep -rn "^import logging\|^print(" *.py | grep -v test` returns
   zero matches (all migrated to loguru).
5. `.env` is in `.gitignore` and `.env.example` is committed.

## Commit message

```
Task 8: add loguru + Sentry observability

- logging_setup.py centralizes loguru sinks (console INFO + file DEBUG)
- Sentry free-tier integration with 170 events/day rate cap
- Legacy print/logging migrated to loguru
- .env.example template committed; .env gitignored
- 2 new tests

Every future bug is 10x easier to diagnose.
```
