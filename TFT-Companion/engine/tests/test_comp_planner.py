"""Phase 4 acceptance tests — comp_planner. See skills/comp_planner/SKILL.md."""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest
from schemas import GameState, BoardUnit
from comp_planner import load_archetypes, top_k_comps, score_archetype
from pool import PoolTracker
from knowledge import load_set

SET17 = load_set("17")


def _state(**kw) -> GameState:
    defaults = dict(stage="3-2", gold=30, hp=70, level=6,
                    xp_current=0, xp_needed=36, streak=0, set_id="17")
    defaults.update(kw)
    return GameState(**defaults)


def test_all_archetypes_load():
    archs = load_archetypes()
    assert len(archs) >= 12
    for a in archs:
        assert len(a.core_units) >= 3
        assert a.target_level in (7, 8, 9, 10)
        assert a.tier in ("S", "A", "B", "C")
        assert a.playstyle in ("fast8", "reroll", "standard")


def test_top_comp_when_augment_matches():
    state = _state(augments=["Dark Star Soul"])
    pt = PoolTracker(SET17)
    top = top_k_comps(state, pt, load_archetypes(), SET17, k=3)
    ids = [c.archetype.archetype_id for c in top]
    assert "dark_star" in ids
    dark_star_cand = next(c for c in top if c.archetype.archetype_id == "dark_star")
    assert dark_star_cand.trait_fit > 0.25


def test_low_pool_does_not_crash():
    state = _state(
        stage="4-2", gold=40, hp=70, level=8,
        board=[BoardUnit(champion="Jhin", star=2)],
    )
    pt = PoolTracker(SET17)
    pt.observe_own_board(state.board, state.bench)
    top = top_k_comps(state, pt, load_archetypes(), SET17, k=5)
    dark_star = next((c for c in top if c.archetype.archetype_id == "dark_star"), None)
    assert dark_star is not None


def test_progress_raises_score():
    empty = _state(stage="4-1", level=7)
    with_board = _state(
        stage="4-1", level=7,
        board=[BoardUnit(champion=c, star=1) for c in ["Jhin", "Karma", "Kai'Sa"]],
    )
    pt = PoolTracker(SET17)
    dark_star = next(a for a in load_archetypes() if a.archetype_id == "dark_star")
    empty_score = score_archetype(dark_star, empty, pt, SET17).total_score
    loaded_score = score_archetype(dark_star, with_board, pt, SET17).total_score
    assert loaded_score > empty_score


def test_recommended_buys_excludes_owned():
    state = _state(
        stage="3-2", level=6,
        board=[BoardUnit(champion="Jhin", star=2)],
    )
    pt = PoolTracker(SET17)
    dark_star = next(a for a in load_archetypes() if a.archetype_id == "dark_star")
    cand = score_archetype(dark_star, state, pt, SET17)
    # Jhin is 2-star — it's "had", so next buys should not start with Jhin
    assert "Jhin" not in cand.missing_units


def test_top_k_respects_k():
    state = _state()
    pt = PoolTracker(SET17)
    archs = load_archetypes()
    assert len(top_k_comps(state, pt, archs, SET17, k=3)) == 3
    assert len(top_k_comps(state, pt, archs, SET17, k=5)) == 5


def test_scores_between_0_and_1():
    state = _state()
    pt = PoolTracker(SET17)
    for arch in load_archetypes():
        cand = score_archetype(arch, state, pt, SET17)
        assert 0.0 <= cand.p_reach <= 1.0
        assert 0.0 <= cand.expected_power <= 1.0
        assert 0.0 <= cand.trait_fit <= 1.0
        assert 0.0 <= cand.total_score <= 1.0


def test_sorted_descending():
    state = _state()
    pt = PoolTracker(SET17)
    top = top_k_comps(state, pt, load_archetypes(), SET17, k=12)
    scores = [c.total_score for c in top]
    assert scores == sorted(scores, reverse=True)


def test_trait_fit_uses_champion_traits():
    """Phase C: trait_fit reads champion.traits populated by Phase B.

    A board with 3 Dark Star units (Jhin, Kai'Sa, Mordekaiser) should produce
    a strictly higher trait_fit score for the dark_star archetype than an
    empty board, because the trait synergy signal now fires.
    """
    archs = {a.archetype_id: a for a in load_archetypes()}
    dark_star = archs["dark_star"]
    pt = PoolTracker(SET17)

    state_empty = _state(board=[])
    state_loaded = _state(board=[
        BoardUnit(champion="Jhin",       star=1),
        BoardUnit(champion="Kai'Sa",     star=1),
        BoardUnit(champion="Mordekaiser", star=1),
    ])

    score_empty  = score_archetype(dark_star, state_empty,  pt, SET17).trait_fit
    score_loaded = score_archetype(dark_star, state_loaded, pt, SET17).trait_fit

    assert score_loaded > score_empty, (
        f"Board with 3 Dark Star units should raise trait_fit above empty-board "
        f"baseline (empty={score_empty:.3f}, loaded={score_loaded:.3f})"
    )
