"""keyboard_sim.py — Keyboard simulation stub.

Placeholder for TFT keyboard interactions. Not yet implemented.
All public functions raise NotImplementedError until the feature is
formally scoped and approved.

Likely future use cases:
    - Press Spacebar to lock shop
    - Press D to roll
    - Press F to buy XP
    - Press 1-5 to purchase specific shop slots

Implementation plan when the time comes:
    1. Use `keyboard` lib (already in requirements) for global hotkey sends
    2. Add win32api fallback for games that filter keyboard lib events
    3. Always gate on a USER_CONFIRMED flag — never automate silently
    4. dry_run=True mode logs the action without sending it
"""
from __future__ import annotations


def send_key(key: str, *, dry_run: bool = True) -> None:
    """Send a single keystroke to the active window.

    Args:
        key: key name compatible with `keyboard` library (e.g. "space", "d").
        dry_run: when True, log the action but don't actually send it.

    Raises:
        NotImplementedError: always, until this module is implemented.
    """
    raise NotImplementedError(
        f"keyboard_sim.send_key({key!r}) is not yet implemented. "
        "This stub is reserved for future UI-assist automation."
    )


def roll_shop(*, dry_run: bool = True) -> None:
    """Press D to roll the shop."""
    send_key("d", dry_run=dry_run)


def buy_xp(*, dry_run: bool = True) -> None:
    """Press F to buy XP."""
    send_key("f", dry_run=dry_run)


def lock_shop(*, dry_run: bool = True) -> None:
    """Press Space to lock/unlock shop."""
    send_key("space", dry_run=dry_run)
