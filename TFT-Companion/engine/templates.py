"""templates.py — Deterministic verdict renderer.

Used as a fallback when the advisor LLM call times out or errors. Produces
a plain-English verdict from the top-ranked ActionCandidate and CompCandidate
without any LLM involvement.

Output quality is lower than the LLM version (no qualitative context, no
augment synergy reasoning) but it's fast (<1ms), deterministic, and
guaranteed never to fail. The overlay never shows blank or hangs.
"""
from __future__ import annotations

from schemas import (
    ActionCandidate, ActionType, AdvisorVerdict,
    CompCandidate, Fire, GameState,
)

# ── Expected level by stage — mirrors the heuristic in rules.py ───────────────
_EXPECTED_LEVEL: dict[str, int] = {
    "2-1": 4, "2-5": 4,
    "3-1": 5, "3-2": 6, "3-5": 6,
    "4-1": 7, "4-2": 8, "4-5": 8,
    "5-1": 8, "5-5": 9, "6-1": 9,
}


# ── Public entry point ─────────────────────────────────────────────────────────

def render_deterministic_verdict(
    state: GameState,
    top_action: ActionCandidate,
    top_comp: CompCandidate | None,
    fires: list[Fire],
) -> AdvisorVerdict:
    """Build a reasonable AdvisorVerdict with zero LLM involvement.

    Confidence is always MEDIUM because the deterministic renderer has no
    access to qualitative context. The warning field surfaces the fallback.
    """
    one_liner = _render_one_liner(top_action, state)
    reasoning = _render_reasoning(top_action, top_comp, fires)
    tempo     = _infer_tempo(state)

    return AdvisorVerdict(
        one_liner=one_liner,
        confidence="MEDIUM",
        tempo_read=tempo,
        primary_action=top_action.action_type,
        chosen_candidate=top_action,
        reasoning=reasoning,
        considerations=[],
        warnings=["advisor LLM unavailable — using deterministic fallback"],
        data_quality_note="deterministic fallback; no LLM call made",
    )


# ── One-liner renderer ─────────────────────────────────────────────────────────

def _render_one_liner(action: ActionCandidate, state: GameState) -> str:
    t = action.action_type
    p = action.params

    if t == ActionType.BUY:
        champ = p.get("champion", "unit")
        return f"Buy {champ} from shop."
    if t == ActionType.SELL:
        champ = p.get("champion") or p.get("unit_name", "flagged unit")
        return f"Sell {champ} to free bench space."
    if t == ActionType.ROLL_TO:
        floor = p.get("gold_floor", 0)
        return f"Roll to {floor}g — looking for upgrades."
    if t == ActionType.LEVEL_UP:
        return f"Buy XP to reach level {state.level + 1}."
    if t == ActionType.HOLD_ECON:
        return f"Hold at {state.gold}g for interest."
    if t == ActionType.SLAM_ITEM:
        components = p.get("components", ["?", "?"])
        carrier    = p.get("carrier", "main carry")
        c1 = components[0] if components else "?"
        c2 = components[1] if len(components) > 1 else "?"
        return f"Slam {c1} + {c2} on {carrier}."
    if t == ActionType.PIVOT_COMP:
        arch_id = p.get("archetype_id", "alternative comp")
        return f"Pivot to {arch_id}."
    return "Hold position — re-press F9 after shop refresh."


# ── Reasoning renderer ─────────────────────────────────────────────────────────

def _render_reasoning(
    action: ActionCandidate,
    top_comp: CompCandidate | None,
    fires: list[Fire],
) -> str:
    parts: list[str] = [f"Top action score: {action.total_score:.1f}"]

    if top_comp:
        parts.append(
            f"Target comp: {top_comp.archetype.display_name} "
            f"(P(reach)={top_comp.p_reach:.0%})"
        )

    crit_fires = [f for f in fires if f.severity >= 0.7]
    if crit_fires:
        fire_ids = ", ".join(f.rule_id for f in crit_fires[:3])
        parts.append(f"Active alerts: {fire_ids}")

    if action.reasoning_tags:
        parts.append(f"Tags: {', '.join(action.reasoning_tags[:4])}")

    return " | ".join(parts)


# ── Tempo inference ────────────────────────────────────────────────────────────

def _infer_tempo(state: GameState) -> str:
    if state.hp < 25:
        return "CRITICAL"
    expected = _EXPECTED_LEVEL.get(state.stage, 6)
    if state.level < expected - 1:
        return "BEHIND"
    if state.level > expected + 1:
        return "AHEAD"
    return "ON_PACE"
