"""SQLite logging layer.

Centralizes DB access + capture compression. Every module that wants to log
something calls into here — keeps the schema in one place and lets us swap
to Postgres later without touching callers.

Captures are stored on disk as JPEG q85, max 1280px wide (resize preserves
aspect ratio). DB holds path + sha256 + dimensions only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from PIL import Image

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "tftcoach.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
CAPTURES_DIR = ROOT / "captures"
CROPS_DIR = ROOT / "captures" / "crops"

JPEG_QUALITY = 85
MAX_WIDTH = 1280


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call repeatedly."""
    conn = _connect()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def _compress_png(png_bytes: bytes) -> tuple[bytes, int, int]:
    """PNG bytes in → JPEG bytes out (resized if wider than MAX_WIDTH)."""
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    if w > MAX_WIDTH:
        new_h = round(h * (MAX_WIDTH / w))
        img = img.resize((MAX_WIDTH, new_h), Image.LANCZOS)
        w, h = MAX_WIDTH, new_h
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), w, h


def log_capture(png_bytes: bytes, game_id: Optional[int] = None,
                trigger: str = "hotkey") -> int:
    """Compress + store screenshot, insert captures row, return capture_id."""
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    jpeg_bytes, w, h = _compress_png(png_bytes)
    sha = hashlib.sha256(jpeg_bytes).hexdigest()
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sha[:8]}.jpg"
    path = CAPTURES_DIR / fname
    path.write_bytes(jpeg_bytes)

    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO captures
               (game_id, file_path, sha256, width, height, bytes_on_disk, trigger)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (game_id, str(path.relative_to(ROOT)), sha, w, h, len(jpeg_bytes), trigger),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def log_extraction(capture_id: int, field: str, source: str,
                   raw: Any = None, parsed: Any = None,
                   confidence: Optional[float] = None,
                   elapsed_ms: int = 0, error: Optional[str] = None) -> None:
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO extractions
               (capture_id, field, source, raw_value, parsed_value, confidence, elapsed_ms, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (capture_id, field, source,
             json.dumps(raw) if raw is not None else None,
             json.dumps(parsed) if parsed is not None else None,
             confidence, elapsed_ms, error),
        )
        conn.commit()
    finally:
        conn.close()


def log_template_match(capture_id: int, category: str,
                       region: tuple[int, int, int, int],
                       winner: Optional[str], winner_score: float,
                       runner_up: Optional[str] = None,
                       runner_up_score: Optional[float] = None,
                       is_ambiguous: bool = False,
                       is_rejected: bool = False,
                       elapsed_ms: int = 0,
                       crop_png: Optional[bytes] = None) -> int:
    """Log a template-match attempt. If crop_png given, dump it for later labeling."""
    x, y, w, h = region
    crop_path = None
    if crop_png:
        CROPS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        crop_path = CROPS_DIR / f"{category}_{ts}.png"
        crop_path.write_bytes(crop_png)

    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO template_matches
               (capture_id, category, region_x, region_y, region_w, region_h,
                dumped_crop_path, winner_name, winner_score,
                runner_up_name, runner_up_score, is_ambiguous, is_rejected, elapsed_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (capture_id, category, x, y, w, h,
             str(crop_path.relative_to(ROOT)) if crop_path else None,
             winner, winner_score, runner_up, runner_up_score,
             int(is_ambiguous), int(is_rejected), elapsed_ms),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def log_vision_call(capture_id: int, model: str, prompt_version: str,
                    response_json: Optional[str], parse_ok: bool,
                    input_tokens: Optional[int] = None,
                    output_tokens: Optional[int] = None,
                    cost_usd: Optional[float] = None,
                    error: Optional[str] = None,
                    elapsed_ms: int = 0) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO vision_calls
               (capture_id, model, prompt_version, input_tokens, output_tokens,
                cost_usd, response_json, parse_ok, error, elapsed_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (capture_id, model, prompt_version, input_tokens, output_tokens,
             cost_usd, response_json, int(parse_ok), error, elapsed_ms),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def log_game_state(game_id: int, capture_id: Optional[int], state: dict) -> int:
    xp = state.get("xp") or ""
    xp_cur, xp_need = None, None
    if "/" in xp:
        try:
            xp_cur, xp_need = (int(x) for x in xp.split("/", 1))
        except ValueError:
            pass

    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO game_states
               (game_id, capture_id, stage, gold, hp, level, xp_current, xp_needed,
                streak, state_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (game_id, capture_id, state.get("stage"), state.get("gold"),
             state.get("hp"), state.get("level"), xp_cur, xp_need,
             state.get("streak"), json.dumps(state)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


class Timer:
    """Context manager — `with Timer() as t: ...; t.ms` gives elapsed ms."""
    def __enter__(self):
        self._start = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *_):
        self.ms = int((time.perf_counter() - self._start) * 1000)
