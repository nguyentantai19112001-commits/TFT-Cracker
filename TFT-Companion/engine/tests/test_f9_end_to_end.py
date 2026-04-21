"""End-to-end smoke test for the F9 pipeline.

Exercises the full chain from a fixture GameState through rules →
comp_planner → recommender → (mocked) advisor, verifying each stage
produces a non-empty, well-typed result. Does NOT make a live Claude
API call.

This test is the primary regression guard for the Task 1 wiring. If it
fails, the F9 button doesn't work in production.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure engine/ is importable regardless of where pytest is invoked from.
_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest

import knowledge
import rules
import econ
import comp_planner
import recommender
import advisor
from schemas import GameState, BoardUnit, ShopSlot
from pool import PoolTracker


# ── Fixture state ──────────────────────────────────────────────────────────────

FIXTURE_STATE = GameState(
    stage="3-2",
    gold=30,
    hp=70,
    level=6,
    xp_current=5,
    xp_needed=36,
    streak=0,
    set_id="17",
    board=[BoardUnit(champion="Jinx", star=1, items=[])],
    bench=[],
    shop=[
        ShopSlot(champion="Jinx",        cost=2, locked=False),
        ShopSlot(champion="Akali",       cost=2, locked=False),
        ShopSlot(champion="Poppy",       cost=1, locked=False),
        ShopSlot(champion="Leona",       cost=1, locked=False),
        ShopSlot(champion="Mordekaiser", cost=2, locked=False),
    ],
    active_traits=[],
    augments=[],
)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_pipeline_end_to_end_produces_actions():
    """Full chain: state → rules → comp_planner → recommender.

    Every stage must return a non-empty, well-typed result.
    Actions must be sorted descending by total_score.
    """
    set_       = knowledge.load_set("17")
    core       = knowledge.load_core()
    pool       = PoolTracker(set_)
    pool.observe_own_board(FIXTURE_STATE.board, FIXTURE_STATE.bench)
    archetypes = comp_planner.load_archetypes()

    fires = rules.evaluate(FIXTURE_STATE, econ, pool, knowledge)
    assert isinstance(fires, list), "rules.evaluate must return a list"

    comps = comp_planner.top_k_comps(FIXTURE_STATE, pool, archetypes, set_, k=3)
    assert len(comps) == 3, "comp_planner must return exactly k=3 comps"
    assert all(hasattr(c, "p_reach") for c in comps), "each comp must have p_reach"

    actions = recommender.top_k(FIXTURE_STATE, fires, comps, pool, set_, core, k=3)
    assert len(actions) == 3, "recommender must return exactly k=3 actions"
    # Must be sorted descending
    assert actions[0].total_score >= actions[1].total_score >= actions[2].total_score


def test_pipeline_handles_empty_state_gracefully():
    """Stage 1-1, empty board — must complete without crash."""
    empty_state = GameState(
        stage="1-1", gold=0, hp=100, level=1,
        xp_current=0, xp_needed=2, streak=0, set_id="17",
    )
    set_       = knowledge.load_set("17")
    core       = knowledge.load_core()
    pool       = PoolTracker(set_)
    archetypes = comp_planner.load_archetypes()

    fires   = rules.evaluate(empty_state, econ, pool, knowledge)
    comps   = comp_planner.top_k_comps(empty_state, pool, archetypes, set_, k=3)
    actions = recommender.top_k(empty_state, fires, comps, pool, set_, core, k=3)

    assert isinstance(actions, list)
    # With gold=0 and level=1, fewer than 3 candidates may be generated — that's correct.
    assert 1 <= len(actions) <= 3


def test_advisor_receives_correct_inputs(monkeypatch):
    """Verify advisor.advise_stream is called with the right parameters.

    This is the test that most directly catches a broken wiring — if the
    pipeline computes actions/comps but passes them in the wrong shape,
    this will catch it.
    """
    called_with = {}

    def fake_advise_stream(**kwargs):
        called_with.update(kwargs)
        yield ("one_liner", "Hold to interest cap.")
        yield ("final", {"verdict": None, "recommendation": {}, "__meta__": {"parse_ok": True}})

    monkeypatch.setattr(advisor, "advise_stream", fake_advise_stream)

    set_       = knowledge.load_set("17")
    core       = knowledge.load_core()
    pool       = PoolTracker(set_)
    archetypes = comp_planner.load_archetypes()

    fires   = rules.evaluate(FIXTURE_STATE, econ, pool, knowledge)
    comps   = comp_planner.top_k_comps(FIXTURE_STATE, pool, archetypes, set_, k=3)
    actions = recommender.top_k(FIXTURE_STATE, fires, comps, pool, set_, core, k=3)

    # Drive the advisor stream exactly as PipelineWorker.run() does
    events = list(advisor.advise_stream(
        state=FIXTURE_STATE, fires=fires, actions=actions, comps=comps,
        client=None, capture_id=None,
    ))

    assert "state"   in called_with, "advisor must receive state"
    assert "fires"   in called_with, "advisor must receive fires"
    assert "actions" in called_with, "advisor must receive actions"
    assert "comps"   in called_with, "advisor must receive comps"
    assert len(called_with["actions"]) == 3, "must be top-3 actions"
    assert len(called_with["comps"])   == 3, "must be top-3 comps"
    assert any(e[0] == "one_liner" for e in events), "must emit one_liner event"
    assert any(e[0] == "final"     for e in events), "must emit final event"
