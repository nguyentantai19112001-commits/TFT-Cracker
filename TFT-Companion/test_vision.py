"""One-shot vision test. Usage:
    py test_vision.py               # captures current screen
    py test_vision.py path/to.png   # parses an existing screenshot
"""

import json
import os
import sys
import time
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from vision import capture_screen, parse_game_state


def main() -> None:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"ERROR: {path} not found")
            sys.exit(1)
        png = path.read_bytes()
        print(f"Loaded {path} ({len(png) // 1024} KB)")
    else:
        print("Capturing current screen in 3s... switch to TFT now.")
        time.sleep(3)
        png = capture_screen()
        out = Path("last_capture.png")
        out.write_bytes(png)
        print(f"Captured {len(png) // 1024} KB, saved to {out}")

    print("Sending to Claude...")
    t0 = time.time()
    client = Anthropic(api_key=api_key)
    try:
        state = parse_game_state(png, client)
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"Parsed in {time.time() - t0:.1f}s\n")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
