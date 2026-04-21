"""Tests for advisor deterministic fallback (Task 3).

Verifies that when the LLM path raises any exception, advise_stream()
falls through to templates.render_deterministic_verdict() without hanging
or crashing. The overlay must always receive actionable events.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest
from advisor import advise_stream, _advise_stream_llm
from templates import render_deterministic_verdict
from schemas import (
    ActionCandidate, ActionScores, ActionType, GameState,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _fixture_state() -> GameState:
    return GameState(
        stage="3-2", gold=30, hp=70, level=6,
        xp_current=5, xp_needed=36, streak=0, set_id="17",
    )


def _fixture_action(action_type: ActionType = ActionType.ROLL_TO) -> ActionCandidate:
    return ActionCandidate(
        action_type=action_type,
        params={"gold_floor": 20} if action_type == ActionType.ROLL_TO else {},
        scores=ActionScores(tempo=1, econ=-1, hp_risk=0, board_strength=1, pivot_value=0),
        total_score=1.0,
        human_summary="Roll to 20g",
    )


# ── Template renderer tests ────────────────────────────────────────────────────

def test_deterministic_verdict_roll():
    v = render_deterministic_verdict(_fixture_state(), _fixture_action(), None, [])
    assert "20" in v.one_liner
    assert v.primary_action == ActionType.ROLL_TO
    assert v.confidence == "MEDIUM"
    assert v.warnings, "fallback verdict must have a warning noting LLM unavailable"


def test_deterministic_verdict_never_empty():
    """Every ActionType must produce a non-empty one_liner."""
    for at in ActionType:
        action = ActionCandidate(
            action_type=at,
            params={"champion": "Jinx"} if at == ActionType.BUY else {},
            scores=ActionScores(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0),
            total_score=0.0,
            human_summary="test",
        )
        v = render_deterministic_verdict(_fixture_state(), action, None, [])
        assert v.one_liner, f"ActionType {at} produced empty one_liner"


def test_deterministic_verdict_hold_econ():
    action = _fixture_action(ActionType.HOLD_ECON)
    v = render_deterministic_verdict(_fixture_state(), action, None, [])
    assert "30" in v.one_liner   # should reference current gold


def test_deterministic_verdict_buy():
    action = ActionCandidate(
        action_type=ActionType.BUY,
        params={"champion": "Jinx", "cost": 2},
        scores=ActionScores(tempo=0, econ=0, hp_risk=0, board_strength=0, pivot_value=0),
        total_score=0.0,
        human_summary="Buy Jinx",
    )
    v = render_deterministic_verdict(_fixture_state(), action, None, [])
    assert "Jinx" in v.one_liner


# ── Fallback integration tests ─────────────────────────────────────────────────

def test_advisor_timeout_falls_through(monkeypatch):
    """When LLM raises TimeoutError, fallback path emits correct events."""
    def always_timeout(*args, **kwargs):
        raise TimeoutError("simulated first-token timeout")

    monkeypatch.setattr("advisor._advise_stream_llm", always_timeout)

    events = list(advise_stream(
        state=_fixture_state(), fires=[], actions=[_fixture_action()], comps=[],
        client=None, capture_id=None,
    ))

    event_types = [e[0] for e in events]
    assert "one_liner" in event_types, "fallback must emit one_liner"
    assert "final"     in event_types, "fallback must emit final"

    final_evt = next(e for e in events if e[0] == "final")
    assert final_evt[1]["__meta__"]["source"] == "deterministic_fallback"
    assert final_evt[1]["__meta__"]["parse_ok"] is True


def test_advisor_exception_falls_through(monkeypatch):
    """Any exception type (not just timeout) triggers fallback."""
    def always_500(*args, **kwargs):
        raise RuntimeError("simulated API 500")

    monkeypatch.setattr("advisor._advise_stream_llm", always_500)

    events = list(advise_stream(
        state=_fixture_state(), fires=[], actions=[_fixture_action()], comps=[],
        client=None, capture_id=None,
    ))
    assert any(e[0] == "final" for e in events)
    final_evt = next(e for e in events if e[0] == "final")
    assert "500" in final_evt[1]["__meta__"]["error"]


def test_advisor_empty_candidates_safe_message(monkeypatch):
    """If recommender returned no actions, fallback still produces something."""
    def always_fail(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr("advisor._advise_stream_llm", always_fail)

    events = list(advise_stream(
        state=_fixture_state(), fires=[], actions=[], comps=[],
        client=None, capture_id=None,
    ))
    final_evt = next(e for e in events if e[0] == "final")
    assert final_evt[1]["verdict"] is not None
    assert final_evt[1]["verdict"].confidence == "LOW"
