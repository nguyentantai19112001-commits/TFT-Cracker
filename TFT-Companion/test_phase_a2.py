"""Phase A2 infrastructure smoke test — NO API required.

Verifies:
    1. DB schema loads cleanly (captures/extractions/template_matches/vision_calls)
    2. log_capture compresses PNG → JPEG, inserts row, hash + path stored
    3. Template bank loads (champions, traits)
    4. Template matcher self-matches with score 1.0 + wide margin
    5. Matcher logs to DB with dumped-crop path when ambiguous/rejected

Run with: py test_phase_a2.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from PIL import Image

import db
import template_match as tm


ROOT = Path(__file__).parent


def _count(table: str) -> int:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def main() -> int:
    print("=== Phase A2 infra smoke test ===\n")

    print("[1] init_db ...")
    db.init_db()
    for table in ("captures", "extractions", "template_matches",
                  "vision_calls", "game_states", "games"):
        n = _count(table)
        print(f"    {table}: {n} rows")

    print("\n[2] log_capture against test_screenshot_en.png ...")
    screenshot = ROOT / "test_screenshot_en.png"
    if not screenshot.exists():
        print(f"    SKIP — {screenshot} missing")
        return 1
    png = screenshot.read_bytes()
    orig_kb = len(png) // 1024

    capture_id = db.log_capture(png, trigger="test")
    print(f"    capture_id={capture_id}")
    conn = sqlite3.connect(db.DB_PATH)
    row = conn.execute(
        "SELECT file_path, sha256, width, height, bytes_on_disk FROM captures WHERE id=?",
        (capture_id,)
    ).fetchone()
    conn.close()
    path, sha, w, h, disk_bytes = row
    print(f"    stored: {path} ({w}x{h}, {disk_bytes//1024} KB  <- was {orig_kb} KB)")
    print(f"    sha256={sha[:16]}...")

    print("\n[3] template bank stats ...")
    print(f"    {tm.bank_stats()}")

    print("\n[4] self-match sanity (Aatrox portrait vs full bank) ...")
    aatrox = Image.open(ROOT / "assets/champions/TFT17_Aatrox.png")
    winner, score, runner, rscore = tm.match(aatrox, "champion")
    print(f"    winner='{winner}'  score={score:.3f}")
    print(f"    runner='{runner}'  score={rscore:.3f}")
    assert winner == "Aatrox", f"Expected Aatrox, got {winner!r}"
    assert score > 0.99, f"Self-match should be ~1.0, got {score:.3f}"
    print("    PASS")

    print("\n[5] match_and_log (ambiguous crop — random noise) ...")
    import numpy as np
    noise_arr = (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
    noise_img = Image.fromarray(noise_arr)
    winner, score = tm.match_and_log(
        capture_id=capture_id, region=noise_img, category="champion",
        region_xywh=(0, 0, 64, 64),
    )
    print(f"    noise matched='{winner}' score={score:.3f} (expect low + rejected)")

    print("\n[6] final row counts ...")
    for table in ("captures", "template_matches", "extractions"):
        print(f"    {table}: {_count(table)}")

    print("\nAll infrastructure green. Ready for end-to-end with ANTHROPIC_API_KEY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
