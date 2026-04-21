"""Tests for the phase-1 orchestrator — 5 rule-based agents in parallel."""
from __future__ import annotations

import asyncio
import pytest

from engine.agents.orchestrator import AgentContext, CoachOrchestrator, _next_armory
from engine.agents.schemas import CoachResult
from engine.knowledge.loader import reset_cache
from engine.agents.holder_matrix import reset_holders_cache


@pytest.fixture(autouse=True)
def _clear_caches():
    reset_cache()
    reset_holders_cache()
    yield
    reset_cache()
    reset_holders_cache()


def _ctx(**kwargs) -> AgentContext:
    defaults = dict(
        hp=60, gold=50, level=7, stage=(4, 2), streak=0,
        board_strength=0.5, bench_components=[], item_recipes={},
        board_slots=[], augments_picked=[], augment_tiers=[],
        target_comp_apis=[],
    )
    defaults.update(kwargs)
    return AgentContext(**defaults)


def run(ctx: AgentContext) -> CoachResult:
    return CoachOrchestrator().run_sync(ctx)


# ── _next_armory ──────────────────────────────────────────────────────────────

def test_next_armory_before_2_1():
    assert _next_armory((1, 4)) == (2, 1)


def test_next_armory_at_2_1():
    assert _next_armory((2, 1)) == (3, 2)


def test_next_armory_at_2_5():
    assert _next_armory((2, 5)) == (3, 2)


def test_next_armory_at_3_2():
    assert _next_armory((3, 2)) == (4, 2)


def test_next_armory_past_all():
    assert _next_armory((5, 1)) == (4, 2)


# ── CoachResult structure ─────────────────────────────────────────────────────

def test_orchestrator_returns_coach_result():
    r = run(_ctx())
    assert isinstance(r, CoachResult)


def test_all_eight_agents_populated():
    r = run(_ctx())
    assert r.frame is not None
    assert r.bis is not None
    assert r.econ is not None
    assert r.holders is not None
    assert r.augments is not None
    assert r.comp is not None
    assert r.tempo is not None
    assert r.item_econ is not None


def test_frame_agent_name():
    r = run(_ctx())
    assert r.frame.agent_name == "situational_frame"


def test_econ_agent_name():
    r = run(_ctx())
    assert r.econ.agent_name == "micro_econ"


def test_augment_agent_name():
    r = run(_ctx())
    assert r.augments.agent_name == "augment_quality"


def test_holder_agent_name():
    r = run(_ctx())
    assert r.holders.agent_name == "holder_matrix"


# ── Rule-based agent correctness ──────────────────────────────────────────────

def test_frame_hp_tier_from_context():
    r = run(_ctx(hp=25))
    # hp=25 is in danger tier (20-39)
    assert r.frame.hp_tier == "danger"


def test_frame_dying_hp():
    r = run(_ctx(hp=10))
    assert r.frame.game_tag == "dying"


def test_econ_current_gold_matches():
    r = run(_ctx(gold=44))
    assert r.econ.current.gold == 44


def test_econ_interest_correct():
    r = run(_ctx(gold=40))
    assert r.econ.current.interest == 4


def test_augments_upcoming_stage_correct():
    # stage 2-1 → upcoming should be 3-2
    r = run(_ctx(stage=(2, 1)))
    assert r.augments.upcoming_stage == (3, 2)


def test_augments_prior_tiers_g_g():
    r = run(_ctx(stage=(4, 1), augment_tiers=["G", "G"]))
    # upcoming=4-2, prior G_G → gold prob 0.88
    assert r.augments.tier_probabilities.gold > 0.8


def test_empty_board_no_bis_units():
    r = run(_ctx(board_slots=[]))
    assert r.bis.all_units == []


def test_board_unit_processed():
    board = [{
        "api_name": "TFT17_Vex",
        "display_name": "Vex",
        "cost": 5,
        "star": 2,
        "items_held": [],
        "bis_trios": [["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]],
        "value_class": "S",
    }]
    recipes = {
        "GuinsoosRageblade": ["RB", "Rod"],
        "JeweledGauntlet":   ["Glove", "Rod"],
        "ArchangelsStaff":   ["Tear", "Rod"],
    }
    r = run(_ctx(board_slots=board, item_recipes=recipes))
    assert len(r.bis.all_units) == 1
    assert r.bis.all_units[0].api_name == "TFT17_Vex"


def test_holder_vex_at_stage_4():
    board = [{"api_name": "TFT17_Vex", "display_name": "Vex", "cost": 5}]
    r = run(_ctx(board_slots=board, stage=(4, 2)))
    assert len(r.holders.assignments) == 1
    assert r.holders.assignments[0].stage_role == "primary"


# ── Stub agents ───────────────────────────────────────────────────────────────

def test_stub_comp_has_agent_name():
    r = run(_ctx())
    assert r.comp.agent_name == "comp_picker"


def test_stub_tempo_has_agent_name():
    r = run(_ctx())
    assert r.tempo.agent_name == "tempo_agent"


def test_stub_item_econ_has_agent_name():
    r = run(_ctx())
    assert r.item_econ.agent_name == "item_economy"


# ── Serialization ─────────────────────────────────────────────────────────────

def test_coach_result_serializes():
    r = run(_ctx())
    d = r.model_dump()
    assert set(d.keys()) >= {"frame", "comp", "bis", "tempo", "econ", "item_econ", "holders", "augments"}


# ── Determinism ───────────────────────────────────────────────────────────────

def test_deterministic():
    ctx = _ctx(hp=65, gold=40, level=7, stage=(4, 2), streak=2, board_strength=0.6)
    r1 = run(ctx)
    r2 = run(ctx)
    assert r1.model_dump() == r2.model_dump()


# ── Async run ─────────────────────────────────────────────────────────────────

def test_async_run():
    async def _run():
        return await CoachOrchestrator().run(_ctx())
    r = asyncio.run(_run())
    assert isinstance(r, CoachResult)
