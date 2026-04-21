"""Agent 6 — ItemEconomy (Haiku LLM, <2s).

Decides slam_now / hold / gamble for current bench components.
Rule pre-filter handles clear-cut cases; Haiku resolves ambiguous ones.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

import anthropic

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import ItemEconomyResult, ItemSlamRec

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"


class ItemEconomyAgent(AgentBase):
    name = "item_economy"
    timeout_ms = 2000

    async def _run_impl(self, ctx: Any) -> ItemEconomyResult:
        rule = _rule_filter(ctx)
        if rule is not None:
            return rule
        return await _llm_item_econ(ctx)

    def _fallback(self, ctx: Any) -> AgentResult:
        rule = _rule_filter(ctx)
        if rule is not None:
            return rule
        return ItemEconomyResult(
            agent_name="item_economy",
            used_fallback=True,
            decision="hold",
            hold_reason="Fallback: hold components.",
            reasoning="Agent failed — defaulting to hold.",
            risk_tag="safe",
        )


def _rule_filter(ctx: Any) -> ItemEconomyResult | None:
    """Return a deterministic decision when one clearly applies; None otherwise."""
    bench = ctx.bench_components or []
    stage_major = ctx.stage[0]

    # Never slam: too few components and too early
    if len(bench) <= 2 and stage_major < 3:
        return ItemEconomyResult(
            agent_name="item_economy",
            decision="hold",
            hold_reason="Early game — preserve components for better items.",
            reasoning="Too few components and too early to commit.",
            risk_tag="safe",
        )

    best_slam = _find_best_slam(ctx)

    # Always slam: HP critical — stabilize now
    if ctx.hp < 40 and stage_major >= 3 and best_slam is not None:
        return ItemEconomyResult(
            agent_name="item_economy",
            decision="slam_now",
            slam=best_slam,
            reasoning=f"HP {ctx.hp} — slam now to stabilize.",
            risk_tag="moderate",
        )

    # Always slam: winning streak — capitalize lead
    if ctx.streak >= 3 and ctx.hp > 60 and best_slam is not None:
        return ItemEconomyResult(
            agent_name="item_economy",
            decision="slam_now",
            slam=best_slam,
            reasoning=f"Streak {ctx.streak} — slam to extend lead.",
            risk_tag="safe",
        )

    # Always slam: 2★ carry missing last BIS item
    last_item = _find_two_star_last_item(ctx)
    if last_item is not None:
        return ItemEconomyResult(
            agent_name="item_economy",
            decision="slam_now",
            slam=last_item,
            reasoning="2★ carry missing last BIS item — complete now.",
            risk_tag="safe",
        )

    return None  # ambiguous — send to LLM


async def _llm_item_econ(ctx: Any) -> ItemEconomyResult:
    client = anthropic.AsyncAnthropic()
    msg = await client.messages.create(
        model=_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": _build_prompt(ctx)}],
    )
    return _parse_llm_response(msg.content[0].text, ctx)


def _build_prompt(ctx: Any) -> str:
    bench = ctx.bench_components or []
    board_lines = []
    for slot in (ctx.board_slots or []):
        name = slot.get("display_name") or slot.get("api_name", "?")
        star = slot.get("star", 1)
        items = slot.get("items_held", [])
        trios = slot.get("bis_trios", [])
        bis_str = " / ".join(trios[0]) if trios else "?"
        board_lines.append(f"  {name}({star}★): holding {items}, BIS={bis_str}")

    board_str = "\n".join(board_lines) if board_lines else "  (empty)"

    return f"""You are a TFT item economy coach. Decide: slam an item now, hold, or gamble?

State:
- HP: {ctx.hp} | Stage: {ctx.stage[0]}-{ctx.stage[1]} | Streak: {ctx.streak}
- Bench components: {bench}

Board:
{board_str}

Return ONLY valid JSON (no markdown):
{{"decision": "slam_now", "item_id": "...", "holder_api": "...", "holder_display": "...", "reasoning": "one sentence", "risk_tag": "safe"}}

decision must be one of: slam_now, hold, gamble
risk_tag must be one of: safe, moderate, risky
If decision is hold or gamble, item_id and holder_api can be empty strings."""


def _parse_llm_response(raw: str, ctx: Any) -> ItemEconomyResult:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON")
        data = json.loads(raw[start:end])

        decision = data.get("decision", "hold")
        if decision not in ("slam_now", "hold", "gamble"):
            decision = "hold"

        risk_tag = data.get("risk_tag", "safe")
        if risk_tag not in ("safe", "moderate", "risky"):
            risk_tag = "safe"

        reasoning = data.get("reasoning", "")

        slam = None
        if decision == "slam_now":
            item_id = data.get("item_id", "")
            holder_api = data.get("holder_api", "")
            holder_display = data.get("holder_display", "")
            if item_id:
                comps = (ctx.item_recipes or {}).get(item_id, [])
                slam = ItemSlamRec(
                    item_id=item_id,
                    components_used=list(comps),
                    holder_api=holder_api,
                    holder_display=holder_display,
                )

        return ItemEconomyResult(
            agent_name="item_economy",
            decision=decision,
            slam=slam,
            hold_reason=reasoning if decision == "hold" else None,
            reasoning=reasoning,
            risk_tag=risk_tag,
        )
    except Exception as exc:
        log.warning("ItemEconomy parse failed: %s | raw=%.200s", exc, raw)
        return ItemEconomyResult(
            agent_name="item_economy",
            used_fallback=True,
            decision="hold",
            hold_reason="Parse error.",
            reasoning="Parse error — defaulting to hold.",
            risk_tag="safe",
        )


def _find_best_slam(ctx: Any) -> ItemSlamRec | None:
    """Find the highest-priority item buildable from bench components."""
    bench = Counter(ctx.bench_components or [])
    recipes = ctx.item_recipes or {}
    board = ctx.board_slots or []

    if not bench or not recipes or not board:
        return None

    value_order = {"S": 4, "A": 3, "B": 2, "C": 1}
    best_score = -1
    best: tuple | None = None

    for item_id, comps in recipes.items():
        if len(comps) != 2:
            continue
        c1, c2 = comps
        if c1 == c2:
            if bench.get(c1, 0) < 2:
                continue
        else:
            if bench.get(c1, 0) < 1 or bench.get(c2, 0) < 1:
                continue

        for slot in board:
            items_held = slot.get("items_held", [])
            if item_id in items_held:
                continue
            bis_trios = slot.get("bis_trios", [])
            value_class = slot.get("value_class", "C")
            in_bis = any(item_id in trio for trio in bis_trios)

            score = value_order.get(value_class, 1) + (10 if in_bis else 0)
            if score > best_score:
                best_score = score
                best = (item_id, comps, slot, in_bis)

    if best is None:
        return None

    item_id, comps, slot, is_bis = best
    return ItemSlamRec(
        item_id=item_id,
        components_used=list(comps),
        holder_api=slot.get("api_name", ""),
        holder_display=slot.get("display_name", ""),
        is_bis=is_bis,
        value_estimate=slot.get("value_class", "B"),
    )


def _find_two_star_last_item(ctx: Any) -> ItemSlamRec | None:
    """Find a 2★ unit holding exactly 2 BIS items and missing 1 that's buildable now."""
    bench = Counter(ctx.bench_components or [])
    recipes = ctx.item_recipes or {}

    for slot in (ctx.board_slots or []):
        if slot.get("star", 1) < 2:
            continue
        items_held = slot.get("items_held", [])
        if len(items_held) != 2:
            continue

        for trio in slot.get("bis_trios", []):
            missing = [item for item in trio if item not in items_held]
            if len(missing) != 1:
                continue
            needed = missing[0]
            comps = recipes.get(needed, [])
            if len(comps) != 2:
                continue
            c1, c2 = comps
            can_build = (
                bench.get(c1, 0) >= 2 if c1 == c2
                else bench.get(c1, 0) >= 1 and bench.get(c2, 0) >= 1
            )
            if can_build:
                return ItemSlamRec(
                    item_id=needed,
                    components_used=list(comps),
                    holder_api=slot.get("api_name", ""),
                    holder_display=slot.get("display_name", ""),
                    is_bis=True,
                    value_estimate=slot.get("value_class", "B"),
                )

    return None
