"""advisor.py (v2) — Haiku + tool-use narrator.

Narrates the top-3 recommendations produced by recommender.top_k(). Doesn't decide;
picks the best of the 3 using qualitative context and writes a verdict.

Switching from Sonnet (v1) to Haiku saves ~5x per call. Haiku is fine because the
hard numeric decision is already done upstream by recommender.py.

Entry points:
    advise_stream()  — generator, yields ("one_liner", str), ("reasoning", str),
                       ("final", {verdict, __meta__}) in order
    advise()         — blocking wrapper around advise_stream()
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Generator, Iterator, Optional, Tuple

_ROOT = Path(__file__).resolve().parent
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

from anthropic import Anthropic
from schemas import (
    ActionCandidate, ActionType, AdvisorVerdict, CompCandidate,
    Fire, GameState,
)
from templates import render_deterministic_verdict
import econ as econ_mod
from pool import PoolTracker
from comp_planner import load_archetypes
import knowledge as km

MODEL = "claude-haiku-4-5-20251001"
PROMPT_VERSION = "advisor_v2"

COST_INPUT_PER_MTOK = 0.80   # Haiku pricing
COST_OUTPUT_PER_MTOK = 4.00


SYSTEM = """You are a Challenger-level Teamfight Tactics coach for Set 17 "Space Gods".

You receive:
- Current game state (gold, hp, level, stage, board, traits, augments)
- Deterministic rule fires (what the engine already caught)
- Top-3 candidate actions from the recommender (each with 5 numeric scores)
- Top-3 reachable comps from the comp planner (each with p_reach, tier, etc.)

Your job:
1. Pick the best action from the provided top-3. Do NOT invent a 4th option.
2. Use qualitative context (comp cohesion, augment synergy, stage feel) to break ties.
3. Write a direct imperative verdict (<=120 chars) and 2-4 sentence reasoning.

You may call these tools to look up exact numbers for your narration:
- econ_p_hit: get P(hit) for a specific champion at current state
- comp_details: get full archetype details for a comp id

You MUST NOT invent numbers. Every number you cite must come from the provided data or a tool result.

Return ONLY a JSON object. Keys must appear in this exact order:
{
  "one_liner": "<imperative, <=120 chars>",
  "confidence": "HIGH|MEDIUM|LOW",
  "tempo_read": "AHEAD|ON_PACE|BEHIND|CRITICAL",
  "primary_action": "<ActionType of chosen candidate>",
  "chosen_candidate_index": 0,
  "reasoning": "<2-4 sentences referencing scores and comps>",
  "considerations": [],
  "warnings": [],
  "data_quality_note": null
}"""


TOOLS = [
    {
        "name": "econ_p_hit",
        "description": (
            "Compute probability of hitting a champion at current level and gold. "
            "Use when you want to confirm or cite a specific P(hit) number."
        ),
        "input_schema": {
            "type": "object",
            "required": ["champion", "gold"],
            "properties": {
                "champion": {"type": "string"},
                "gold": {"type": "integer", "minimum": 0},
            },
        },
    },
    {
        "name": "comp_details",
        "description": (
            "Get full details of a reachable archetype — core units, items, playstyle. "
            "Use when you want to reference specific units in your reasoning."
        ),
        "input_schema": {
            "type": "object",
            "required": ["archetype_id"],
            "properties": {"archetype_id": {"type": "string"}},
        },
    },
]


def _handle_tool_call(
    tool_name: str,
    tool_input: dict,
    state: GameState,
    pool: PoolTracker,
    set_,
    archetypes: list,
) -> dict:
    if tool_name == "econ_p_hit":
        try:
            pool_state = pool.to_pool_state(tool_input["champion"])
            analysis = econ_mod.analyze_roll(
                target=tool_input["champion"],
                level=state.level,
                gold=tool_input["gold"],
                pool=pool_state,
                set_=set_,
            )
            return {
                "p_hit_at_least_1": round(analysis.p_hit_at_least_1, 3),
                "p_hit_at_least_2": round(analysis.p_hit_at_least_2, 3),
                "expected_copies": round(analysis.expected_copies_seen, 2),
            }
        except Exception as e:
            return {"error": str(e)}

    if tool_name == "comp_details":
        arch = next(
            (a for a in archetypes if a.archetype_id == tool_input["archetype_id"]),
            None,
        )
        if not arch:
            return {"error": f"Unknown archetype: {tool_input['archetype_id']}"}
        return arch.model_dump()

    return {"error": f"Unknown tool: {tool_name}"}


def _build_user_payload(
    state: GameState,
    fires: list[Fire],
    actions: list[ActionCandidate],
    comps: list[CompCandidate],
) -> str:
    payload = {
        "state": {
            "stage": state.stage,
            "gold": state.gold,
            "hp": state.hp,
            "level": state.level,
            "xp": f"{state.xp_current}/{state.xp_needed}",
            "streak": state.streak,
            "augments": state.augments,
            "active_traits": [
                {"trait": t.trait, "count": t.count, "tier": t.tier}
                for t in state.active_traits
            ],
            "board": [
                {"champion": u.champion, "star": u.star, "items": u.items}
                for u in state.board
            ],
            "shop": [
                {"champion": s.champion, "cost": s.cost}
                for s in state.shop
            ],
            "item_components_on_bench": state.item_components_on_bench,
        },
        "rule_fires": [
            {"id": f.rule_id, "severity": f.severity, "action": f.action, "message": f.message}
            for f in fires
        ],
        "top_3_actions": [
            {
                "index": i,
                "action": a.action_type.value,
                "params": a.params,
                "summary": a.human_summary,
                "total_score": round(a.total_score, 3),
                "scores": {
                    "tempo": round(a.scores.tempo, 2),
                    "econ": round(a.scores.econ, 2),
                    "hp_risk": round(a.scores.hp_risk, 2),
                    "board_strength": round(a.scores.board_strength, 2),
                    "pivot_value": round(a.scores.pivot_value, 2),
                },
                "tags": a.reasoning_tags,
            }
            for i, a in enumerate(actions[:3])
        ],
        "top_3_comps": [
            {
                "id": c.archetype.archetype_id,
                "display": c.archetype.display_name,
                "tier": c.archetype.tier,
                "p_reach": round(c.p_reach, 3),
                "total_score": round(c.total_score, 3),
                "missing_units": c.missing_units[:4],
                "next_buys": c.recommended_next_buys,
            }
            for c in comps[:3]
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_complete_string_field(buf: str, key: str) -> Optional[str]:
    """Extract a fully-closed JSON string value for `key` from a streaming buffer."""
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
            try:
                return json.loads('"' + "".join(out) + '"')
            except json.JSONDecodeError:
                return None
        out.append(c)
        i += 1
    return None


def _strip_fence(raw: str) -> str:
    raw = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    return fence.group(1) if fence else raw


def _parse_verdict(recommendation: dict, actions: list[ActionCandidate]) -> Optional[AdvisorVerdict]:
    try:
        idx = int(recommendation.get("chosen_candidate_index", 0))
        idx = max(0, min(idx, len(actions) - 1))
        chosen = actions[idx]
        return AdvisorVerdict(
            one_liner=recommendation.get("one_liner", ""),
            confidence=recommendation.get("confidence", "MEDIUM"),
            tempo_read=recommendation.get("tempo_read", "ON_PACE"),
            primary_action=ActionType(recommendation.get("primary_action", "HOLD_ECON")),
            chosen_candidate=chosen,
            reasoning=recommendation.get("reasoning", ""),
            considerations=recommendation.get("considerations") or [],
            warnings=recommendation.get("warnings") or [],
            data_quality_note=recommendation.get("data_quality_note"),
        )
    except Exception:
        return None


def _advise_stream_llm(
    state: GameState,
    fires: list[Fire],
    actions: list[ActionCandidate],
    comps: list[CompCandidate],
    client: Anthropic,
    capture_id: Optional[int] = None,
    pool: Optional[PoolTracker] = None,
) -> Generator[Tuple[str, object], None, None]:
    """LLM streaming path. Called by advise_stream() — do not call directly.

    Yields ("one_liner", str), ("reasoning", str), ("final", {...}).
    Swallows internal LLM exceptions into meta["error"]; always emits final.
    """
    set_ = km.load_set(state.set_id)
    archetypes = load_archetypes()
    if pool is None:
        pool = PoolTracker(set_)

    user_text = _build_user_payload(state, fires, actions, comps)
    messages  = [{"role": "user", "content": user_text}]

    buf      = ""
    emitted: set[str] = set()
    streamable = ("one_liner", "reasoning")
    recommendation: Optional[dict] = None
    meta: dict = {
        "model": MODEL, "prompt_version": PROMPT_VERSION,
        "input_tokens": 0, "output_tokens": 0,
        "cost_usd": None, "parse_ok": False, "error": None, "elapsed_ms": 0,
        "tool_calls": 0,
    }

    t0 = time.time()

    try:
        # Agentic loop: allow the model to call tools up to 3 times.
        for _turn in range(4):
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
            )
            meta["input_tokens"] += getattr(response.usage, "input_tokens", 0)
            meta["output_tokens"] += getattr(response.usage, "output_tokens", 0)

            text_buf   = ""
            tool_uses  = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_buf += block.text
                elif block.type == "tool_use":
                    tool_uses.append(block)

            if text_buf:
                buf += text_buf
                for key in streamable:
                    if key in emitted:
                        continue
                    val = _extract_complete_string_field(buf, key)
                    if val is not None:
                        emitted.add(key)
                        yield (key, val)

            if response.stop_reason == "end_turn" or not tool_uses:
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tu in tool_uses:
                result = _handle_tool_call(tu.name, tu.input, state, pool, set_, archetypes)
                meta["tool_calls"] += 1
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                })
            messages.append({"role": "user", "content": tool_results})

        raw = _strip_fence(buf)
        if raw:
            recommendation = json.loads(raw)
            meta["parse_ok"] = True
            meta["raw_text"] = raw

    except Exception as e:
        meta["error"] = f"{type(e).__name__}: {e}"

    meta["elapsed_ms"] = int((time.time() - t0) * 1000)
    in_tok = meta["input_tokens"]
    out_tok = meta["output_tokens"]
    if in_tok and out_tok:
        meta["cost_usd"] = round(
            in_tok / 1_000_000 * COST_INPUT_PER_MTOK
            + out_tok / 1_000_000 * COST_OUTPUT_PER_MTOK, 5,
        )

    verdict = _parse_verdict(recommendation, actions) if recommendation else None
    yield ("final", {"verdict": verdict, "recommendation": recommendation, "__meta__": meta})


def advise_stream(
    state: GameState,
    fires: list[Fire],
    actions: list[ActionCandidate],
    comps: list[CompCandidate],
    client: Anthropic,
    capture_id: Optional[int] = None,
    pool: Optional[PoolTracker] = None,
) -> Generator[Tuple[str, object], None, None]:
    """Public entry point — LLM narration with deterministic fallback.

    Yields:
        ("one_liner", str)
        ("reasoning", str)
        ("final", {"verdict": AdvisorVerdict | None,
                   "recommendation": dict | None,
                   "__meta__": dict})

    If the LLM call raises any exception (timeout, API 500, network error),
    falls through to templates.render_deterministic_verdict() which produces
    a verdict string in <1ms from the same structured data. The overlay
    never hangs or shows blank on LLM failure.
    """
    try:
        yield from _advise_stream_llm(
            state, fires, actions, comps, client, capture_id, pool,
        )
    except Exception as exc:
        import logging
        logging.warning("advisor LLM failed, using deterministic fallback: %s", exc)

        top_action = actions[0] if actions else None
        top_comp   = comps[0]   if comps   else None

        if top_action is None:
            # Rare edge: recommender returned no candidates at all.
            # chosen_candidate is required by the schema, so use a safe no-op.
            from schemas import ActionScores as _AS
            top_action = ActionCandidate(
                action_type=ActionType.HOLD_ECON, params={},
                scores=_AS(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0),
                total_score=0.0, human_summary="Hold position",
            )
            safe_verdict = AdvisorVerdict(
                one_liner="Take a moment — press F9 again for advice.",
                confidence="LOW",
                tempo_read="ON_PACE",
                primary_action=ActionType.HOLD_ECON,
                chosen_candidate=top_action,
                reasoning="Recommender returned no candidates.",
                considerations=[],
                warnings=["no actions available"],
                data_quality_note="deterministic fallback; recommender empty",
            )
        else:
            safe_verdict = render_deterministic_verdict(
                state, top_action, top_comp, fires,
            )

        yield ("one_liner", safe_verdict.one_liner)
        yield ("reasoning", safe_verdict.reasoning)
        yield ("final", {
            "verdict":        safe_verdict,
            "recommendation": safe_verdict.model_dump(),
            "__meta__": {
                "source":     "deterministic_fallback",
                "error":      str(exc),
                "parse_ok":   True,   # verdict is valid, just not from LLM
            },
        })


def advise(
    state: GameState,
    fires: list[Fire],
    actions: list[ActionCandidate],
    comps: list[CompCandidate],
    client: Anthropic,
    capture_id: Optional[int] = None,
    pool: Optional[PoolTracker] = None,
) -> dict:
    """Blocking variant. Drains advise_stream() and returns the final payload."""
    out: dict = {"verdict": None, "recommendation": None, "__meta__": {}}
    for evt, payload in advise_stream(
        state, fires, actions, comps, client,
        capture_id=capture_id, pool=pool,
    ):
        if evt == "final":
            out = payload
    return out
