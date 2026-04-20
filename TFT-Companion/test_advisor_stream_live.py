"""End-to-end streaming test — measures per-event arrival times.

Same pipeline as test_advisor.py but uses advise_stream() and prints
timestamps for each event (one_liner, reasoning, final) so you can
see exactly when the first verdict arrives vs the full response.

Usage:
    py test_advisor_stream_live.py                        # captures live screen
    py test_advisor_stream_live.py test_screenshot_en.png # parses saved shot
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

import advisor
import rules
import scoring
from state_builder import build_state
from vision import capture_screen


def main() -> int:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        png = path.read_bytes()
        print(f"Loaded {path} ({len(png)//1024} KB)")
    else:
        print("Capturing in 3s...")
        time.sleep(3)
        png = capture_screen()

    client = Anthropic(api_key=api_key)

    t_ext0 = time.time()
    state = build_state(png, client, trigger="test_stream")
    d = state.to_dict()
    print(f"\nExtraction done at +{time.time()-t_ext0:.1f}s  "
          f"(stage={d['stage']} hp={d['hp']} gold={d['gold']} lvl={d['level']})")

    fires = rules.evaluate(d)
    bs = scoring.compute_board_strength(d)
    print(f"Rules+scoring done at +{time.time()-t_ext0:.1f}s  "
          f"(score={bs['score']} conf={bs['confidence']} fires={len(fires)})")

    print("\n--- advisor stream ---")
    t_adv = time.time()
    final = None
    for evt, payload in advisor.advise_stream(
        d, fires, bs, client, capture_id=state.capture_id
    ):
        dt = time.time() - t_adv
        if evt == "one_liner":
            print(f"  [{dt:5.2f}s] one_liner: {payload}")
        elif evt == "reasoning":
            print(f"  [{dt:5.2f}s] reasoning: {payload[:120]}{'...' if len(payload) > 120 else ''}")
        elif evt == "final":
            final = payload
            print(f"  [{dt:5.2f}s] final  (parse_ok={payload['__meta__']['parse_ok']})")

    if final and final["__meta__"]["parse_ok"]:
        rec = final["recommendation"] or {}
        meta = final["__meta__"]
        print(f"\naction={rec.get('primary_action')}  conf={rec.get('confidence')}  "
              f"tempo={rec.get('tempo_read')}")
        print(f"tokens in/out = {meta['input_tokens']}/{meta['output_tokens']}  "
              f"cost=${meta['cost_usd']}")

        vision_cost = d["sources"]["vision_cost_usd"] or 0
        advisor_cost = meta["cost_usd"] or 0
        total_wall = time.time() - t_ext0
        print(f"\ntotal pipeline wall = {total_wall:.1f}s  "
              f"cost = ${vision_cost + advisor_cost:.4f}")
    else:
        print(f"\nFAILED: {final['__meta__']['error'] if final else 'no final event'}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
