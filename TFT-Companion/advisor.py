"""Claude reasoning layer.

Ingests: merged state + rule fires + board-strength score.
Outputs:  structured JSON recommendation.

This is the TOP of the decision pyramid:
    LCU + Vision + templates → state
    state → rules → fires
    state → scoring → board_strength
    state + fires + board_strength → THIS LAYER → play

Kept deliberately cheap: Sonnet 4.6, text-only (no re-sending screenshot),
short system prompt, strict JSON output.

Logged to vision_calls table with prompt_version="advisor_v1".
"""

from __future__ import annotations

import json
import re
from typing import Optional

from anthropic import Anthropic

import db


MODEL = "claude-sonnet-4-6"
PROMPT_VERSION = "advisor_v1"

COST_INPUT_PER_MTOK = 3.0
COST_OUTPUT_PER_MTOK = 15.0


SYSTEM = """You are a Challenger-level Teamfight Tactics coach specialized in Set 17 "Space Gods".

You receive a JSON object with: current game state, pre-computed deterministic rule fires,
and a board-strength score (0–100 relative to ideal for the stage).

You return ONLY a JSON object (no prose, no markdown fences) with this shape:

{
  "primary_action": "<ROLL_DOWN|LEVEL_UP|HOLD_ECON|COMMIT_DIRECTION|PLAN_GOD_PICK|SCOUT|POSITION|OTHER>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "one_liner": "<one-sentence call, imperative, <=120 chars>",
  "reasoning": "<2–4 sentences explaining the WHY — tempo, HP, econ, contested, augment-path>",
  "considerations": ["<short secondary point>", ...],
  "warnings": ["<short warning if any>", ...],
  "tempo_read": "<AHEAD|ON_PACE|BEHIND|CRITICAL> — relative to peers at this stage",
  "data_quality_note": "<if board units are 'Unknown' or key fields missing, say so; else null>"
}

Rules:
- Be direct. Challenger coach tone, not hedging.
- If board_strength.confidence is LOW (many unknown units), explicitly call that out in data_quality_note
  and drop your overall confidence to LOW unless rules alone are decisive.
- If HP_URGENT rule fired, primary_action is almost always ROLL_DOWN regardless of other signals.
- Reference Set 17 mechanics naturally (Realm of the Gods at 4-7, Kayle's Radiant boon,
  Meeple synergy, N.O.V.A., Psionic items, lose-streak gold bonus is new in Space Gods).
- Do NOT invent champions or items — use what's in the state.
- Output must be valid JSON parseable by json.loads."""


def _build_user_payload(state: dict, rule_fires: list, board_strength: dict) -> str:
    compact_state = {
        "stage": state.get("stage"),
        "gold": state.get("gold"),
        "hp": state.get("hp"),
        "level": state.get("level"),
        "xp": state.get("xp"),
        "streak": state.get("streak"),
        "augments": state.get("augments") or [],
        "active_traits": state.get("active_traits") or [],
        "board_units": [
            {"champion": u.get("champion"), "star": u.get("star"),
             "items": u.get("items") or []}
            for u in (state.get("board") or [])
        ],
        "bench": state.get("bench") or [],
        "shop": state.get("shop") or [],
    }
    fires_out = [
        {"id": f.rule_id, "severity": f.severity, "action": f.action,
         "message": f.message}
        for f in rule_fires
    ]
    payload = {
        "state": compact_state,
        "rule_fires": fires_out,
        "board_strength": {
            "score": board_strength.get("score"),
            "expected_raw": board_strength.get("expected_raw"),
            "raw": board_strength.get("raw"),
            "confidence": board_strength.get("confidence"),
            "unknown_units": board_strength.get("unknown_units"),
            "active_traits": board_strength.get("active_traits"),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def advise(state: dict, rule_fires: list, board_strength: dict,
           client: Anthropic, capture_id: Optional[int] = None) -> dict:
    """Call Claude, parse, log. Returns recommendation dict with __meta__ key for caller."""
    user_text = _build_user_payload(state, rule_fires, board_strength)

    out = {
        "recommendation": None,
        "__meta__": {
            "model": MODEL, "prompt_version": PROMPT_VERSION,
            "input_tokens": None, "output_tokens": None, "cost_usd": None,
            "parse_ok": False, "error": None, "elapsed_ms": 0,
        },
    }

    with db.Timer() as t:
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=1024, system=SYSTEM,
                messages=[{"role": "user", "content": user_text}],
            )
            in_tok = getattr(resp.usage, "input_tokens", None)
            out_tok = getattr(resp.usage, "output_tokens", None)
            out["__meta__"]["input_tokens"] = in_tok
            out["__meta__"]["output_tokens"] = out_tok
            if in_tok is not None and out_tok is not None:
                out["__meta__"]["cost_usd"] = round(
                    in_tok / 1_000_000 * COST_INPUT_PER_MTOK
                    + out_tok / 1_000_000 * COST_OUTPUT_PER_MTOK, 4,
                )

            raw = resp.content[0].text.strip()
            fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
            if fence:
                raw = fence.group(1)
            out["recommendation"] = json.loads(raw)
            out["__meta__"]["parse_ok"] = True
            out["__meta__"]["raw_text"] = raw
        except Exception as e:
            out["__meta__"]["error"] = f"{type(e).__name__}: {e}"
    out["__meta__"]["elapsed_ms"] = t.ms

    if capture_id is not None:
        meta = out["__meta__"]
        db.log_vision_call(
            capture_id=capture_id, model=MODEL, prompt_version=PROMPT_VERSION,
            response_json=meta.get("raw_text"),
            parse_ok=meta["parse_ok"],
            input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"],
            cost_usd=meta["cost_usd"], error=meta["error"],
            elapsed_ms=meta["elapsed_ms"],
        )

    return out
