"""Phase 6 tests — advisor. Structure/import tests run without API key.
Live API tests are marked slow and skipped in CI.
"""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest
from schemas import GameState, BoardUnit, ActionType


def test_advisor_model_is_haiku():
    from advisor import MODEL
    assert "haiku" in MODEL.lower()


def test_advisor_prompt_version_is_v2():
    from advisor import PROMPT_VERSION
    assert PROMPT_VERSION == "advisor_v2"


def test_advisor_tools_defined():
    from advisor import TOOLS
    tool_names = {t["name"] for t in TOOLS}
    assert "econ_p_hit" in tool_names
    assert "comp_details" in tool_names


def test_build_user_payload_structure():
    from advisor import _build_user_payload
    from schemas import GameState, Fire, ActionCandidate, ActionScores, ActionType
    from comp_planner import load_archetypes, score_archetype
    from pool import PoolTracker
    from knowledge import load_set
    import json

    set17 = load_set("17")
    state = GameState(stage="3-2", gold=30, hp=70, level=6,
                      xp_current=0, xp_needed=36, streak=0, set_id="17")
    fires: list[Fire] = []
    null_scores = ActionScores(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0)
    actions = [
        ActionCandidate(
            action_type=ActionType.HOLD_ECON, params={},
            scores=null_scores, total_score=0, human_summary="Hold econ",
        )
    ]
    pt = PoolTracker(set17)
    archs = load_archetypes()
    comps = [score_archetype(archs[0], state, pt, set17)]

    payload_str = _build_user_payload(state, fires, actions, comps)
    payload = json.loads(payload_str)
    assert "state" in payload
    assert "rule_fires" in payload
    assert "top_3_actions" in payload
    assert "top_3_comps" in payload
    assert payload["state"]["stage"] == "3-2"
    assert len(payload["top_3_actions"]) == 1


def test_parse_verdict_valid():
    from advisor import _parse_verdict
    from schemas import ActionCandidate, ActionScores, ActionType

    null_scores = ActionScores(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0)
    actions = [
        ActionCandidate(
            action_type=ActionType.HOLD_ECON, params={},
            scores=null_scores, total_score=0, human_summary="Hold econ",
        ),
        ActionCandidate(
            action_type=ActionType.ROLL_TO, params={"gold_floor": 20},
            scores=null_scores, total_score=1, human_summary="Roll to 20g",
        ),
    ]
    rec = {
        "one_liner": "Hold to 50g for interest cap.",
        "confidence": "HIGH",
        "tempo_read": "ON_PACE",
        "primary_action": "HOLD_ECON",
        "chosen_candidate_index": 0,
        "reasoning": "You have 48g. Holding keeps 4g interest.",
        "considerations": [],
        "warnings": [],
        "data_quality_note": None,
    }
    verdict = _parse_verdict(rec, actions)
    assert verdict is not None
    assert verdict.primary_action == ActionType.HOLD_ECON
    assert verdict.chosen_candidate.action_type == ActionType.HOLD_ECON
    assert verdict.confidence == "HIGH"


def test_parse_verdict_out_of_bounds_index():
    """chosen_candidate_index=99 should clamp to last candidate."""
    from advisor import _parse_verdict
    from schemas import ActionCandidate, ActionScores, ActionType

    null_scores = ActionScores(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0)
    actions = [
        ActionCandidate(
            action_type=ActionType.HOLD_ECON, params={},
            scores=null_scores, total_score=0, human_summary="Hold",
        )
    ]
    rec = {
        "one_liner": "x", "confidence": "LOW", "tempo_read": "BEHIND",
        "primary_action": "HOLD_ECON", "chosen_candidate_index": 99,
        "reasoning": "x", "considerations": [], "warnings": [], "data_quality_note": None,
    }
    verdict = _parse_verdict(rec, actions)
    assert verdict is not None
    assert verdict.chosen_candidate == actions[0]


@pytest.mark.slow
def test_advisor_live_returns_verdict():
    """Requires ANTHROPIC_API_KEY. Skip in CI."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("No API key")
    pytest.skip("Enable after Phase 6 with recorded API responses")
