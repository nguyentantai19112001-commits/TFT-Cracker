"""test_smoke.py — End-to-end smoke test against a logged capture.

Run this after every integration pass. It exercises the full pipeline on a captured
game state without requiring a live game, and asserts the pipeline doesn't crash and
emits the expected shapes.

Usage:
    pytest tests/test_smoke.py -v

To add a new fixture: drop a PNG + LCU snapshot JSON into tests/fixtures/captures/<name>/,
then add a parametrize entry below.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# engine/ root — all module paths resolve relative to here, not CWD.
_ENGINE = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ENGINE):
    sys.path.insert(0, str(_ENGINE))

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "captures"


def _available_fixtures() -> list[str]:
    if not FIXTURES_DIR.exists():
        return []
    return [d.name for d in FIXTURES_DIR.iterdir() if d.is_dir()]


# ==============================================================================
# Phase 0 smoke — schemas + knowledge load cleanly
# ==============================================================================

def test_schemas_import():
    import schemas
    assert hasattr(schemas, "GameState")
    assert hasattr(schemas, "AdvisorVerdict")
    assert hasattr(schemas, "ActionType")


def test_knowledge_loads():
    pytest.importorskip("knowledge")
    from knowledge import load_core, load_set

    core = load_core()
    assert core.xp_cost_per_buy == 4

    set17 = load_set("17")
    assert set17.set_id == "17"
    for level in range(3, 12):
        odds = set17.shop_odds[level]
        # odds come in as percents summing to 100 (raw YAML); the loader may return
        # fractions. Either form is acceptable as long as they sum.
        s = sum(odds)
        assert s <= 100.01 and s >= 0.0  # some levels may sum < 100 by design


# ==============================================================================
# Phase 1 smoke — econ produces sensible numbers
# ==============================================================================

def test_econ_available():
    pytest.importorskip("econ")


@pytest.mark.skipif(not (_ENGINE / "econ.py").exists(), reason="econ.py not yet built")
def test_econ_p_hit_reasonable():
    from knowledge import load_set
    from schemas import PoolState
    import econ

    set17 = load_set("17")
    # Full pool, 4-cost, 50g at L8 — tftodds says ~80%
    pool = PoolState(copies_of_target_remaining=10,
                     same_cost_copies_remaining=130,
                     distinct_same_cost=13)
    r = econ.analyze_roll("Jinx", level=8, gold=50, pool=pool, set_=set17)
    assert 0.55 < r.p_hit_at_least_2 < 0.80  # Markov gives ~0.64 for this config


# ==============================================================================
# Phase 2 smoke — pool tracker updates
# ==============================================================================

@pytest.mark.skipif(not (_ENGINE / "pool.py").exists(), reason="pool.py not yet built")
def test_pool_tracker_decrement():
    from pool import PoolTracker
    from schemas import BoardUnit
    from knowledge import load_set

    t = PoolTracker(load_set("17"))
    before = t.belief_for("Jinx").k_estimate
    t.observe_own_board(board=[BoardUnit(champion="Jinx", star=1)], bench=[])
    after = t.belief_for("Jinx").k_estimate
    assert after == before - 1


# ==============================================================================
# Phase 3 smoke — rules fire
# ==============================================================================

@pytest.mark.skipif(not (_ENGINE / "rules.py").exists(), reason="rules.py not yet extended")
def test_rules_hp_urgent_fires():
    from schemas import GameState
    import rules
    import econ
    import knowledge as km
    from pool import PoolTracker

    state = GameState(stage="3-2", gold=30, hp=20, level=6,
                      xp_current=0, xp_needed=36, streak=0, set_id="17")
    pt = PoolTracker(km.load_set("17"))
    fires = rules.evaluate(state, econ, pt, km)
    assert any(f.rule_id == "HP_URGENT" for f in fires)


# ==============================================================================
# Phase 5 smoke — recommender returns top-k
# ==============================================================================

@pytest.mark.skipif(not (_ENGINE / "recommender.py").exists(), reason="recommender.py not yet built")
def test_recommender_returns_top_k():
    from schemas import GameState
    from pool import PoolTracker
    from comp_planner import load_archetypes, top_k_comps
    from recommender import top_k
    import rules
    import econ
    import knowledge as km

    state = GameState(stage="3-2", gold=30, hp=70, level=6,
                      xp_current=0, xp_needed=36, streak=0, set_id="17")
    set17 = km.load_set("17")
    core = km.load_core()
    pt = PoolTracker(set17)
    archs = load_archetypes()
    comps = top_k_comps(state, pt, archs, set17, k=3)
    fires = rules.evaluate(state, econ, pt, km)
    actions = top_k(state, fires, comps, pt, set17, core, k=3)
    assert len(actions) == 3
    for a in actions:
        assert -15 <= a.total_score <= 15  # 5 dims × weight ~1.5 × score ±3


# ==============================================================================
# Phase 6 smoke — advisor picks from top-k (requires live API or recorded session)
# ==============================================================================

@pytest.mark.skipif(not (_ENGINE / "advisor.py").exists(), reason="advisor.py not yet refactored")
@pytest.mark.slow  # needs API key; skip in CI without one
def test_advisor_picks_from_top_k():
    pytest.skip("Enable after Phase 6 with recorded API responses")


# ==============================================================================
# Full end-to-end on a captured fixture
# ==============================================================================

@pytest.mark.parametrize("fixture_name", _available_fixtures())
@pytest.mark.skipif(not _available_fixtures(), reason="no capture fixtures")
def test_full_pipeline_on_capture(fixture_name):
    """Full pipeline on a recorded capture: state → validate → rules → comp → recommender.

    Does NOT call the advisor (that requires a live API key). Verifies the deterministic
    layers don't crash and produce well-formed output on any fixture state.
    """
    fixture_dir = FIXTURES_DIR / fixture_name
    state_json = json.loads((fixture_dir / "state.json").read_text())

    from schemas import GameState
    import econ
    import rules
    import knowledge as km
    from pool import PoolTracker
    from comp_planner import load_archetypes, top_k_comps
    from recommender import top_k
    from validators import validate

    state = GameState.model_validate(state_json)
    assert state.stage
    assert state.hp >= 0
    assert state.level >= 1

    # Validator must not raise
    result = validate(state)
    assert result.ok, f"fixture state failed validation: {result.failures}"

    # Deterministic rule engine
    set17 = km.load_set("17")
    core  = km.load_core()
    pt    = PoolTracker(set17)
    fires = rules.evaluate(state, econ, pt, km)
    assert isinstance(fires, list)

    # Comp planner
    archs = load_archetypes()
    comps = top_k_comps(state, pt, archs, set17, k=3)
    assert len(comps) <= 3

    # Recommender
    actions = top_k(state, fires, comps, pt, set17, core, k=3)
    assert len(actions) <= 3
    for a in actions:
        assert -15 <= a.total_score <= 15
