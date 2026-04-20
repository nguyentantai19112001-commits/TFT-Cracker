"""One-shot test of the unified state builder.

Usage:
    py test_state_builder.py                    # captures current screen
    py test_state_builder.py path/to.png        # parses existing screenshot
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from state_builder import build_state
from vision import capture_screen


def main() -> int:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return 1

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"ERROR: {path} not found")
            return 1
        png = path.read_bytes()
        print(f"Loaded {path} ({len(png) // 1024} KB)")
    else:
        print("Capturing current screen in 3s... switch to TFT now.")
        time.sleep(3)
        png = capture_screen()
        out = Path("last_capture.png")
        out.write_bytes(png)
        print(f"Captured {len(png) // 1024} KB, saved to {out}")

    print("Building state (LCU → OCR → Claude Vision)...")
    client = Anthropic(api_key=api_key)
    state = build_state(png, client)

    d = state.to_dict()
    print("\n=== Source Status ===")
    for k, v in d["sources"].items():
        print(f"  {k}: {v}")

    print("\n=== Game State ===")
    print(json.dumps({k: v for k, v in d.items() if k != "sources"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
