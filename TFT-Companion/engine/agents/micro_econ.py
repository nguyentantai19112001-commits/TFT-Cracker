"""Agent 5 — MicroEcon (rule-based, pure arithmetic, <5ms).

Computes exact gold/XP math for level-up, roll-down, and hold scenarios
so the player never has to do mental arithmetic mid-game.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import EconScenario, EconSnapshot, MicroEconResult
from engine.knowledge.loader import constants, interest_for_gold, streak_bonus_for, xp_to_next


@dataclass
class MicroEconInput:
    gold: int
    level: int
    streak: int                      # positive = win, negative = loss
    stage: tuple[int, int]
    target_levels: list[int] = field(default_factory=list)  # levels to evaluate (e.g. [8, 9])
    roll_amounts: list[int] = field(default_factory=list)   # gold to spend rolling


class MicroEconAgent(AgentBase):
    name = "micro_econ"
    timeout_ms = 100

    async def _run_impl(self, ctx: Any) -> MicroEconResult:
        inp: MicroEconInput = ctx
        return _compute(inp)

    def _fallback(self, ctx: Any) -> AgentResult:
        return MicroEconResult(used_fallback=True)


# ── Pure deterministic computation ────────────────────────────────────────────

def _compute(inp: MicroEconInput) -> MicroEconResult:
    k = constants()
    streak = streak_bonus_for(inp.streak, k)
    base = _base_income(inp.stage, k)
    interest_now = interest_for_gold(inp.gold, k)

    current = EconSnapshot(
        gold=inp.gold,
        level=inp.level,
        streak=inp.streak,
        stage=inp.stage,
        interest=interest_now,
        econ_tier=_econ_tier(inp.gold),
    )

    scenarios: list[EconScenario] = []

    # Hold scenario
    hold_gold_after = inp.gold + base + streak + interest_now
    hold_interest_after = interest_for_gold(hold_gold_after, k)
    scenarios.append(EconScenario(
        id="hold",
        action="Hold — build interest",
        gold_before=inp.gold,
        gold_after=hold_gold_after,
        interest_delta=interest_for_gold(hold_gold_after, k) - interest_now,
        opportunity_cost=0.0,
        recommendation_score=_hold_score(inp),
    ))

    # Level scenarios
    for target in inp.target_levels:
        if target <= inp.level or target > 11:
            continue
        s = _level_scenario(inp, target, base, streak, interest_now, k)
        if s is not None:
            scenarios.append(s)

    # Roll scenarios
    for roll_gold in inp.roll_amounts:
        if roll_gold <= 0 or roll_gold > inp.gold:
            continue
        s = _roll_scenario(inp, roll_gold, base, streak, interest_now, k)
        scenarios.append(s)

    # Rank by recommendation_score
    scenarios.sort(key=lambda s: s.recommendation_score, reverse=True)
    best = scenarios[0].id if scenarios else "hold"

    one_liner = _build_one_liner(scenarios[0] if scenarios else None, inp)

    return MicroEconResult(
        current=current,
        scenarios=scenarios,
        best_scenario=best,
        one_liner=one_liner,
    )


def _level_scenario(
    inp: MicroEconInput,
    target: int,
    base: int,
    streak_bonus: int,
    interest_now: int,
    k: dict,
) -> EconScenario | None:
    xp_needed = _xp_between(inp.level, target)
    if xp_needed <= 0:
        return None
    # XP is bought in 4-XP chunks at 4g each
    gold_cost = math.ceil(xp_needed / 4) * 4
    if gold_cost > inp.gold:
        return None

    gold_after = inp.gold - gold_cost
    interest_after = interest_for_gold(gold_after, k)
    next_gold = gold_after + base + streak_bonus + interest_after

    interest_lost = max(0, interest_now - interest_after)
    hold_gold_next = inp.gold + base + streak_bonus + interest_now
    opp_cost = hold_gold_next - next_gold

    score = _level_score(inp, target, interest_lost, opp_cost)

    return EconScenario(
        id=f"level_{target}",
        action=f"Level to {target}",
        gold_before=inp.gold,
        gold_after=gold_after,
        interest_delta=-interest_lost,
        opportunity_cost=round(opp_cost, 2),
        recommendation_score=score,
    )


def _roll_scenario(
    inp: MicroEconInput,
    roll_gold: int,
    base: int,
    streak_bonus: int,
    interest_now: int,
    k: dict,
) -> EconScenario:
    gold_after = inp.gold - roll_gold
    interest_after = interest_for_gold(gold_after, k)
    next_gold = gold_after + base + streak_bonus + interest_after

    interest_lost = max(0, interest_now - interest_after)
    hold_gold_next = inp.gold + base + streak_bonus + interest_now
    opp_cost = hold_gold_next - next_gold

    score = _roll_score(inp, roll_gold, interest_lost)

    return EconScenario(
        id=f"roll_{roll_gold}",
        action=f"Roll {roll_gold}g",
        gold_before=inp.gold,
        gold_after=gold_after,
        interest_delta=-interest_lost,
        opportunity_cost=round(opp_cost, 2),
        recommendation_score=score,
    )


def _base_income(stage: tuple[int, int], k: dict) -> int:
    """Gold earned at end of round (base, not counting interest or streak)."""
    tbl = k["base_income_per_round"]
    stage_str = f"{stage[0]}-{stage[1]}"
    if stage_str in tbl:
        return int(tbl[stage_str])
    # 2-2+ means 5g from stage 2-2 onward
    if stage >= (2, 2):
        return int(tbl.get("2-2+", 5))
    return 0


def _xp_between(current_level: int, target_level: int) -> int:
    """Total XP needed to go from current_level to target_level."""
    total = 0
    for lvl in range(current_level, target_level):
        total += xp_to_next(lvl)
    return total


def _econ_tier(gold: int) -> str:
    if gold >= 50:
        return "ahead"
    elif gold >= 30:
        return "on_curve"
    elif gold >= 10:
        return "behind"
    return "broken"


def _hold_score(inp: MicroEconInput) -> float:
    # Holding is better when gold is near an interest breakpoint
    tier = inp.gold // 10
    breakpoint_dist = (inp.gold % 10)
    if breakpoint_dist >= 8:
        return 0.85  # very close to next interest tier, hold to get it
    if inp.gold >= 50:
        return 0.70  # already at max interest
    return 0.50


def _level_score(inp: MicroEconInput, target: int, interest_lost: int, opp_cost: float) -> float:
    base = 0.7
    # Penalize if we lose interest tiers
    base -= interest_lost * 0.08
    # Penalize high opportunity cost
    base -= min(0.3, opp_cost * 0.02)
    # Reward leveling to power spikes
    if target == 8:
        base += 0.15
    elif target == 9:
        base += 0.10
    return round(max(0.0, min(1.0, base)), 4)


def _roll_score(inp: MicroEconInput, roll_gold: int, interest_lost: int) -> float:
    base = 0.6
    base -= interest_lost * 0.10
    fraction = roll_gold / max(1, inp.gold)
    base -= fraction * 0.2
    return round(max(0.0, min(1.0, base)), 4)


def _build_one_liner(best: EconScenario | None, inp: MicroEconInput) -> str:
    if best is None:
        return "Hold current gold."
    if best.id == "hold":
        return f"Hold — {inp.gold}g, {interest_for_gold(inp.gold)} interest next round."
    if best.id.startswith("level_"):
        target = best.id.split("_")[1]
        return (
            f"Level to {target} costs {best.gold_before - best.gold_after}g "
            f"— leaves {best.gold_after}g, {abs(best.interest_delta)} interest tier change."
        )
    if best.id.startswith("roll_"):
        roll_g = best.gold_before - best.gold_after
        return f"Roll {roll_g}g — remaining {best.gold_after}g."
    return best.action
