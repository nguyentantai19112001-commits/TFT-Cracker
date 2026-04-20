"""TFT Companion — hotkey-driven live advisor.

Runs the full pipeline on each hotkey press:
    F9   → capture + extract + rules + scoring + Claude advisor
    F10  → start a new game session (binds subsequent captures to it)
    F11  → end the current game session (prompt for final placement)
    ESC  → quit

Every call is logged to db/tftcoach.db. Inspect with:
    py -c "import sqlite3; [print(r) for r in sqlite3.connect('db/tftcoach.db').execute('SELECT * FROM game_states ORDER BY id DESC LIMIT 5')]"
"""

from __future__ import annotations

import json
import os
import sys
import time

import keyboard
from anthropic import Anthropic
from dotenv import load_dotenv

import advisor
import rules
import scoring
import session
from state_builder import build_state
from vision import capture_screen


HOTKEY_ADVISE = "f9"
HOTKEY_START = "f10"
HOTKEY_END = "f11"
HOTKEY_QUIT = "esc"


def _banner(text: str, ch: str = "=") -> None:
    print(f"\n{ch * 3} {text} {ch * max(0, 70 - len(text))}")


def _pretty_recommendation(rec: dict) -> None:
    if not rec:
        print("  (no recommendation)")
        return
    conf = rec.get("confidence", "?")
    tempo = rec.get("tempo_read", "?")
    print(f"  [{conf} confidence | tempo: {tempo}]")
    print(f"  → {rec.get('one_liner', '')}")
    print(f"\n  Why: {rec.get('reasoning', '')}")
    cons = rec.get("considerations") or []
    if cons:
        print("\n  Also consider:")
        for c in cons:
            print(f"    - {c}")
    warns = rec.get("warnings") or []
    if warns:
        print("\n  ⚠ Warnings:")
        for w in warns:
            print(f"    - {w}")
    dq = rec.get("data_quality_note")
    if dq:
        print(f"\n  (data note: {dq})")


def on_advise(client: Anthropic) -> None:
    t0 = time.time()
    print(f"\n[{time.strftime('%H:%M:%S')}] Capturing...")
    png = capture_screen()
    game_id = session.current_game_id()

    _banner("1/4 extraction")
    state = build_state(png, client, game_id=game_id, trigger="hotkey")
    d = state.to_dict()
    print(f"  stage={d['stage']} gold={d['gold']} hp={d['hp']} lvl={d['level']} "
          f"xp={d['xp']} streak={d['streak']}  board={len(d['board'])} "
          f"shop={len(d['shop'])} traits={len(d['active_traits'])}")
    if not state.sources.vision_ok:
        print(f"  Vision failed: {state.sources.vision_error}")
        return

    _banner("2/4 rules")
    fires = rules.evaluate(d)
    if not fires:
        print("  (no rules fired)")
    for f in fires[:6]:
        print(f"  [{f.severity:.1f}] {f.rule_id:30s} {f.message}")

    _banner("3/4 board strength")
    bs = scoring.compute_board_strength(d)
    print(f"  score={bs['score']}/100  conf={bs['confidence']}  "
          f"unknown={bs['unknown_units']}/{bs['total_units']} units")

    _banner("4/4 advisor")
    res = advisor.advise(d, fires, bs, client, capture_id=state.capture_id)
    meta = res["__meta__"]
    if not meta["parse_ok"]:
        print(f"  FAILED: {meta['error']}")
        return
    _pretty_recommendation(res["recommendation"])

    total_cost = (d["sources"]["vision_cost_usd"] or 0) + (meta["cost_usd"] or 0)
    print(f"\n  [pipeline: {time.time()-t0:.1f}s  |  ${total_cost:.4f}  |  "
          f"game_id={game_id}  capture_id={state.capture_id}]")
    print(f"\nPress {HOTKEY_ADVISE.upper()} again, {HOTKEY_QUIT.upper()} to quit.")


def on_start_game() -> None:
    gid = session.start_game(queue_type="ranked")
    print(f"\n>>> Game session started (game_id={gid})")


def on_end_game() -> None:
    gid = session.current_game_id()
    if gid is None:
        print("\n>>> No active game session.")
        return
    try:
        raw = input("\nFinal placement (1-8, blank to skip): ").strip()
        placement = int(raw) if raw else None
    except (ValueError, EOFError):
        placement = None
    session.end_game(final_placement=placement)
    print(f">>> Game session {gid} closed (placement={placement}).")


def main() -> None:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Copy .env.example to .env.")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    print("=" * 72)
    print("  TFT COMPANION  —  Phase B1 advisor")
    print("=" * 72)
    print(f"  {HOTKEY_ADVISE.upper()}   advise on current state")
    print(f"  {HOTKEY_START.upper()}  start a game session")
    print(f"  {HOTKEY_END.upper()}  end current game session (prompts for placement)")
    print(f"  {HOTKEY_QUIT.upper()}  quit")
    print()

    keyboard.add_hotkey(HOTKEY_ADVISE, on_advise, args=(client,))
    keyboard.add_hotkey(HOTKEY_START, on_start_game)
    keyboard.add_hotkey(HOTKEY_END, on_end_game)

    try:
        keyboard.wait(HOTKEY_QUIT)
    except KeyboardInterrupt:
        pass
    print("\nBye.")


if __name__ == "__main__":
    main()
