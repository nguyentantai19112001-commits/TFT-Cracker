"""mouse_sim.py — Mouse simulation stub.

Placeholder for TFT mouse interactions. Not yet implemented.
All public functions raise NotImplementedError until the feature is
formally scoped, calibrated coordinates are verified, and the user
approves the automation scope.

Likely future use cases:
    - Click a shop slot to purchase a champion
    - Drag a champion from bench to board (requires coord calibration)
    - Click augment options during augment rounds

Implementation plan when the time comes:
    1. Import calibrated coords from screen_coords.py
    2. Use pyautogui or win32api for actual mouse events
    3. Verify board resolution / DPI scaling before ANY click
    4. dry_run=True mode that prints the target but doesn't click
    5. Safety guard: only allow clicks within known TFT-window bounds
"""
from __future__ import annotations
from typing import Optional


def click(x: int, y: int, *, dry_run: bool = True) -> None:
    """Click at absolute screen coordinates.

    Args:
        x, y: absolute screen coordinates (pixels from top-left).
        dry_run: when True, log target but don't actually click.

    Raises:
        NotImplementedError: always, until this module is implemented.
    """
    raise NotImplementedError(
        f"mouse_sim.click({x}, {y}) is not yet implemented. "
        "This stub is reserved for future UI-assist automation."
    )


def buy_shop_slot(slot_index: int, *, dry_run: bool = True) -> None:
    """Click the Nth shop slot (0-indexed).

    Requires calibrated coords from screen_coords.py. Not yet wired.
    """
    raise NotImplementedError("mouse_sim.buy_shop_slot is not yet implemented.")


def drag_to_board(bench_idx: int, board_x: int, board_y: int, *,
                  dry_run: bool = True) -> None:
    """Drag a unit from bench position bench_idx to board hex (board_x, board_y).

    Requires coord calibration and DPI-aware transform. Not yet wired.
    """
    raise NotImplementedError("mouse_sim.drag_to_board is not yet implemented.")
