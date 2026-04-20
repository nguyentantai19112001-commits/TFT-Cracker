"""Smoke test: import every module and run a trivial check.

Run after adding or moving files. If this passes, imports are healthy and
existing code paths were not broken.
"""

from __future__ import annotations

import sys
import traceback


def _check(label: str, fn) -> bool:
    try:
        fn()
        print(f"  OK   {label}")
        return True
    except Exception as e:
        print(f"  FAIL {label}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def main() -> int:
    print("Augie — import smoke test")
    print("-" * 50)
    results = []

    # Existing modules (must still work after phase A0)
    results.append(_check("vision (existing)", lambda: __import__("vision")))
    results.append(_check("assistant (existing)", lambda: __import__("assistant")))
    results.append(_check("test_vision (existing)", lambda: __import__("test_vision")))

    # New/lifted modules
    results.append(_check("vec2", lambda: __import__("vec2").Vec2(10, 20).get_coords()))
    results.append(_check("vec4", lambda: __import__("vec4")))
    results.append(_check("screen_coords", lambda: __import__("screen_coords").GOLD_POS.get_coords()))
    results.append(_check("ocr", lambda: __import__("ocr")))
    results.append(_check("ocr_helpers", lambda: __import__("ocr_helpers")))
    results.append(_check("round_reader", lambda: __import__("round_reader")))
    results.append(_check("game_assets", lambda: __import__("game_assets")))

    def check_tesseract_optional():
        import ocr
        err = ocr.check_tesseract()
        if err:
            print(f"       (tesseract not callable: {err} — install OK but binary not in expected path, set TESSERACT_CMD env var if needed)")
        else:
            print("       (tesseract binary reachable)")
    results.append(_check("tesseract binary check", check_tesseract_optional))

    def check_set_data():
        import game_assets
        if not game_assets.CHAMPIONS:
            print("       (set_data.json missing or empty — run data/fetch_community_dragon.py)")
        else:
            print(f"       ({len(game_assets.CHAMPIONS)} champions loaded, set {game_assets.SET_ID})")
    results.append(_check("game_assets data", check_set_data))

    print("-" * 50)
    if all(results):
        print("ALL PASSED")
        return 0
    print(f"FAILED: {results.count(False)} of {len(results)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
