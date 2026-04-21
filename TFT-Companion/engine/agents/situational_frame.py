"""Agent 1 — SituationalFrame (rule-based, <10ms).

Classifies the current game state into one of 5 game tags and produces
a one-line frame sentence that sets the posture for all other agents.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import SituationalFrameResult
from engine.knowledge.loader import constants


@dataclass
class SituationalFrameInput:
    hp: int
    gold: int
    level: int
    stage: tuple[int, int]              # (stage_num, round_num)
    streak: int                         # positive = win, negative = loss
    interest_tier: int = 0              # 0-5
    augments_picked: list[str] = field(default_factory=list)
    board_strength: float = 0.5         # 0.0-1.0


class SituationalFrameAgent(AgentBase):
    name = "situational_frame"
    timeout_ms = 200

    async def _run_impl(self, ctx: Any) -> SituationalFrameResult:
        inp: SituationalFrameInput = ctx
        k = constants()
        return _compute(inp, k)

    def _fallback(self, ctx: Any) -> AgentResult:
        return SituationalFrameResult(used_fallback=True)


# ── Pure deterministic computation ────────────────────────────────────────────

def _compute(inp: SituationalFrameInput, k: dict) -> SituationalFrameResult:
    stage_str = f"{inp.stage[0]}-{inp.stage[1]}"

    # ── EV calculation ────────────────────────────────────────────────────────
    ev_base = 4.5

    if inp.stage >= (3, 1):
        hp_signal = (inp.hp - 50) / 50
        ev_base -= hp_signal * 1.0

    expected_gold = _econ_curve_at(inp.stage, k)
    if expected_gold is not None:
        gold_signal = (inp.gold - expected_gold) / 10
        ev_base -= gold_signal * 0.4

    if abs(inp.streak) >= 3:
        ev_base -= math.copysign(0.3, inp.streak)

    ev_base -= (inp.board_strength - 0.5) * 1.2

    ev_avg = max(1.5, min(7.5, ev_base))

    # ── Tags ──────────────────────────────────────────────────────────────────
    if inp.hp < 20:
        tag = "dying"
    elif ev_avg > 5.5 and inp.hp < 50:
        tag = "salvage"
    elif ev_avg <= 2.5:
        tag = "winning"
    elif ev_avg <= 4.0:
        tag = "stable"
    else:
        tag = "losing"

    # ── HP tier ───────────────────────────────────────────────────────────────
    hp_tiers = k["hp_tiers"]
    if inp.hp >= hp_tiers["healthy"]:
        hp_tier = "healthy"
    elif inp.hp >= hp_tiers["warn"]:
        hp_tier = "warn"
    elif inp.hp >= hp_tiers["danger"]:
        hp_tier = "danger"
    else:
        hp_tier = "critical"

    # ── Econ tier ─────────────────────────────────────────────────────────────
    econ_delta = inp.gold - (expected_gold or 0)
    thr = k["econ_tier_thresholds"]
    if econ_delta >= thr["ahead"]:
        econ_tier = "ahead"
    elif econ_delta >= thr["on_curve"]:
        econ_tier = "on_curve"
    elif econ_delta >= thr["behind"]:
        econ_tier = "behind"
    else:
        econ_tier = "broken"

    # ── Posture ───────────────────────────────────────────────────────────────
    posture_map = {
        "winning": "greed",
        "stable": "stabilize",
        "losing": "stabilize",
        "salvage": "salvage",
        "dying": "all_in",
    }
    frame_posture = posture_map[tag]

    # ── Top signal ────────────────────────────────────────────────────────────
    top_signal = _top_signal(inp, econ_delta, expected_gold)

    # ── Frame sentence ────────────────────────────────────────────────────────
    templates = k.get("frame_templates", {})
    frame_sentence = _build_sentence(tag, ev_avg, inp, stage_str, top_signal, templates)

    # ── Confidence decreases in early stages ─────────────────────────────────
    if inp.stage[0] < 2:
        ev_confidence = 0.3
    elif inp.stage[0] == 2:
        ev_confidence = 0.5
    else:
        ev_confidence = 0.7

    return SituationalFrameResult(
        game_tag=tag,
        ev_avg_placement=round(ev_avg, 2),
        ev_confidence=ev_confidence,
        hp_tier=hp_tier,
        econ_tier=econ_tier,
        frame_sentence=frame_sentence,
        frame_posture=frame_posture,
        top_signal=top_signal,
    )


def _econ_curve_at(stage: tuple[int, int], k: dict) -> float | None:
    """Find expected gold for the given stage from econ_curve.

    Falls back to nearest previous entry if exact key missing.
    """
    curve: dict[str, float] = k["econ_curve"]
    exact = f"{stage[0]}-{stage[1]}"
    if exact in curve:
        return float(curve[exact])
    # scan backwards for nearest defined entry
    s, r = stage
    for rr in range(r - 1, 0, -1):
        key = f"{s}-{rr}"
        if key in curve:
            return float(curve[key])
    for ss in range(s - 1, 0, -1):
        for rr in range(7, 0, -1):
            key = f"{ss}-{rr}"
            if key in curve:
                return float(curve[key])
    return None


def _top_signal(inp: SituationalFrameInput, econ_delta: float, expected_gold: float | None) -> str:
    contributions = []
    if inp.stage >= (3, 1):
        hp_signal = abs(inp.hp - 50) / 50
        contributions.append((hp_signal * 1.0, "HP pressure" if inp.hp < 50 else "HP lead"))
    if expected_gold is not None:
        contributions.append((abs(econ_delta) / 10 * 0.4, "below econ curve" if econ_delta < 0 else "ahead of curve"))
    if abs(inp.streak) >= 3:
        contributions.append((0.3, "win streak" if inp.streak > 0 else "loss streak"))
    contributions.append((abs(inp.board_strength - 0.5) * 1.2, "board strength" if inp.board_strength > 0.5 else "weak board"))
    if not contributions:
        return ""
    contributions.sort(key=lambda x: x[0], reverse=True)
    return contributions[0][1]


def _build_sentence(
    tag: str,
    ev_avg: float,
    inp: SituationalFrameInput,
    stage_str: str,
    top_signal: str,
    templates: dict,
) -> str:
    ev = round(ev_avg, 1)
    reason = top_signal or "standard line"
    stage = stage_str

    if tag == "winning":
        t = templates.get("winning", "Win streak — push tempo. EV ≈ {ev}.")
        return t.format(ev=ev, reason=reason, hp=inp.hp, stage=stage)
    elif tag == "stable":
        t = templates.get("stable_on_curve", templates.get("stable", "On curve — standard leveling. EV ≈ {ev}."))
        return t.format(ev=ev, reason=reason, focus=reason, hp=inp.hp, stage=stage)
    elif tag == "losing":
        t = templates.get("losing_healthy", templates.get("losing", "Behind tempo — play for top 4. EV ≈ {ev}."))
        return t.format(ev=ev, reason=reason, hp=inp.hp, stage=stage)
    elif tag == "salvage":
        t = templates.get("salvage", "Salvage mode — {reason}, minimize HP bleed. EV ≈ {ev}.")
        return t.format(ev=ev, reason=reason, hp=inp.hp, stage=stage)
    else:  # dying
        t = templates.get("dying", "Critical — spend everything on stage {stage} stabilization.")
        return t.format(ev=ev, reason=reason, hp=inp.hp, stage=stage)
