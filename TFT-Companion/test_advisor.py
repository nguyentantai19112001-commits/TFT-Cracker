"""Full pipeline end-to-end on a screenshot.

Extraction (LCU + Vision) → rules → scoring → Claude advisor → pretty-print.

Usage:
    py test_advisor.py                        # captures live screen
    py test_advisor.py test_screenshot_en.png # parses saved screenshot
"""

from __future__ import annotations

import json
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


def _hr(label: str, char: str = "=") -> None:
    print(f"\n{char * 3} {label} {char * (70 - len(label))}")


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

    client = Anthropic(api_key=api_key)

    _hr("1. Extraction (LCU + Claude Vision)")
    state = build_state(png, client, trigger="test_advisor")
    d = state.to_dict()
    print(f"  sources: {d['sources']}")
    print(f"  stage={d['stage']}  gold={d['gold']}  hp={d['hp']}  level={d['level']}  "
          f"xp={d['xp']}  streak={d['streak']}")
    print(f"  board_units={len(d['board'])} bench={len(d['bench'])} shop={len(d['shop'])} "
          f"traits={len(d['active_traits'])} augments={len(d['augments'])}")

    _hr("2. Rule engine (deterministic)")
    fires = rules.evaluate(d)
    if not fires:
        print("  (no rules fired)")
    for f in fires:
        print(f"  [{f.severity:.1f}] {f.rule_id:30s} {f.action:18s} {f.message}")

    _hr("3. Board strength (0–100)")
    bs = scoring.compute_board_strength(d)
    print(f"  score={bs['score']}  raw={bs['raw']}  expected_raw={bs['expected_raw']}  "
          f"confidence={bs['confidence']}  unknown={bs['unknown_units']}/{bs['total_units']}")
    print(f"  active_traits={bs['active_traits']}  trait_mult={bs['trait_mult']}  "
          f"items={bs['item_count']}")

    _hr("4. Claude advisor (Sonnet 4.6)")
    result = advisor.advise(d, fires, bs, client, capture_id=state.capture_id)
    meta = result["__meta__"]
    if not meta["parse_ok"]:
        print(f"  FAILED: {meta['error']}")
        print(f"  raw: {meta.get('raw_text', '')[:500]}")
        return 1
    print(f"  cost=${meta['cost_usd']}  elapsed={meta['elapsed_ms']}ms  "
          f"tokens={meta['input_tokens']}in/{meta['output_tokens']}out")
    _hr("RECOMMENDATION", "-")
    print(json.dumps(result["recommendation"], indent=2, ensure_ascii=False))

    _hr("5. Total pipeline cost", "-")
    vision_cost = d["sources"]["vision_cost_usd"] or 0
    advisor_cost = meta["cost_usd"] or 0
    print(f"  vision: ${vision_cost:.4f}")
    print(f"  advisor: ${advisor_cost:.4f}")
    print(f"  TOTAL:  ${vision_cost + advisor_cost:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
