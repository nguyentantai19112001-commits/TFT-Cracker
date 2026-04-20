"""Game session lifecycle — bind every capture / recommendation to a game_id.

Call start_game() when a match begins, end_game() when it ends. In between,
current_game_id() returns the active game so state_builder can tag captures.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

import db
import game_assets


_CURRENT: Optional[int] = None


def start_game(queue_type: Optional[str] = None,
               notes: Optional[str] = None) -> int:
    """Insert a games row, return its id. Replaces any active session."""
    global _CURRENT
    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        cur = conn.execute(
            """INSERT INTO games (set_id, patch_version, queue_type, notes)
               VALUES (?, ?, ?, ?)""",
            (game_assets.SET_ID, game_assets.PATCH, queue_type, notes),
        )
        conn.commit()
        _CURRENT = cur.lastrowid
        return _CURRENT
    finally:
        conn.close()


def end_game(final_placement: Optional[int] = None) -> None:
    """Mark the active game complete."""
    global _CURRENT
    if _CURRENT is None:
        return
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute(
            """UPDATE games SET end_time = CURRENT_TIMESTAMP,
                                final_placement = ?
               WHERE id = ?""",
            (final_placement, _CURRENT),
        )
        conn.commit()
    finally:
        conn.close()
    _CURRENT = None


def current_game_id() -> Optional[int]:
    return _CURRENT
