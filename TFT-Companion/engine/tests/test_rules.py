"""Phase 3 acceptance tests — rule engine. See skills/rules/SKILL.md."""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
# Always force augie-v2/ to position 0 — parent dir also has rules.py and
# pool.py prepends TFT-Companion/ to sys.path, which would shadow ours otherwise.
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import yaml
import pytest
from schemas import GameState, BoardUnit, TraitActivation
from rules import ALL_RULES, evaluate

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "rule_scenarios.yaml"
FIXTURES = yaml.safe_load(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _make_state(**kw) -> GameState:
    defaults = dict(
        stage="3-2", gold=30, hp=70, level=6,
        xp_current=0, xp_needed=36, streak=0, set_id="17",
        board=[], bench=[], shop=[], active_traits=[], item_components_on_bench=[],
    )
    defaults.update(kw)
    return GameState(**defaults)


# ──────────────────────────────────────────────────────────────────────────────
# Parametrized fixture tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("entry", FIXTURES["rules"])
def test_rule_positive_fires(entry):
    state = _make_state(**entry["positive"])
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert entry["id"] in ids, (
        f"Expected {entry['id']} to fire for {entry['desc']}, got: {ids}"
    )


@pytest.mark.parametrize("entry", FIXTURES["rules"])
def test_rule_negative_silent(entry):
    state = _make_state(**entry["negative"])
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert entry["id"] not in ids, (
        f"Expected {entry['id']} to be silent for negative case, got: {ids}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Coverage / contract tests
# ──────────────────────────────────────────────────────────────────────────────

def test_total_rule_count():
    assert len(ALL_RULES) >= 39  # ROLL_CONTESTED_BAIL removed in 3.5a


def test_no_rule_crashes_on_empty_state():
    state = _make_state()
    # Must not raise — evaluate() swallows exceptions internally
    fires = evaluate(state, None, None, None)
    assert isinstance(fires, list)


def test_fires_sorted_by_severity_desc():
    state = _make_state(gold=8, hp=20, streak=-3, stage="4-2", level=6)
    fires = evaluate(state, None, None, None)
    severities = [f.severity for f in fires]
    assert severities == sorted(severities, reverse=True)


def test_hp_urgent_highest_priority():
    """HP_URGENT (sev=1.0) must be first when it fires."""
    state = _make_state(hp=20, gold=20)
    fires = evaluate(state, None, None, None)
    assert fires, "Expected at least one fire"
    assert fires[0].rule_id in ("HP_URGENT", "ROLL_HP_PANIC")
    assert fires[0].severity == 1.0


def test_trait_uncommitted_fires_after_3_2():
    state = _make_state(
        stage="3-3",
        active_traits=[TraitActivation(trait="Sniper", count=1, tier="inactive")],
    )
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "TRAIT_UNCOMMITTED" in ids


def test_trait_uncommitted_silent_before_3_2():
    state = _make_state(
        stage="2-5",
        active_traits=[],
    )
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "TRAIT_UNCOMMITTED" not in ids


def test_item_slam_mandate():
    state = _make_state(
        stage="3-5",
        item_components_on_bench=["B.F. Sword", "Chain Vest", "Recurve Bow"],
    )
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "ITEM_SLAM_MANDATE" in ids


def test_board_under_cap():
    state = _make_state(level=7, board=[BoardUnit(champion="Jinx", star=1)])
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "BOARD_UNDER_CAP" in ids


def test_realm_of_gods_fires_at_4_6():
    state = _make_state(stage="4-6", hp=60, streak=0)
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "REALM_OF_GODS_NEXT" in ids


def test_stage_4_2_fastspike():
    state = _make_state(stage="4-2", level=8, gold=40)
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "STAGE_4_2_FASTSPIKE" in ids


def test_econ_interest_cap_hold():
    state = _make_state(gold=52)
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "ECON_INTEREST_CAP_HOLD" in ids


def test_hp_comfortable():
    state = _make_state(hp=90)
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "HP_COMFORTABLE" in ids


def test_streak_lose_cap_approaching():
    state = _make_state(streak=-5, hp=50)
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "STREAK_LOSE_CAP_APPROACHING" in ids


def test_streak_win_cap_approaching():
    state = _make_state(streak=5, hp=70)
    fires = evaluate(state, None, None, None)
    ids = {f.rule_id for f in fires}
    assert "STREAK_WIN_CAP_APPROACHING" in ids
