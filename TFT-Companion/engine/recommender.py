"""recommender.py — Enumerate and score action candidates; return top-k.

Public API:
    enumerate_candidates(state, comps, pool, set_) -> list[ActionCandidate]
    score_candidate(candidate, state, fires, comps, pool, set_, core) -> ActionCandidate
    top_k(state, fires, comps, pool, set_, core, k=3) -> list[ActionCandidate]
"""
from __future__ import annotations

import sys
from itertools import combinations
from math import ceil
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

from schemas import (
    ActionCandidate, ActionScores, ActionType, BoardUnit, CompCandidate,
    CoreKnowledge, Fire, GameState, SetKnowledge, ScoringWeights,
)
from pool import PoolTracker
import econ as econ_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stage_key(stage: str) -> float:
    """'4-2' → 4.2 for comparison."""
    try:
        parts = stage.split("-")
        return float(parts[0]) + float(parts[1]) / 10
    except Exception:
        return 0.0


def _completes_2_star(champion: str, state: GameState) -> bool:
    """Buying this champion would combine into a 2-star (we already have 2 copies at 1-star)."""
    ones = sum(
        1 for u in state.board + state.bench
        if u.champion == champion and u.star == 1
    )
    return ones >= 2


def _unit_in_any_comp(champion: str, comps: list[CompCandidate]) -> bool:
    for c in comps:
        all_units = set(c.archetype.core_units) | set(c.archetype.optional_units)
        if champion in all_units:
            return True
    return False


def _top_comp_carriers(comps: list[CompCandidate]) -> set[str]:
    if not comps:
        return set()
    top = comps[0].archetype
    carrier_set: set[str] = set()
    for unit in top.ideal_items:
        carrier_set.add(unit)
    return carrier_set


def _is_board_upgrade(cand: ActionCandidate, state: GameState) -> bool:
    champ = cand.params.get("champion", "")
    return champ in {u.champion for u in state.board}


def _shop_cost(champion: str, state: GameState) -> int:
    for slot in state.shop:
        if slot.champion == champion:
            return slot.cost
    return 0


def _xp_to_level(state: GameState) -> int:
    return max(0, state.xp_needed - state.xp_current)


def _level_gold_cost(state: GameState, core: CoreKnowledge) -> int:
    xp_needed = _xp_to_level(state)
    if xp_needed == 0:
        return 0
    buys = ceil(xp_needed / core.xp_per_buy)
    return buys * core.xp_cost_per_buy


def _interest_tier(gold: int, core: CoreKnowledge) -> int:
    return min(core.interest_cap, gold // 10)


# ---------------------------------------------------------------------------
# Enumerate candidates
# ---------------------------------------------------------------------------

def enumerate_candidates(
    state: GameState,
    comps: list[CompCandidate],
    pool: PoolTracker,
    set_: SetKnowledge,
) -> list[ActionCandidate]:
    candidates: list[ActionCandidate] = []
    null_scores = ActionScores(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0)

    top_3_units: set[str] = set()
    for c in comps[:3]:
        top_3_units |= set(c.archetype.core_units) | set(c.archetype.optional_units)

    # BUY — shop units relevant to top comps or completing a 2-star
    bench_full = len(state.bench) >= 9
    for slot in state.shop:
        champ = slot.champion
        relevant = champ in top_3_units or _completes_2_star(champ, state)
        if relevant and not bench_full:
            candidates.append(ActionCandidate(
                action_type=ActionType.BUY,
                params={"champion": champ, "cost": slot.cost},
                scores=null_scores, total_score=0, human_summary=f"Buy {champ}",
            ))

    # SELL — bench/board units not in any top-3 comp, no items, not carrying items
    for i, u in enumerate(state.bench):
        if not _unit_in_any_comp(u.champion, comps[:3]) and not u.items:
            candidates.append(ActionCandidate(
                action_type=ActionType.SELL,
                params={"unit_index": i, "location": "bench", "champion": u.champion},
                scores=null_scores, total_score=0, human_summary=f"Sell {u.champion} (bench)",
            ))
    for i, u in enumerate(state.board):
        if not u.items and not _unit_in_any_comp(u.champion, comps[:3]):
            candidates.append(ActionCandidate(
                action_type=ActionType.SELL,
                params={"unit_index": i, "location": "board", "champion": u.champion},
                scores=null_scores, total_score=0, human_summary=f"Sell {u.champion} (board)",
            ))

    # ROLL_TO — three floor variants
    for floor in (0, 20, 30):
        if state.gold > floor + 4:  # need at least 4 to roll once after floor
            candidates.append(ActionCandidate(
                action_type=ActionType.ROLL_TO,
                params={"gold_floor": floor},
                scores=null_scores, total_score=0, human_summary=f"Roll to {floor}g",
            ))

    # LEVEL_UP — at most one
    if state.level < 10:
        cost = _level_gold_cost(state, _dummy_core())
        if state.gold >= cost and cost > 0 and state.gold - cost >= state.gold * 0.2:
            candidates.append(ActionCandidate(
                action_type=ActionType.LEVEL_UP,
                params={},
                scores=null_scores, total_score=0, human_summary=f"Level up to {state.level + 1}",
            ))

    # HOLD_ECON — always
    candidates.append(ActionCandidate(
        action_type=ActionType.HOLD_ECON,
        params={},
        scores=null_scores, total_score=0, human_summary="Hold econ",
    ))

    # SLAM_ITEM — one per pair of bench components
    components = state.item_components_on_bench
    if len(components) >= 2:
        carriers = _top_comp_carriers(comps)
        seen_pairs: set[tuple[str, str]] = set()
        for c1, c2 in combinations(components, 2):
            pair = tuple(sorted([c1, c2]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            carrier = next(
                (u.champion for u in state.board if u.champion in carriers), ""
            )
            candidates.append(ActionCandidate(
                action_type=ActionType.SLAM_ITEM,
                params={"components": [c1, c2], "carrier": carrier},
                scores=null_scores, total_score=0,
                human_summary=f"Slam {c1} + {c2}" + (f" onto {carrier}" if carrier else ""),
            ))

    # PIVOT_COMP — if 2nd comp is within 0.2 of 1st
    if len(comps) >= 2 and comps[0].total_score - comps[1].total_score < 0.2:
        pivot = comps[1]
        candidates.append(ActionCandidate(
            action_type=ActionType.PIVOT_COMP,
            params={"archetype_id": pivot.archetype.archetype_id},
            scores=null_scores, total_score=0,
            human_summary=f"Pivot to {pivot.archetype.display_name}",
        ))

    return candidates


def _dummy_core() -> CoreKnowledge:
    """Minimal core for use before core is passed in."""
    from knowledge import load_core
    return load_core()


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def _score_tempo(cand: ActionCandidate, state: GameState, comps: list[CompCandidate]) -> float:
    if cand.action_type == ActionType.BUY:
        champ = cand.params.get("champion", "")
        if _completes_2_star(champ, state):
            return 3.0
        if champ in {u.champion for u in state.board}:
            return 1.0
        return 0.0
    if cand.action_type == ActionType.ROLL_TO:
        gold_spent = state.gold - cand.params["gold_floor"]
        return min(3.0, gold_spent / 10)
    if cand.action_type == ActionType.LEVEL_UP:
        return 1.0 if _stage_key(state.stage) >= 4.0 else 0.0
    if cand.action_type == ActionType.HOLD_ECON:
        return -1.0
    if cand.action_type == ActionType.SLAM_ITEM:
        carrier = cand.params.get("carrier", "")
        return 2.0 if carrier in _top_comp_carriers(comps) else 1.0
    if cand.action_type == ActionType.SELL:
        return -1.0 if cand.params.get("location") == "board" else 0.0
    if cand.action_type == ActionType.PIVOT_COMP:
        return -2.0
    return 0.0


def _score_econ(cand: ActionCandidate, state: GameState, core: CoreKnowledge) -> float:
    interest_now = _interest_tier(state.gold, core)

    if cand.action_type == ActionType.HOLD_ECON:
        return 2.0 if interest_now >= 4 else 1.0
    if cand.action_type == ActionType.ROLL_TO:
        gold_after = cand.params["gold_floor"]
        interest_after = _interest_tier(gold_after, core)
        lost = interest_now - interest_after
        return -min(3.0, float(lost))
    if cand.action_type == ActionType.LEVEL_UP:
        gold_needed = _level_gold_cost(state, core)
        return -1.0 if gold_needed >= 10 else 0.0
    if cand.action_type == ActionType.BUY:
        cost = cand.params.get("cost", _shop_cost(cand.params.get("champion", ""), state))
        if cost >= 3 and state.gold - cost < interest_now * 10:
            return -1.0
        return 0.0
    return 0.0


def _score_hp_risk(cand: ActionCandidate, state: GameState) -> float:
    hp = state.hp
    if hp >= 60:
        multiplier = 0.3
    elif hp >= 40:
        multiplier = 1.0
    elif hp >= 25:
        multiplier = 2.0
    else:
        multiplier = 3.0

    raw = 0.0
    if cand.action_type == ActionType.ROLL_TO:
        if hp < 40:
            gold_spent = state.gold - cand.params["gold_floor"]
            raw = min(3.0, gold_spent / 10)
    elif cand.action_type == ActionType.HOLD_ECON:
        if hp < 35:
            raw = -2.0
    elif cand.action_type == ActionType.BUY:
        if hp < 40 and _is_board_upgrade(cand, state):
            raw = 1.0
    elif cand.action_type == ActionType.LEVEL_UP:
        if hp < 30:
            raw = -1.0
    elif cand.action_type == ActionType.SLAM_ITEM:
        if hp < 45:
            raw = 2.0

    return max(-3.0, min(3.0, raw * multiplier / 3))


def _score_board_strength(cand: ActionCandidate, state: GameState, comps: list[CompCandidate]) -> float:
    delta = 0.0
    if cand.action_type == ActionType.BUY:
        champ = cand.params.get("champion", "")
        if _completes_2_star(champ, state):
            delta = 20.0
        elif _is_board_upgrade(cand, state):
            delta = 8.0
        else:
            delta = 3.0
    elif cand.action_type == ActionType.ROLL_TO:
        if comps:
            top = comps[0]
            # Heuristic: rolling gives partial expected board gain
            gold_spent = state.gold - cand.params["gold_floor"]
            delta = 12.0 * min(1.0, gold_spent / 40) * top.p_reach
    elif cand.action_type == ActionType.LEVEL_UP:
        delta = 10.0  # new unit slot + possible cost tier
    elif cand.action_type == ActionType.SELL:
        delta = -5.0
    elif cand.action_type == ActionType.SLAM_ITEM:
        delta = 15.0
    elif cand.action_type == ActionType.HOLD_ECON:
        delta = 0.0

    return max(-3.0, min(3.0, delta / 10))


def _score_pivot_value(cand: ActionCandidate, state: GameState, comps: list[CompCandidate]) -> float:
    if not comps:
        return 0.0
    top_comp = comps[0]
    top_units = set(top_comp.archetype.core_units) | set(top_comp.archetype.optional_units)

    if cand.action_type == ActionType.BUY:
        champ = cand.params.get("champion", "")
        if champ in top_comp.archetype.core_units:
            return 2.0
        if champ in top_comp.archetype.optional_units:
            return 1.0
        return -1.0
    if cand.action_type == ActionType.PIVOT_COMP:
        target_id = cand.params.get("archetype_id", "")
        target = next((c for c in comps if c.archetype.archetype_id == target_id), None)
        return 2.0 if target and target.total_score > 0.7 else 0.0
    if cand.action_type == ActionType.SELL:
        champ = cand.params.get("champion", "")
        if champ in top_units:
            return -2.0
    return 0.0


def _build_reasoning_tags(
    cand: ActionCandidate,
    state: GameState,
    fires: list[Fire],
    comps: list[CompCandidate],
    set_: SetKnowledge,
    core: CoreKnowledge,
) -> list[str]:
    tags: list[str] = []
    fire_ids = {f.rule_id for f in fires}

    if state.hp < 35:
        tags.append("hp_danger")
    if "SPIKE_ROUND_NEXT" in fire_ids:
        tags.append("spike_round")
    if abs(state.streak) >= 3:
        if cand.action_type in (ActionType.HOLD_ECON, ActionType.BUY):
            tags.append("streak_preserve")

    if cand.action_type == ActionType.ROLL_TO:
        gold_after = cand.params.get("gold_floor", 0)
        if _interest_tier(state.gold, core) == _interest_tier(gold_after, core):
            tags.append("interest_kept")
        else:
            tags.append("interest_lost")

    if comps:
        top = comps[0]
        if top.p_reach > 0.5:
            tags.append("comp_reachable")
        elif cand.action_type == ActionType.BUY:
            champ = cand.params.get("champion", "")
            if champ in top.archetype.core_units and "comp_reachable" not in tags:
                tags.append("comp_reachable")

    return tags


def score_candidate(
    candidate: ActionCandidate,
    state: GameState,
    fires: list[Fire],
    comps: list[CompCandidate],
    pool: PoolTracker,
    set_: SetKnowledge,
    core: CoreKnowledge,
) -> ActionCandidate:
    weights = core.scoring_weights
    tempo = max(-3.0, min(3.0, _score_tempo(candidate, state, comps)))
    econ = max(-3.0, min(3.0, _score_econ(candidate, state, core)))
    hp_risk = max(-3.0, min(3.0, _score_hp_risk(candidate, state)))
    board_str = max(-3.0, min(3.0, _score_board_strength(candidate, state, comps)))
    pivot = max(-3.0, min(3.0, _score_pivot_value(candidate, state, comps)))

    scores = ActionScores(
        tempo=tempo, econ=econ, hp_risk=hp_risk,
        board_strength=board_str, pivot_value=pivot,
    )
    total = (
        weights.tempo * tempo
        + weights.econ * econ
        + weights.hp_risk * hp_risk
        + weights.board_strength * board_str
        + weights.pivot_value * pivot
    )
    tags = _build_reasoning_tags(candidate, state, fires, comps, set_, core)

    return ActionCandidate(
        action_type=candidate.action_type,
        params=candidate.params,
        scores=scores,
        total_score=total,
        human_summary=candidate.human_summary,
        reasoning_tags=tags,
    )


# ---------------------------------------------------------------------------
# Top-k entry point
# ---------------------------------------------------------------------------

def top_k(
    state: GameState,
    fires: list[Fire],
    comps: list[CompCandidate],
    pool: PoolTracker,
    set_: SetKnowledge,
    core: CoreKnowledge,
    k: int = 3,
) -> list[ActionCandidate]:
    candidates = enumerate_candidates(state, comps, pool, set_)
    scored = [score_candidate(c, state, fires, comps, pool, set_, core) for c in candidates]
    scored.sort(key=lambda c: c.total_score, reverse=True)
    return scored[:k]
