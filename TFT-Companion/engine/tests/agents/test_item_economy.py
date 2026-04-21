"""Tests for Agent 6 — ItemEconomy (rule pre-filter + mocked LLM)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from engine.agents.item_economy import (
    ItemEconomyAgent,
    _find_best_slam,
    _find_two_star_last_item,
    _parse_llm_response,
    _rule_filter,
)
from engine.agents.orchestrator import AgentContext
from engine.agents.schemas import ItemEconomyResult


RECIPES = {
    "JeweledGauntlet":   ["Glove", "Rod"],
    "ArchangelsStaff":   ["Tear", "Rod"],
    "GuinsoosRageblade": ["RB", "Rod"],
    "BlueBuff":          ["Tear", "Tear"],
    "InfinityEdge":      ["BF", "Glove"],
}

VEX_SLOT = {
    "api_name": "TFT17_Vex",
    "display_name": "Vex",
    "cost": 5,
    "star": 2,
    "items_held": [],
    "bis_trios": [["JeweledGauntlet", "ArchangelsStaff", "GuinsoosRageblade"]],
    "value_class": "S",
}


def ctx(**kwargs) -> AgentContext:
    defaults = dict(
        hp=60, gold=50, level=7, stage=(4, 2), streak=0,
        board_strength=0.5, bench_components=[], item_recipes=RECIPES,
        board_slots=[], augments_picked=[], augment_tiers=[],
        target_comp_apis=[],
    )
    defaults.update(kwargs)
    return AgentContext(**defaults)


def _llm_msg(**data):
    payload = json.dumps(data)
    content = MagicMock()
    content.text = payload
    msg = MagicMock()
    msg.content = [content]
    return msg


def run(c: AgentContext) -> ItemEconomyResult:
    return asyncio.run(ItemEconomyAgent().run(ctx=c))


# ── Rule: never slam ──────────────────────────────────────────────────────────

def test_rule_too_early_holds():
    c = ctx(bench_components=["Glove"], stage=(2, 1))
    r = _rule_filter(c)
    assert r is not None
    assert r.decision == "hold"
    assert r.risk_tag == "safe"


def test_rule_two_comps_early_holds():
    c = ctx(bench_components=["Glove", "Rod"], stage=(2, 3))
    r = _rule_filter(c)
    assert r is not None
    assert r.decision == "hold"


# ── Rule: always slam ─────────────────────────────────────────────────────────

def test_rule_desperate_hp_slams():
    c = ctx(
        hp=30, stage=(4, 2),
        bench_components=["Glove", "Rod"],
        board_slots=[VEX_SLOT],
    )
    r = _rule_filter(c)
    assert r is not None
    assert r.decision == "slam_now"
    assert r.slam is not None
    assert r.risk_tag == "moderate"


def test_rule_winning_streak_slams():
    c = ctx(
        hp=70, streak=4,
        bench_components=["Glove", "Rod"],
        board_slots=[VEX_SLOT],
    )
    r = _rule_filter(c)
    assert r is not None
    assert r.decision == "slam_now"
    assert r.risk_tag == "safe"


def test_rule_two_star_last_bis_item_slams():
    slot = {
        **VEX_SLOT,
        "star": 2,
        "items_held": ["JeweledGauntlet", "ArchangelsStaff"],
    }
    # Missing GuinsoosRageblade = RB + Rod
    c = ctx(bench_components=["RB", "Rod"], board_slots=[slot])
    r = _rule_filter(c)
    assert r is not None
    assert r.decision == "slam_now"
    assert r.slam is not None
    assert r.slam.is_bis is True
    assert r.slam.item_id == "GuinsoosRageblade"


def test_rule_ambiguous_returns_none():
    # 4 components, mid-game, no streak, healthy HP
    c = ctx(
        hp=65, streak=0, stage=(3, 2),
        bench_components=["Glove", "Rod", "Tear", "BF"],
    )
    r = _rule_filter(c)
    assert r is None


# ── Slam helpers ──────────────────────────────────────────────────────────────

def test_find_best_slam_picks_bis_item():
    c = ctx(
        bench_components=["Glove", "Rod"],
        board_slots=[VEX_SLOT],
    )
    slam = _find_best_slam(c)
    assert slam is not None
    assert slam.item_id == "JeweledGauntlet"  # in Vex BIS trio
    assert slam.is_bis is True


def test_find_best_slam_empty_bench_returns_none():
    c = ctx(bench_components=[], board_slots=[VEX_SLOT])
    assert _find_best_slam(c) is None


def test_find_two_star_last_item_finds_correctly():
    slot = {**VEX_SLOT, "star": 2, "items_held": ["JeweledGauntlet", "ArchangelsStaff"]}
    c = ctx(bench_components=["RB", "Rod"], board_slots=[slot])
    result = _find_two_star_last_item(c)
    assert result is not None
    assert result.item_id == "GuinsoosRageblade"
    assert result.is_bis is True


def test_find_two_star_last_item_not_buildable_returns_none():
    # Missing the right components
    slot = {**VEX_SLOT, "star": 2, "items_held": ["JeweledGauntlet", "ArchangelsStaff"]}
    c = ctx(bench_components=["BF", "BF"], board_slots=[slot])  # can build IE, not Guinsoo
    assert _find_two_star_last_item(c) is None


# ── LLM path (mocked) ─────────────────────────────────────────────────────────

def test_llm_hold_decision():
    mock_msg = _llm_msg(decision="hold", item_id="", holder_api="", holder_display="",
                         reasoning="Wait for better item.", risk_tag="safe")
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("engine.agents.item_economy.anthropic.AsyncAnthropic", return_value=mock_client):
        c = ctx(hp=65, streak=0, stage=(3, 2),
                bench_components=["Glove", "Rod", "Tear", "BF"])
        r = run(c)

    assert r.decision == "hold"
    assert r.agent_name == "item_economy"
    assert not r.used_fallback


def test_llm_slam_decision():
    mock_msg = _llm_msg(
        decision="slam_now",
        item_id="JeweledGauntlet",
        holder_api="TFT17_Vex",
        holder_display="Vex",
        reasoning="Complete BIS on Vex.",
        risk_tag="safe",
    )
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("engine.agents.item_economy.anthropic.AsyncAnthropic", return_value=mock_client):
        c = ctx(hp=65, streak=0, stage=(3, 2),
                bench_components=["Glove", "Rod", "Tear", "BF"],
                board_slots=[VEX_SLOT])
        r = run(c)

    assert r.decision == "slam_now"
    assert r.slam is not None
    assert r.slam.item_id == "JeweledGauntlet"


# ── Parse edge cases ──────────────────────────────────────────────────────────

def test_parse_invalid_decision_defaults_hold():
    raw = json.dumps({"decision": "YOLO", "reasoning": "x", "risk_tag": "safe"})
    c = ctx()
    r = _parse_llm_response(raw, c)
    assert r.decision == "hold"


def test_parse_no_json_fallback():
    c = ctx()
    r = _parse_llm_response("cannot help", c)
    assert r.used_fallback is True
    assert r.decision == "hold"


# ── Fallback ──────────────────────────────────────────────────────────────────

def test_fallback_returns_item_economy_result():
    fb = ItemEconomyAgent()._fallback(ctx(stage=(3, 2), bench_components=["Glove", "Rod", "Tear"]))
    assert isinstance(fb, ItemEconomyResult)
    assert fb.agent_name == "item_economy"


# ── Full round-trip ───────────────────────────────────────────────────────────

def test_agent_result_structure():
    # Desperate HP triggers rule → no LLM needed
    c = ctx(hp=30, stage=(4, 2), bench_components=["Glove", "Rod"], board_slots=[VEX_SLOT])
    r = run(c)
    assert isinstance(r, ItemEconomyResult)
    assert r.agent_name == "item_economy"
    assert r.decision in ("slam_now", "hold", "gamble")
    assert r.risk_tag in ("safe", "moderate", "risky")


def test_result_serializes():
    c = ctx(hp=30, stage=(4, 2), bench_components=["Glove", "Rod"], board_slots=[VEX_SLOT])
    r = run(c)
    d = r.model_dump()
    assert "decision" in d
    assert "risk_tag" in d
