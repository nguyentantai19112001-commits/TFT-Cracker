"""Tests for Agent 4 — TempoAgent (rule pre-filter + mocked LLM)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from engine.agents.tempo_agent import (
    TempoAgentAgent,
    _parse_llm_response,
    _render_display,
    _rule_filter,
)
from engine.agents.orchestrator import AgentContext
from engine.agents.schemas import TempoAgentResult


def ctx(**kwargs) -> AgentContext:
    defaults = dict(
        hp=60, gold=50, level=7, stage=(4, 2), streak=0,
        board_strength=0.5, bench_components=[], item_recipes={},
        board_slots=[], augments_picked=[], augment_tiers=[],
        target_comp_apis=[],
    )
    defaults.update(kwargs)
    return AgentContext(**defaults)


def _llm_msg(template: str, slots: dict, subline: str = "test", priority: str = "medium"):
    payload = json.dumps({"template": template, "slots": slots, "subline": subline, "priority": priority})
    content = MagicMock()
    content.text = payload
    msg = MagicMock()
    msg.content = [content]
    return msg


def run(c: AgentContext) -> TempoAgentResult:
    return asyncio.run(TempoAgentAgent().run(ctx=c))


# ── Rule pre-filter ────────────────────────────────────────────────────────────

def test_rule_early_winning_streak_holds():
    r = _rule_filter(ctx(stage=(2, 3), hp=85, streak=3, gold=30))
    assert r is not None
    assert r.verdict_template == "Hold — build interest"
    assert r.action_priority == "high"


def test_rule_rich_healthy_late_levels_up():
    r = _rule_filter(ctx(stage=(4, 2), hp=60, gold=55, level=7))
    assert r is not None
    assert r.verdict_template == "Level to {N}"
    assert r.verdict_slots["N"] == 8


def test_rule_dying_with_units_rolls_down():
    board = [{"api_name": "TFT17_Vex", "display_name": "Vex", "cost": 5}]
    r = _rule_filter(ctx(stage=(4, 2), hp=30, board_slots=board))
    assert r is not None
    assert r.verdict_template == "Roll down for {unit}"
    assert r.verdict_slots["unit"] == "Vex"
    assert r.action_priority == "critical"


def test_rule_dying_no_units_all_in():
    r = _rule_filter(ctx(stage=(4, 2), hp=25, board_slots=[]))
    assert r is not None
    assert r.verdict_template == "All-in roll at level {N}"
    assert r.action_priority == "critical"


def test_rule_ambiguous_returns_none():
    # Stage 3, mid HP, no streak — no deterministic rule fires
    r = _rule_filter(ctx(stage=(3, 2), hp=60, gold=30, streak=0))
    assert r is None


def test_rule_top_unit_picks_highest_cost():
    board = [
        {"api_name": "TFT17_Viktor", "display_name": "Viktor", "cost": 3},
        {"api_name": "TFT17_Vex", "display_name": "Vex", "cost": 5},
    ]
    r = _rule_filter(ctx(stage=(4, 2), hp=30, board_slots=board))
    assert r is not None
    assert r.verdict_slots["unit"] == "Vex"


# ── Display rendering ──────────────────────────────────────────────────────────

def test_render_level():
    assert _render_display("Level to {N}", {"N": 8}) == "→ Level to 8"


def test_render_hold():
    assert _render_display("Hold — build interest", {}) == "→ Hold — build interest"


def test_render_bad_slots_falls_back():
    result = _render_display("Roll down for {unit}", {})
    assert result.startswith("→")


# ── LLM path (mocked) ─────────────────────────────────────────────────────────

def test_llm_level_verdict():
    mock_msg = _llm_msg("Level to {N}", {"N": 8}, "Level now for power spike.", "high")
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("engine.agents.tempo_agent.anthropic.AsyncAnthropic", return_value=mock_client):
        # Stage 3 → ambiguous, rule returns None, LLM fires
        r = run(ctx(stage=(3, 2), hp=60, gold=40, streak=0))

    assert r.verdict_template == "Level to {N}"
    assert r.verdict_slots == {"N": 8}
    assert r.verdict_display == "→ Level to 8"
    assert r.action_priority == "high"
    assert r.agent_name == "tempo_agent"
    assert not r.used_fallback


def test_llm_roll_verdict():
    mock_msg = _llm_msg("Roll down for {unit}", {"unit": "Viktor"}, "Viktor reroll at 7.", "critical")
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("engine.agents.tempo_agent.anthropic.AsyncAnthropic", return_value=mock_client):
        r = run(ctx(stage=(3, 2), hp=50, gold=25, streak=-1))

    assert r.verdict_template == "Roll down for {unit}"
    assert r.verdict_display == "→ Roll down for Viktor"
    assert r.action_priority == "critical"


# ── Parse edge cases ───────────────────────────────────────────────────────────

def test_parse_invalid_priority_clamps_to_medium():
    raw = json.dumps({"template": "Hold — build interest", "slots": {}, "subline": "x", "priority": "TURBO"})
    r = _parse_llm_response(raw)
    assert r.action_priority == "medium"


def test_parse_no_json_returns_fallback():
    r = _parse_llm_response("sorry, I cannot help with that")
    assert r.used_fallback is True
    assert r.verdict_template == "Hold — build interest"


def test_parse_slam_verdict():
    raw = json.dumps({
        "template": "Slam {item} on {unit}",
        "slots": {"item": "Rabadon", "unit": "Vex"},
        "subline": "BIS completes now.",
        "priority": "high",
    })
    r = _parse_llm_response(raw)
    assert r.verdict_display == "→ Slam Rabadon on Vex"
    assert r.verdict_slots["item"] == "Rabadon"


# ── Fallback ───────────────────────────────────────────────────────────────────

def test_fallback_returns_tempo_result():
    fb = TempoAgentAgent()._fallback(ctx(stage=(3, 2), hp=60, gold=30))
    assert isinstance(fb, TempoAgentResult)
    assert fb.agent_name == "tempo_agent"


def test_fallback_uses_rule_when_applicable():
    fb = TempoAgentAgent()._fallback(ctx(stage=(2, 3), hp=90, streak=4))
    assert fb.verdict_template == "Hold — build interest"


# ── Full round-trip (rule-based, no mock needed) ──────────────────────────────

def test_agent_result_type_and_fields():
    # Rule fires: rich+healthy at stage 4
    r = run(ctx(stage=(4, 2), hp=60, gold=60, level=7))
    assert isinstance(r, TempoAgentResult)
    assert r.agent_name == "tempo_agent"
    assert r.verdict_display.startswith("→")
    assert r.action_priority in ("critical", "high", "medium", "low")


def test_agent_name_is_tempo_agent():
    r = run(ctx(stage=(4, 2), hp=60, gold=60, level=7))
    assert r.agent_name == "tempo_agent"


def test_result_serializes():
    r = run(ctx(stage=(4, 2), hp=60, gold=60, level=7))
    d = r.model_dump()
    assert "verdict_template" in d
    assert "verdict_display" in d
    assert "action_priority" in d
