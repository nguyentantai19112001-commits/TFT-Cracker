"""Phase 5 acceptance tests — recommender. See skills/recommender/SKILL.md."""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest
from schemas import GameState, BoardUnit, ActionType
from recommender import top_k, enumerate_candidates
from comp_planner import load_archetypes, top_k_comps
from pool import PoolTracker
from rules import evaluate
import knowledge as km
import econ

SET17 = km.load_set("17")
CORE = km.load_core()
ARCHS = load_archetypes()


def _build(state: GameState):
    pt = PoolTracker(SET17)
    comps = top_k_comps(state, pt, ARCHS, SET17, k=3)
    fires = evaluate(state, econ, pt, km)
    return state, fires, comps, pt


def _state(**kw) -> GameState:
    defaults = dict(stage="3-1", gold=20, hp=70, level=5,
                    xp_current=0, xp_needed=20, streak=0, set_id="17")
    defaults.update(kw)
    return GameState(**defaults)


def test_hp_urgent_favors_roll():
    state, fires, comps, pt = _build(_state(hp=25, gold=40, level=7, xp_current=0, xp_needed=28))
    top = top_k(state, fires, comps, pt, SET17, CORE, k=3)
    assert top[0].action_type == ActionType.ROLL_TO


def test_hold_econ_always_present():
    state, fires, comps, pt = _build(_state(gold=50, hp=80))
    candidates = enumerate_candidates(state, comps, pt, SET17)
    assert any(c.action_type == ActionType.HOLD_ECON for c in candidates)


def test_components_surfaces_slam():
    state, fires, comps, pt = _build(_state(
        hp=50, gold=30, level=6, xp_current=0, xp_needed=36,
        board=[BoardUnit(champion="Jhin", star=2)],
        item_components_on_bench=["BF Sword", "Recurve Bow", "Tear of the Goddess"],
    ))
    top = top_k(state, fires, comps, pt, SET17, CORE, k=5)
    assert any(c.action_type == ActionType.SLAM_ITEM for c in top)


def test_top_k_respects_k():
    state, fires, comps, pt = _build(_state())
    for k in (1, 3, 5):
        result = top_k(state, fires, comps, pt, SET17, CORE, k=k)
        assert len(result) <= k


def test_scores_in_bounds():
    state, fires, comps, pt = _build(_state())
    top = top_k(state, fires, comps, pt, SET17, CORE, k=5)
    for c in top:
        for score_val in [c.scores.tempo, c.scores.econ, c.scores.hp_risk,
                          c.scores.board_strength, c.scores.pivot_value]:
            assert -3 <= score_val <= 3, f"Score out of bounds: {score_val}"


def test_reasoning_tags_hp_danger():
    state, fires, comps, pt = _build(_state(hp=25, gold=40))
    top = top_k(state, fires, comps, pt, SET17, CORE, k=3)
    assert any("hp_danger" in c.reasoning_tags for c in top)


def test_sorted_descending():
    state, fires, comps, pt = _build(_state())
    top = top_k(state, fires, comps, pt, SET17, CORE, k=10)
    scores = [c.total_score for c in top]
    assert scores == sorted(scores, reverse=True)


def test_total_score_within_max_range():
    """Max possible = 3 * (tempo + econ + hp_risk * 1.5/1 + board * 1.2/1 + pivot * 0.8/1)."""
    state, fires, comps, pt = _build(_state())
    top = top_k(state, fires, comps, pt, SET17, CORE, k=5)
    for c in top:
        assert -20 <= c.total_score <= 20
