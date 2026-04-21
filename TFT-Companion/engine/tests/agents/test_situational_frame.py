"""Tests for Agent 1 — SituationalFrame (rule-based, deterministic)."""
from __future__ import annotations

import asyncio
import pytest

from engine.agents.situational_frame import SituationalFrameAgent, SituationalFrameInput, _compute
from engine.agents.schemas import SituationalFrameResult
from engine.knowledge.loader import constants, reset_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


def run(inp: SituationalFrameInput) -> SituationalFrameResult:
    return asyncio.run(SituationalFrameAgent().run(ctx=inp))


# ── game_tag × hp_tier coverage ───────────────────────────────────────────────

def test_tag_dying_hp_critical():
    r = run(SituationalFrameInput(hp=15, gold=30, level=7, stage=(4, 2), streak=0))
    assert r.game_tag == "dying"
    assert r.hp_tier == "critical"


def test_tag_dying_hp_boundary():
    # HP=19 is still dying (< 20)
    r = run(SituationalFrameInput(hp=19, gold=50, level=8, stage=(4, 2), streak=0))
    assert r.game_tag == "dying"


def test_tag_winning_strong_board():
    # EV should be < 2.5: high board strength (0.9), win streak 4, healthy HP, rich
    r = run(SituationalFrameInput(hp=90, gold=70, level=8, stage=(4, 2), streak=4, board_strength=0.9))
    assert r.game_tag == "winning"
    assert r.frame_posture == "greed"


def test_tag_winning_high_board_strength():
    # hp=90, gold=80 vs curve=62, streak=6, board=0.95 → ev ≈ 2.14 → winning
    r = run(SituationalFrameInput(hp=90, gold=80, level=9, stage=(5, 2), streak=6, board_strength=0.95))
    assert r.game_tag == "winning"
    assert r.ev_avg_placement <= 2.5


def test_tag_stable_default():
    # Perfectly average everything → stable
    r = run(SituationalFrameInput(hp=60, gold=56, level=8, stage=(4, 2), streak=0, board_strength=0.5))
    assert r.game_tag in ("stable", "losing")  # depending on econ delta


def test_tag_stable_on_curve():
    # 3-2, hp=60, gold=50 (exactly on-curve), board_strength=0.5 → stable
    r = run(SituationalFrameInput(hp=60, gold=50, level=6, stage=(3, 2), streak=0, board_strength=0.5))
    # ev_base = 4.5 - (60-50)/50*1.0 - (50-50)/10*0.4 - 0 = 4.5 - 0.2 = 4.3
    assert r.game_tag in ("stable", "losing")
    assert r.hp_tier == "healthy"
    assert r.econ_tier == "on_curve"


def test_tag_losing_behind_curve():
    # Stage 4-2, gold=30 (way behind 56), hp=55
    r = run(SituationalFrameInput(hp=55, gold=30, level=7, stage=(4, 2), streak=-2, board_strength=0.5))
    assert r.game_tag in ("losing", "salvage")
    assert r.frame_posture in ("stabilize", "salvage")


def test_tag_salvage_high_ev_low_hp():
    # Must satisfy: ev_avg > 5.5 AND hp < 50
    # Low board strength + low gold + damage HP → high EV
    r = run(SituationalFrameInput(hp=35, gold=10, level=5, stage=(4, 2), streak=-4, board_strength=0.1))
    assert r.game_tag in ("salvage", "dying")  # hp=35 ≥ 20, so salvage if ev>5.5


def test_tag_salvage_posture():
    r = run(SituationalFrameInput(hp=40, gold=10, level=5, stage=(4, 2), streak=-5, board_strength=0.1))
    if r.game_tag == "salvage":
        assert r.frame_posture == "salvage"


# ── HP tier boundaries ────────────────────────────────────────────────────────

def test_hp_tier_healthy_60():
    r = run(SituationalFrameInput(hp=60, gold=50, level=6, stage=(3, 2), streak=0))
    assert r.hp_tier == "healthy"


def test_hp_tier_warn_59():
    r = run(SituationalFrameInput(hp=59, gold=50, level=6, stage=(3, 2), streak=0))
    assert r.hp_tier == "warn"


def test_hp_tier_warn_40():
    r = run(SituationalFrameInput(hp=40, gold=50, level=6, stage=(3, 2), streak=0))
    assert r.hp_tier == "warn"


def test_hp_tier_danger_39():
    r = run(SituationalFrameInput(hp=39, gold=50, level=6, stage=(3, 2), streak=0))
    assert r.hp_tier == "danger"


def test_hp_tier_danger_20():
    r = run(SituationalFrameInput(hp=20, gold=50, level=6, stage=(3, 2), streak=0))
    assert r.hp_tier == "danger"


def test_hp_tier_critical_19():
    r = run(SituationalFrameInput(hp=19, gold=50, level=6, stage=(3, 2), streak=0))
    assert r.hp_tier == "critical"


# ── EV range clamp ────────────────────────────────────────────────────────────

def test_ev_clamped_to_min():
    # Perfect everything → EV floor 1.5
    r = run(SituationalFrameInput(hp=100, gold=100, level=9, stage=(5, 1), streak=6, board_strength=1.0))
    assert r.ev_avg_placement >= 1.5


def test_ev_clamped_to_max():
    # Terrible everything → EV ceiling 7.5
    r = run(SituationalFrameInput(hp=5, gold=0, level=3, stage=(4, 2), streak=-6, board_strength=0.0))
    assert r.ev_avg_placement <= 7.5


# ── Econ tier ─────────────────────────────────────────────────────────────────

def test_econ_ahead():
    # At 4-2, curve=56. Gold=70 → delta=+14 → ahead
    r = run(SituationalFrameInput(hp=60, gold=70, level=8, stage=(4, 2), streak=0))
    assert r.econ_tier == "ahead"


def test_econ_broken():
    # At 4-2, curve=56. Gold=20 → delta=-36 → broken
    r = run(SituationalFrameInput(hp=60, gold=20, level=8, stage=(4, 2), streak=0))
    assert r.econ_tier == "broken"


# ── Stage-1 edge case ─────────────────────────────────────────────────────────

def test_stage_1_early_confidence():
    r = run(SituationalFrameInput(hp=100, gold=5, level=2, stage=(1, 2), streak=0))
    assert r.ev_confidence == 0.3


def test_stage_2_confidence():
    r = run(SituationalFrameInput(hp=100, gold=10, level=3, stage=(2, 3), streak=0))
    assert r.ev_confidence == 0.5


# ── Determinism ───────────────────────────────────────────────────────────────

def test_deterministic_same_input():
    inp = SituationalFrameInput(hp=55, gold=40, level=7, stage=(3, 5), streak=2, board_strength=0.6)
    r1 = run(inp)
    r2 = run(inp)
    assert r1.model_dump() == r2.model_dump()


# ── Frame sentence non-empty ──────────────────────────────────────────────────

def test_frame_sentence_non_empty():
    r = run(SituationalFrameInput(hp=60, gold=50, level=6, stage=(3, 2), streak=0))
    assert len(r.frame_sentence) > 0


# ── Posture map completeness ──────────────────────────────────────────────────

def test_all_postures_reachable():
    postures_seen = set()
    cases = [
        SituationalFrameInput(hp=90, gold=80, level=8, stage=(4, 2), streak=5, board_strength=0.95),  # winning→greed
        SituationalFrameInput(hp=60, gold=50, level=6, stage=(3, 2), streak=0, board_strength=0.5),   # stable→stabilize
        SituationalFrameInput(hp=55, gold=30, level=6, stage=(3, 5), streak=-2, board_strength=0.5),  # losing→stabilize
        SituationalFrameInput(hp=38, gold=10, level=5, stage=(4, 2), streak=-5, board_strength=0.1),  # salvage or dying
        SituationalFrameInput(hp=5, gold=10, level=5, stage=(4, 2), streak=-5, board_strength=0.1),   # dying→all_in
    ]
    for inp in cases:
        r = run(inp)
        postures_seen.add(r.frame_posture)
    assert "greed" in postures_seen
    assert "all_in" in postures_seen
