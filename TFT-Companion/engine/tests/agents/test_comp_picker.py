"""Tests for Agent 2 — CompPicker (rule scoring + mocked Sonnet LLM)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.agents.comp_picker import (
    CompPickerAgent,
    _compute_fit,
    _fallback_result,
    _score_archetypes,
    reset_archetypes_cache,
    _load_archetypes,
)
from engine.agents.orchestrator import AgentContext
from engine.agents.schemas import CompPickerResult


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_archetypes_cache()
    yield
    reset_archetypes_cache()


def ctx(**kwargs) -> AgentContext:
    defaults = dict(
        hp=60, gold=50, level=7, stage=(4, 2), streak=0,
        board_strength=0.5, bench_components=[], item_recipes={},
        board_slots=[], augments_picked=[], augment_tiers=[],
        target_comp_apis=[],
    )
    defaults.update(kwargs)
    return AgentContext(**defaults)


def _llm_msg(items: list[dict]):
    payload = json.dumps(items)
    content = MagicMock()
    content.text = payload
    msg = MagicMock()
    msg.content = [content]
    return msg


def run(c: AgentContext) -> CompPickerResult:
    return asyncio.run(CompPickerAgent().run(ctx=c))


# ── Scoring — unit overlap ─────────────────────────────────────────────────────

def test_unit_overlap_improves_score():
    arch = {"core_units": ["TFT17_Vex", "TFT17_Blitzcrank", "TFT17_Bard"], "contest_rate": 0.0}
    board_full = {"TFT17_Vex", "TFT17_Blitzcrank", "TFT17_Bard"}
    board_empty = set()

    score_full = _compute_fit(ctx(), arch, board_full, set())
    score_empty = _compute_fit(ctx(), arch, board_empty, set())

    assert score_full > score_empty


def test_full_unit_overlap_score():
    arch = {"core_units": ["TFT17_Vex", "TFT17_Blitzcrank"], "contest_rate": 0.0}
    score = _compute_fit(ctx(), arch, {"TFT17_Vex", "TFT17_Blitzcrank"}, set())
    assert score == pytest.approx(0.55, abs=0.01)


# ── Scoring — augment fit ─────────────────────────────────────────────────────

def test_aug_fit_bonus_on_match():
    arch = {
        "core_units": [],
        "augments": {"prismatic_s": ["LateGameSpecialist"]},
        "contest_rate": 0.0,
    }
    score_match = _compute_fit(ctx(), arch, set(), {"lategamespecialist"})
    score_no_match = _compute_fit(ctx(), arch, set(), set())
    assert score_match > score_no_match


def test_aug_fit_case_insensitive():
    arch = {"core_units": [], "augments": {"gold_s": ["GildedSteel"]}, "contest_rate": 0.0}
    score = _compute_fit(ctx(), arch, set(), {"gildedsteel"})
    assert score == pytest.approx(0.25, abs=0.01)


# ── Scoring — stage gate and contest penalty ──────────────────────────────────

def test_stage_gate_penalty_when_too_early():
    # Give the arch a unit so unit_overlap produces a non-zero base score
    arch = {"core_units": ["TFT17_Vex"], "stage_gate": [4, 2], "contest_rate": 0.0}
    board = {"TFT17_Vex"}
    score_early = _compute_fit(ctx(stage=(2, 1)), arch, board, set())
    score_ready = _compute_fit(ctx(stage=(4, 2)), arch, board, set())
    assert score_ready > score_early


def test_contest_penalty_reduces_score():
    # Need a non-zero base score so the penalty is observable
    arch_low = {"core_units": ["TFT17_Vex"], "contest_rate": 0.1}
    arch_high = {"core_units": ["TFT17_Vex"], "contest_rate": 0.9}
    board = {"TFT17_Vex"}
    score_low = _compute_fit(ctx(), arch_low, board, set())
    score_high = _compute_fit(ctx(), arch_high, board, set())
    assert score_low > score_high


def test_score_never_negative():
    arch = {"core_units": [], "stage_gate": [5, 1], "contest_rate": 1.0}
    score = _compute_fit(ctx(stage=(1, 1)), arch, set(), set())
    assert score >= 0.0


# ── Score sorting ─────────────────────────────────────────────────────────────

def test_score_archetypes_sorted_descending():
    archetypes = _load_archetypes()
    # With vex units on board, vex_9_5 should rank highly
    board = [
        {"api_name": "TFT17_Vex", "display_name": "Vex"},
        {"api_name": "TFT17_Blitzcrank", "display_name": "Blitz"},
    ]
    c = ctx(board_slots=board)
    scored = _score_archetypes(c, archetypes)
    assert all(scored[i][0] >= scored[i+1][0] for i in range(len(scored)-1))


def test_vex_board_ranks_vex_comp_high():
    # All 8 vex_9_5 core units + matching augment → 0.55 + 0.25 - 0.06 = 0.74
    # Beats redeemer (1/1 overlap, no aug match) at 0.5275
    archetypes = _load_archetypes()
    all_vex_cores = [
        "TFT17_Vex", "TFT17_Blitzcrank", "TFT17_Bard", "TFT17_Shen",
        "TFT17_Rammus", "TFT17_Karma", "TFT17_Mordekaiser", "TFT17_Rhaast",
    ]
    board = [{"api_name": api} for api in all_vex_cores]
    c = ctx(board_slots=board, stage=(4, 2), augments_picked=["LateGameSpecialist"])
    scored = _score_archetypes(c, archetypes)
    top_id = scored[0][1]
    assert top_id == "vex_9_5"


# ── LLM path (mocked) ─────────────────────────────────────────────────────────

def test_llm_respects_returned_order():
    # Return viktor_b4l first (even though scoring might rank vex higher)
    llm_response = [
        {"archetype_id": "viktor_b4l", "why_this_fits": "Viktor 2★ on board.", "why_not_the_others": "Vex requires fast 9."},
        {"archetype_id": "vex_9_5", "why_this_fits": "Vex works too.", "why_not_the_others": "Slower payoff."},
        {"archetype_id": "nami_space_groove", "why_this_fits": "Alternative.", "why_not_the_others": "Lower ceiling."},
    ]
    mock_msg = _llm_msg(llm_response)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("engine.agents.comp_picker.anthropic.AsyncAnthropic", return_value=mock_client):
        board = [{"api_name": "TFT17_Viktor"}, {"api_name": "TFT17_Vex"}]
        r = run(ctx(board_slots=board, stage=(4, 2)))

    assert r.top_comp.archetype_id == "viktor_b4l"
    assert len(r.alternates) == 2
    assert r.alternates[0].archetype_id == "vex_9_5"


def test_llm_why_fields_populated():
    llm_response = [
        {"archetype_id": "vex_9_5", "why_this_fits": "Best line.", "why_not_the_others": "Others need reroll."},
    ]
    mock_msg = _llm_msg(llm_response)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("engine.agents.comp_picker.anthropic.AsyncAnthropic", return_value=mock_client):
        board = [{"api_name": "TFT17_Vex"}]
        r = run(ctx(board_slots=board, stage=(4, 2)))

    assert r.top_comp.why_this_fits == "Best line."
    assert r.top_comp.why_not_the_others == "Others need reroll."


# ── Fallback ───────────────────────────────────────────────────────────────────

def test_fallback_returns_comp_picker_result():
    archetypes = _load_archetypes()
    board = [{"api_name": "TFT17_Vex"}, {"api_name": "TFT17_Viktor"}]
    c = ctx(board_slots=board)
    scored = _score_archetypes(c, archetypes)
    fb = _fallback_result(scored, archetypes)
    assert isinstance(fb, CompPickerResult)
    assert fb.agent_name == "comp_picker"
    assert fb.used_fallback is True


def test_fallback_has_top_comp():
    archetypes = _load_archetypes()
    board = [{"api_name": "TFT17_Vex"}, {"api_name": "TFT17_Blitzcrank"}]
    scored = _score_archetypes(ctx(board_slots=board), archetypes)
    fb = _fallback_result(scored, archetypes)
    assert fb.top_comp is not None
    assert fb.top_comp.archetype_id != ""


# ── Result structure ──────────────────────────────────────────────────────────

def test_agent_name():
    board = [{"api_name": "TFT17_Vex"}]
    # Use fallback since we're not mocking LLM
    archetypes = _load_archetypes()
    scored = _score_archetypes(ctx(board_slots=board), archetypes)
    fb = _fallback_result(scored, archetypes)
    assert fb.agent_name == "comp_picker"


def test_result_serializes():
    archetypes = _load_archetypes()
    board = [{"api_name": "TFT17_Vex"}, {"api_name": "TFT17_Viktor"}]
    scored = _score_archetypes(ctx(board_slots=board), archetypes)
    fb = _fallback_result(scored, archetypes)
    d = fb.model_dump()
    assert "top_comp" in d
    assert "alternates" in d
    assert "stage_gate" in d
