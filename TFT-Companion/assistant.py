"""TFT Assistant — Phase 1: press F12 to capture screen and print parsed game state."""

import json
import os
import sys
import time

import keyboard
from anthropic import Anthropic
from dotenv import load_dotenv

from vision import capture_screen, parse_game_state

HOTKEY = "f12"


def analyze(client: Anthropic) -> None:
    print(f"\n[{time.strftime('%H:%M:%S')}] Capturing screen...")
    t0 = time.time()
    png = capture_screen()
    print(f"  screenshot captured ({len(png) // 1024} KB)")

    print("  sending to Claude Opus 4.7...")
    try:
        state = parse_game_state(png, client)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Claude returned unparseable JSON: {e}")
        return
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        return

    elapsed = time.time() - t0
    print(f"  parsed in {elapsed:.1f}s\n")
    print(json.dumps(state, indent=2))
    print(f"\nPress {HOTKEY.upper()} to analyze again. Ctrl+C to quit.")


def main() -> None:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    print("=" * 50)
    print("  TFT ASSISTANT  |  Phase 1: Vision-only")
    print("=" * 50)
    print(f"Hotkey: {HOTKEY.upper()}  (Ctrl+C to quit)")
    print("Open TFT, reach a planning phase, then press the hotkey.\n")

    keyboard.add_hotkey(HOTKEY, analyze, args=(client,))

    try:
        keyboard.wait()  # blocks until interrupted
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
