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

Two entry points:
    advise()          — blocking, returns full dict when done. Used by tests.
    advise_stream()   — generator. Yields ("one_liner", txt), ("reasoning", txt),
                        ("final", full_dict) as they arrive. Used by live loop.

Both log to vision_calls with prompt_version="advisor_v1".
"""

from __future__ import annotations

import json
import re
from typing import Generator, Optional, Tuple

from anthropic import Anthropic

import db


MODEL = "claude-sonnet-4-6"
PROMPT_VERSION = "advisor_v1"

COST_INPUT_PER_MTOK = 3.0
COST_OUTPUT_PER_MTOK = 15.0


SYSTEM = """You are a Challenger-level Teamfight Tactics coach specialized in Set 17 "Space Gods".

You receive a JSON object with: current game state, pre-computed deterministic rule fires,
and a board-strength score (0–100 relative to ideal for the stage).

You return ONLY a JSON object (no prose, no markdown fences). The keys MUST appear in this
exact order — the client streams output and relies on one_liner and reasoning arriving first:

{
  "one_liner": "<one-sentence call, imperative, <=120 chars>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "tempo_read": "<AHEAD|ON_PACE|BEHIND|CRITICAL> — relative to peers at this stage",
  "primary_action": "<ROLL_DOWN|LEVEL_UP|HOLD_ECON|COMMIT_DIRECTION|PLAN_GOD_PICK|SCOUT|POSITION|OTHER>",
  "reasoning": "<2–4 sentences explaining the WHY — tempo, HP, econ, contested, augment-path>",
  "considerations": ["<short secondary point>", ...],
  "warnings": ["<short warning if any>", ...],
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


def _strip_fence(raw: str) -> str:
    raw = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    return fence.group(1) if fence else raw


# Matches a complete "key": "value" pair where the value string has fully closed.
# Handles escaped quotes inside the string.
def _extract_complete_string_field(buf: str, key: str) -> Optional[str]:
    """Return the complete string value for `key` if present in buf, else None.

    We scan for `"key":` then walk through the following string literal
    tracking escapes. Returns None until the closing unescaped `"` arrives.
    """
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*"')
    m = pattern.search(buf)
    if not m:
        return None
    i = m.end()
    out = []
    n = len(buf)
    while i < n:
        c = buf[i]
        if c == "\\" and i + 1 < n:
            out.append(buf[i:i + 2])
            i += 2
            continue
        if c == '"':
            # Closed. Convert the raw JSON string chunk back via json.loads
            # to handle \n \t \" etc.
            try:
                return json.loads('"' + "".join(out) + '"')
            except json.JSONDecodeError:
                return None
        out.append(c)
        i += 1
    return None  # still open


def advise_stream(state: dict, rule_fires: list, board_strength: dict,
                  client: Anthropic, capture_id: Optional[int] = None,
                  ) -> Generator[Tuple[str, object], None, None]:
    """Stream the advisor call. Yields events for progressive UX + a final dict.

    Event stream:
        ("one_liner", text)   — emitted once as soon as the one_liner JSON string closes
        ("reasoning", text)   — emitted once once the reasoning string closes
        ("final", payload)    — terminal event with the full parsed recommendation + meta
    """
    user_text = _build_user_payload(state, rule_fires, board_strength)
    buf = ""
    emitted: set[str] = set()
    streamable = ("one_liner", "reasoning")

    meta: dict = {
        "model": MODEL, "prompt_version": PROMPT_VERSION,
        "input_tokens": None, "output_tokens": None, "cost_usd": None,
        "parse_ok": False, "error": None, "elapsed_ms": 0,
    }
    recommendation: Optional[dict] = None

    with db.Timer() as t:
        try:
            with client.messages.stream(
                model=MODEL, max_tokens=1024, system=SYSTEM,
                messages=[{"role": "user", "content": user_text}],
            ) as stream:
                for chunk in stream.text_stream:
                    buf += chunk
                    for key in streamable:
                        if key in emitted:
                            continue
                        val = _extract_complete_string_field(buf, key)
                        if val is not None:
                            emitted.add(key)
                            yield (key, val)
                final_msg = stream.get_final_message()

            in_tok = getattr(final_msg.usage, "input_tokens", None)
            out_tok = getattr(final_msg.usage, "output_tokens", None)
            meta["input_tokens"] = in_tok
            meta["output_tokens"] = out_tok
            if in_tok is not None and out_tok is not None:
                meta["cost_usd"] = round(
                    in_tok / 1_000_000 * COST_INPUT_PER_MTOK
                    + out_tok / 1_000_000 * COST_OUTPUT_PER_MTOK, 4,
                )

            raw = _strip_fence(buf)
            recommendation = json.loads(raw)
            meta["parse_ok"] = True
            meta["raw_text"] = raw
        except Exception as e:
            meta["error"] = f"{type(e).__name__}: {e}"
    meta["elapsed_ms"] = t.ms

    if capture_id is not None:
        db.log_vision_call(
            capture_id=capture_id, model=MODEL, prompt_version=PROMPT_VERSION,
            response_json=meta.get("raw_text"),
            parse_ok=meta["parse_ok"],
            input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"],
            cost_usd=meta["cost_usd"], error=meta["error"],
            elapsed_ms=meta["elapsed_ms"],
        )

    yield ("final", {"recommendation": recommendation, "__meta__": meta})


def advise(state: dict, rule_fires: list, board_strength: dict,
           client: Anthropic, capture_id: Optional[int] = None) -> dict:
    """Blocking variant. Drains advise_stream() and returns final payload.

    Kept for tests and non-interactive callers. Same result shape as before.
    """
    out = {
        "recommendation": None,
        "__meta__": {
            "model": MODEL, "prompt_version": PROMPT_VERSION,
            "input_tokens": None, "output_tokens": None, "cost_usd": None,
            "parse_ok": False, "error": None, "elapsed_ms": 0,
        },
    }
    for evt, payload in advise_stream(state, rule_fires, board_strength,
                                      client, capture_id=capture_id):
        if evt == "final":
            out = payload  # type: ignore[assignment]
    return out
