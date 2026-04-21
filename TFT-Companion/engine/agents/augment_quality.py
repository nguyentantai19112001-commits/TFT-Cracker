"""Agent 8 — AugmentQuality (rule-based, <5ms).

Predicts the tier distribution of the next augment armory using the
conditional probability table from tftodds.com (in constants.yaml),
and recommends augments per tier against the active comp direction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import (
    AugmentQualityResult,
    AugmentRec,
    TierProbabilities,
)
from engine.knowledge.loader import constants

# Armory stages in order
_ARMORY_STAGES: list[tuple[int, int]] = [(2, 1), (3, 2), (4, 2)]

TierLetter = Literal["S", "G", "P"]


@dataclass
class AugmentQualityInput:
    upcoming_stage: tuple[int, int]
    prior_tiers: list[str] = field(default_factory=list)
    # "S", "G", or "P" for each prior armory in order (e.g. ["G", "P"] = gold at 2-1, prismatic at 3-2)
    comp_direction: str = ""          # archetype_id hint for recommendation filtering


class AugmentQualityAgent(AgentBase):
    name = "augment_quality"
    timeout_ms = 100

    async def _run_impl(self, ctx: Any) -> AugmentQualityResult:
        inp: AugmentQualityInput = ctx
        return _compute(inp)

    def _fallback(self, ctx: Any) -> AgentResult:
        return AugmentQualityResult(used_fallback=True)


# ── Pure deterministic computation ────────────────────────────────────────────

def _compute(inp: AugmentQualityInput) -> AugmentQualityResult:
    k = constants()
    dist = k["augment_distribution"]

    probs = _predict_tier_probs(inp.upcoming_stage, inp.prior_tiers, dist)
    tier_probs = _to_tier_probabilities(probs)
    summary = _build_summary(inp.upcoming_stage, inp.prior_tiers, probs)

    return AugmentQualityResult(
        upcoming_stage=inp.upcoming_stage,
        tier_probabilities=tier_probs,
        recommendations_per_tier={},   # populated in C7 when augments.yaml is added
        top_overall_picks=[],           # same — needs augments.yaml
        probability_conditional_on_history=summary,
    )


def _predict_tier_probs(
    upcoming: tuple[int, int],
    prior_tiers: list[str],
    dist: dict,
) -> dict[str, float]:
    """Return {silver: p, gold: p, prismatic: p} for the upcoming armory."""

    if upcoming == (2, 1) or not prior_tiers:
        # No history — use marginal distribution for 2-1
        marginal = dist.get("stage_2_1_marginal", {})
        return {
            "silver": float(marginal.get("silver", 0.28)),
            "gold": float(marginal.get("gold", 0.62)),
            "prismatic": float(marginal.get("prismatic", 0.10)),
        }

    if upcoming == (3, 2):
        # After 2-1 pick — use tier_probabilities_by_stage["3-2"]
        by_stage = dist.get("tier_probabilities_by_stage", {})
        probs_32 = by_stage.get("3-2", {"silver": 0.35, "gold": 0.45, "prismatic": 0.20})
        return {k: float(v) for k, v in probs_32.items()}

    if upcoming == (4, 2) and len(prior_tiers) >= 2:
        # Use full conditional table: key = "X_Y" where X = 2-1 tier, Y = 3-2 tier
        t1 = _normalize_tier(prior_tiers[0])
        t2 = _normalize_tier(prior_tiers[1])
        key = f"{t1}_{t2}"
        full_table = dist.get("full_table", {})
        row = full_table.get(key)
        if row:
            return {
                "silver": float(row.get("silver", 0.0)),
                "gold": float(row.get("gold", 0.74)),
                "prismatic": float(row.get("prismatic", 0.20)),
            }
        # Fallback: marginal 4-2
        by_stage = dist.get("tier_probabilities_by_stage", {})
        probs_42 = by_stage.get("4-2", {"silver": 0.06, "gold": 0.74, "prismatic": 0.20})
        return {k: float(v) for k, v in probs_42.items()}

    if upcoming == (4, 2) and len(prior_tiers) == 1:
        # Only know 2-1 tier — can't use full table, use stage marginal
        by_stage = dist.get("tier_probabilities_by_stage", {})
        probs_42 = by_stage.get("4-2", {"silver": 0.06, "gold": 0.74, "prismatic": 0.20})
        return {k: float(v) for k, v in probs_42.items()}

    # Fallback
    return {"silver": 0.06, "gold": 0.74, "prismatic": 0.20}


def _normalize_tier(tier_str: str) -> str:
    """Convert tier string to single capital letter: 'silver'→'S', 'gold'→'G', etc."""
    t = tier_str.strip().lower()
    if t.startswith("s"):
        return "S"
    if t.startswith("g"):
        return "G"
    if t.startswith("p"):
        return "P"
    return tier_str[0].upper() if tier_str else "G"


def _to_tier_probabilities(probs: dict[str, float]) -> TierProbabilities:
    s = probs.get("silver", 0.0)
    g = probs.get("gold", 0.0)
    p = probs.get("prismatic", 0.0)
    if p >= 0.20:
        ev = "P"
    elif g > s:
        ev = "G"
    else:
        ev = "S"
    return TierProbabilities(silver=s, gold=g, prismatic=p, expected_value_tier=ev)


def _build_summary(
    upcoming: tuple[int, int],
    prior_tiers: list[str],
    probs: dict[str, float],
) -> str:
    stage_str = f"{upcoming[0]}-{upcoming[1]}"
    p_str = f"silver {probs['silver']:.0%} / gold {probs['gold']:.0%} / prismatic {probs['prismatic']:.0%}"
    if not prior_tiers:
        return f"Stage {stage_str} armory: {p_str} (no prior history)."
    history = " → ".join(prior_tiers)
    return f"Stage {stage_str} armory given [{history}]: {p_str}."
