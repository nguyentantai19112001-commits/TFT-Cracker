"""Tests for Agent 5 — MicroEcon (pure arithmetic, no LLM)."""
from __future__ import annotations

import asyncio
import pytest

from engine.agents.micro_econ import (
    MicroEconAgent,
    MicroEconInput,
    _base_income,
    _xp_between,
    _compute,
)
from engine.agents.schemas import MicroEconResult
from engine.knowledge.loader import constants, reset_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


def run(inp: MicroEconInput) -> MicroEconResult:
    return asyncio.run(MicroEconAgent().run(ctx=inp))


# ── _xp_between ───────────────────────────────────────────────────────────────

def test_xp_between_same_level():
    assert _xp_between(7, 7) == 0


def test_xp_between_7_to_8():
    # xp_to_next[7] = 60
    assert _xp_between(7, 8) == 60


def test_xp_between_7_to_9():
    # xp_to_next[7]=60, xp_to_next[8]=68
    assert _xp_between(7, 9) == 128


def test_xp_between_4_to_5():
    # xp_to_next[4] = 10
    assert _xp_between(4, 5) == 10


def test_xp_between_multi_levels():
    # 3→6: xp[3]=6 + xp[4]=10 + xp[5]=20 = 36
    assert _xp_between(3, 6) == 36


# ── _base_income ──────────────────────────────────────────────────────────────

def test_base_income_stage_1_1():
    k = constants()
    assert _base_income((1, 1), k) == 0


def test_base_income_stage_2_1():
    k = constants()
    assert _base_income((2, 1), k) == 4


def test_base_income_stage_2_2():
    k = constants()
    assert _base_income((2, 2), k) == 5


def test_base_income_stage_3_4():
    # 3-4 is not in table → falls back to 2-2+ = 5
    k = constants()
    assert _base_income((3, 4), k) == 5


def test_base_income_stage_4_2():
    k = constants()
    assert _base_income((4, 2), k) == 5


# ── Level scenario gold math ──────────────────────────────────────────────────

def test_level_7_to_8_cost():
    # xp needed = 60, 60/4 = 15 buys × 4g = 60g
    inp = MicroEconInput(gold=70, level=7, streak=0, stage=(4, 2), target_levels=[8])
    r = run(inp)
    s = next((s for s in r.scenarios if s.id == "level_8"), None)
    assert s is not None
    assert s.gold_after == 70 - 60


def test_level_8_to_9_cost():
    # xp needed = 68, ceil(68/4)*4 = 68g exactly
    inp = MicroEconInput(gold=80, level=8, streak=0, stage=(5, 1), target_levels=[9])
    r = run(inp)
    s = next((s for s in r.scenarios if s.id == "level_9"), None)
    assert s is not None
    assert s.gold_after == 80 - 68


def test_level_not_added_if_cant_afford():
    inp = MicroEconInput(gold=10, level=7, streak=0, stage=(4, 2), target_levels=[8])
    r = run(inp)
    ids = [s.id for s in r.scenarios]
    assert "level_8" not in ids


def test_level_not_added_if_already_at_target():
    inp = MicroEconInput(gold=60, level=8, streak=0, stage=(4, 2), target_levels=[8])
    r = run(inp)
    ids = [s.id for s in r.scenarios]
    assert "level_8" not in ids


# ── Interest tier math ────────────────────────────────────────────────────────

def test_interest_tier_preserved_when_hold():
    # Start at 50g → interest=5; hold → interest stays 5 if base income keeps above 50
    inp = MicroEconInput(gold=50, level=7, streak=0, stage=(4, 2))
    r = run(inp)
    hold = next(s for s in r.scenarios if s.id == "hold")
    assert hold.interest_delta >= 0  # didn't lose interest


def test_interest_lost_when_leveling():
    # 50g → 5 interest. Level costs 60g — but we don't have enough, so skip
    # At 60g → 5 interest. Level to 8 costs 60g → 0g left → 0 interest.
    inp = MicroEconInput(gold=60, level=7, streak=0, stage=(4, 2), target_levels=[8])
    r = run(inp)
    s = next((s for s in r.scenarios if s.id == "level_8"), None)
    if s:
        assert s.interest_delta < 0  # lost interest by spending below 50g


def test_current_snapshot_interest_correct():
    inp = MicroEconInput(gold=30, level=6, streak=0, stage=(3, 2))
    r = run(inp)
    assert r.current.interest == 3  # floor(30/10) = 3


# ── Streak bonus in scenarios ─────────────────────────────────────────────────

def test_streak_bonus_included_in_hold():
    # Streak 4 → +1 bonus gold per round (streak_bonus[4]=1)
    inp_no_streak = MicroEconInput(gold=20, level=5, streak=0, stage=(3, 2))
    inp_streak    = MicroEconInput(gold=20, level=5, streak=4, stage=(3, 2))
    r_no = run(inp_no_streak)
    r_s  = run(inp_streak)
    hold_no = next(s for s in r_no.scenarios if s.id == "hold")
    hold_s  = next(s for s in r_s.scenarios if s.id == "hold")
    assert hold_s.gold_after > hold_no.gold_after


# ── Roll scenarios ────────────────────────────────────────────────────────────

def test_roll_scenario_gold_deducted():
    inp = MicroEconInput(gold=40, level=7, streak=0, stage=(3, 5), roll_amounts=[20])
    r = run(inp)
    s = next((s for s in r.scenarios if s.id == "roll_20"), None)
    assert s is not None
    assert s.gold_after == 20


def test_roll_ignored_if_more_than_gold():
    inp = MicroEconInput(gold=10, level=7, streak=0, stage=(3, 5), roll_amounts=[20])
    r = run(inp)
    ids = [s.id for s in r.scenarios]
    assert "roll_20" not in ids


# ── 4g chunk rounding ────────────────────────────────────────────────────────

def test_xp_cost_rounds_up_to_4g_chunk():
    # xp_to_next[5] = 20, exactly divisible by 4 → cost = 20
    inp = MicroEconInput(gold=30, level=5, streak=0, stage=(3, 2), target_levels=[6])
    r = run(inp)
    s = next((s for s in r.scenarios if s.id == "level_6"), None)
    if s:
        assert (s.gold_before - s.gold_after) % 4 == 0  # always a multiple of 4


def test_xp_cost_6_rounds_to_8():
    # xp_to_next[3] = 6, ceil(6/4)*4 = 8g
    inp = MicroEconInput(gold=20, level=3, streak=0, stage=(2, 3), target_levels=[4])
    r = run(inp)
    s = next((s for s in r.scenarios if s.id == "level_4"), None)
    assert s is not None
    assert s.gold_before - s.gold_after == 8


# ── Output structure ──────────────────────────────────────────────────────────

def test_hold_always_present():
    inp = MicroEconInput(gold=30, level=6, streak=0, stage=(3, 2))
    r = run(inp)
    ids = [s.id for s in r.scenarios]
    assert "hold" in ids


def test_best_scenario_is_valid_id():
    inp = MicroEconInput(gold=40, level=6, streak=0, stage=(3, 2), target_levels=[7])
    r = run(inp)
    ids = [s.id for s in r.scenarios]
    assert r.best_scenario in ids


def test_one_liner_non_empty():
    inp = MicroEconInput(gold=40, level=6, streak=0, stage=(3, 2), target_levels=[7])
    r = run(inp)
    assert len(r.one_liner) > 0


def test_result_serializes():
    inp = MicroEconInput(gold=50, level=7, streak=2, stage=(4, 1), target_levels=[8])
    r = run(inp)
    d = r.model_dump()
    assert "current" in d and "scenarios" in d


def test_deterministic():
    inp = MicroEconInput(gold=50, level=7, streak=2, stage=(4, 1), target_levels=[8], roll_amounts=[20])
    r1 = run(inp)
    r2 = run(inp)
    assert r1.model_dump() == r2.model_dump()
