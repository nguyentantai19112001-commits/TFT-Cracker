"""Tests for Agent 8 — AugmentQuality (probability table, rule-based)."""
from __future__ import annotations

import asyncio
import pytest

from engine.agents.augment_quality import (
    AugmentQualityAgent,
    AugmentQualityInput,
    _normalize_tier,
    _predict_tier_probs,
)
from engine.agents.schemas import AugmentQualityResult
from engine.knowledge.loader import constants, reset_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


def run(inp: AugmentQualityInput) -> AugmentQualityResult:
    return asyncio.run(AugmentQualityAgent().run(ctx=inp))


# ── _normalize_tier ───────────────────────────────────────────────────────────

def test_normalize_silver():
    assert _normalize_tier("silver") == "S"


def test_normalize_gold():
    assert _normalize_tier("gold") == "G"


def test_normalize_prismatic():
    assert _normalize_tier("prismatic") == "P"


def test_normalize_uppercase():
    assert _normalize_tier("G") == "G"
    assert _normalize_tier("S") == "S"


def test_normalize_mixed_case():
    assert _normalize_tier("Gold") == "G"
    assert _normalize_tier("Silver") == "S"
    assert _normalize_tier("Prismatic") == "P"


# ── Stage 2-1 probabilities (no prior history) ───────────────────────────────

def test_stage_2_1_marginal_sums_to_one():
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((2, 1), [], dist)
    assert abs(probs["silver"] + probs["gold"] + probs["prismatic"] - 1.0) < 1e-3


def test_stage_2_1_gold_dominant():
    # Gold is 62% at 2-1
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((2, 1), [], dist)
    assert probs["gold"] > 0.5


def test_stage_2_1_silver():
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((2, 1), [], dist)
    assert abs(probs["silver"] - 0.28) < 0.01


def test_stage_2_1_prismatic():
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((2, 1), [], dist)
    assert abs(probs["prismatic"] - 0.10) < 0.01


# ── Stage 3-2 (after 2-1 pick) ───────────────────────────────────────────────

def test_stage_3_2_returns_probabilities():
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((3, 2), ["G"], dist)
    assert "silver" in probs and "gold" in probs and "prismatic" in probs


def test_stage_3_2_probs_positive():
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((3, 2), ["G"], dist)
    assert all(v >= 0 for v in probs.values())


# ── Stage 4-2 conditional probabilities ──────────────────────────────────────

def test_stage_4_2_G_G_gold_dominant():
    # Gold/Gold history → gold prob 0.88
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((4, 2), ["G", "G"], dist)
    assert probs["gold"] > 0.8


def test_stage_4_2_G_G_values():
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((4, 2), ["G", "G"], dist)
    assert abs(probs["gold"] - 0.88) < 0.01
    assert abs(probs["prismatic"] - 0.12) < 0.01
    assert abs(probs["silver"] - 0.00) < 0.01


def test_stage_4_2_S_P_prismatic_guaranteed():
    # Silver/Prismatic → prismatic: 1.00
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((4, 2), ["S", "P"], dist)
    assert abs(probs["prismatic"] - 1.00) < 0.01


def test_stage_4_2_G_P_has_silver():
    # Gold/Prismatic → silver: 0.353
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((4, 2), ["G", "P"], dist)
    assert probs["silver"] > 0.30


def test_stage_4_2_S_S_split():
    # Silver/Silver → gold: 0.50, prismatic: 0.50
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((4, 2), ["S", "S"], dist)
    assert abs(probs["gold"] - 0.50) < 0.01
    assert abs(probs["prismatic"] - 0.50) < 0.01


def test_stage_4_2_G_S_mostly_gold():
    # Gold/Silver → gold: 0.90
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((4, 2), ["G", "S"], dist)
    assert abs(probs["gold"] - 0.90) < 0.01


def test_stage_4_2_one_prior_only():
    # Only 2-1 pick known → uses stage marginal
    k = constants()
    dist = k["augment_distribution"]
    probs = _predict_tier_probs((4, 2), ["G"], dist)
    assert probs["gold"] > 0.5  # gold dominant at 4-2 marginal


# ── Full agent output structure ───────────────────────────────────────────────

def test_result_has_tier_probabilities():
    r = run(AugmentQualityInput(upcoming_stage=(2, 1), prior_tiers=[]))
    assert r.tier_probabilities is not None
    assert r.tier_probabilities.silver >= 0
    assert r.tier_probabilities.gold >= 0
    assert r.tier_probabilities.prismatic >= 0


def test_result_upcoming_stage_preserved():
    r = run(AugmentQualityInput(upcoming_stage=(3, 2), prior_tiers=["G"]))
    assert r.upcoming_stage == (3, 2)


def test_result_summary_non_empty():
    r = run(AugmentQualityInput(upcoming_stage=(4, 2), prior_tiers=["G", "G"]))
    assert len(r.probability_conditional_on_history) > 0


def test_result_expected_value_tier():
    # At 2-1, gold dominant → ev tier should be G
    r = run(AugmentQualityInput(upcoming_stage=(2, 1), prior_tiers=[]))
    assert r.tier_probabilities.expected_value_tier == "G"


def test_result_serializes():
    r = run(AugmentQualityInput(upcoming_stage=(4, 2), prior_tiers=["G", "G"]))
    d = r.model_dump()
    assert "tier_probabilities" in d
    assert "upcoming_stage" in d


def test_deterministic():
    inp = AugmentQualityInput(upcoming_stage=(4, 2), prior_tiers=["G", "P"])
    r1 = run(inp)
    r2 = run(inp)
    assert r1.model_dump() == r2.model_dump()
