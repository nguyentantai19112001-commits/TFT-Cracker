"""comp_planner.py — Rank reachable Set 17 archetypes by current game state.

Public API:
    load_archetypes(dir_=None) -> list[Archetype]
    top_k_comps(state, pool, archetypes, set_, k=3) -> list[CompCandidate]
    score_archetype(archetype, state, pool, set_) -> CompCandidate
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import yaml
from schemas import Archetype, CompCandidate, GameState, SetKnowledge
from pool import PoolTracker
import econ as econ_mod

_ARCHETYPES_DIR = _ROOT / "knowledge" / "archetypes"

TIER_BASE = {"S": 0.9, "A": 0.75, "B": 0.6, "C": 0.45}


@lru_cache(maxsize=1)
def _load_archetypes_cached(dir_: Path) -> list[Archetype]:
    archetypes = []
    for path in sorted(dir_.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        # Coerce required_traits from [[str, int], ...] to [(str, int), ...]
        rt = raw.get("required_traits", [])
        raw["required_traits"] = [tuple(pair) for pair in rt]
        archetypes.append(Archetype(**raw))
    return archetypes


def load_archetypes(dir_: Path | None = None) -> list[Archetype]:
    return _load_archetypes_cached(dir_ or _ARCHETYPES_DIR)


def _we_have_it(champion: str, state: GameState) -> bool:
    board_names = {u.champion for u in state.board}
    bench_names = {u.champion for u in state.bench}
    return champion in board_names | bench_names


def _we_have_it_starred(champion: str, state: GameState) -> bool:
    for u in state.board + state.bench:
        if u.champion == champion and u.star >= 2:
            return True
    return False


def _compute_p_reach(
    archetype: Archetype,
    state: GameState,
    pool: PoolTracker,
    set_: SetKnowledge,
) -> float:
    need = [u for u in archetype.core_units if not _we_have_it_starred(u, state)]
    if not need:
        return 1.0

    # Already have a unit (1-star) — much easier to 2-star than to find from scratch.
    # Budget ~40g at target level, split naively across missing units.
    gold_per_unit = max(4, 40 // len(need))
    p_all = 1.0
    for champ in need:
        try:
            pool_state = pool.to_pool_state(champ)
            analysis = econ_mod.analyze_roll(
                target=champ,
                level=archetype.target_level,
                gold=gold_per_unit,
                pool=pool_state,
                set_=set_,
            )
            p_all *= analysis.p_hit_at_least_1
        except Exception:
            p_all *= 0.5  # fallback if champion not in pool data
    return p_all


def _compute_expected_power(archetype: Archetype, state: GameState) -> float:
    base = TIER_BASE[archetype.tier]
    have = sum(1 for u in archetype.core_units if _we_have_it(u, state))
    progress = have / len(archetype.core_units)
    return base * (0.5 + 0.5 * progress)


def _compute_trait_fit(
    archetype: Archetype, state: GameState, set_: SetKnowledge
) -> float:
    score = 0.0

    # Augment overlap with required traits
    for aug in state.augments:
        for trait, _ in archetype.required_traits:
            if trait.lower() in aug.lower():
                score += 0.3
                break

    # Item overlap with archetype's ideal items
    all_ideal = {item for items in archetype.ideal_items.values() for item in items}
    for item in state.completed_items_on_bench:
        if item in all_ideal:
            score += 0.2

    # Board alignment — fraction of board units belonging to this archetype
    archetype_units = set(archetype.core_units) | set(archetype.optional_units)
    if state.board:
        board_match = sum(1 for u in state.board if u.champion in archetype_units)
        score += 0.5 * (board_match / len(state.board))

    # Trait synergy — count required_traits present on the player's current board.
    # Reads champion.traits populated by Phase B; weight 0.4.
    if archetype.required_traits and state.board:
        champ_traits: dict[str, list[str]] = {
            c["name"]: c.get("traits", []) for c in set_.champions
        }
        active_traits: set[str] = set()
        for unit in state.board:
            for trait in champ_traits.get(unit.champion, []):
                active_traits.add(trait)
        required_trait_names = {t for t, _ in archetype.required_traits}
        matches = len(active_traits & required_trait_names)
        score += 0.4 * (matches / len(required_trait_names))

    return min(1.0, score)


def _next_buys(archetype: Archetype, state: GameState) -> list[str]:
    missing_core = [u for u in archetype.core_units if not _we_have_it(u, state)]
    upgrade_core = [
        u.champion
        for u in state.board + state.bench
        if u.champion in archetype.core_units and u.star == 1
    ]
    seen: set[str] = set()
    result: list[str] = []
    for champ in missing_core + upgrade_core:
        if champ not in seen:
            seen.add(champ)
            result.append(champ)
    return result[:3]


def score_archetype(
    archetype: Archetype,
    state: GameState,
    pool: PoolTracker,
    set_: SetKnowledge,
) -> CompCandidate:
    p_reach = _compute_p_reach(archetype, state, pool, set_)
    expected_power = _compute_expected_power(archetype, state)
    trait_fit = _compute_trait_fit(archetype, state, set_)
    total_score = 0.5 * p_reach + 0.3 * expected_power + 0.2 * trait_fit
    missing = [u for u in archetype.core_units if not _we_have_it(u, state)]
    return CompCandidate(
        archetype=archetype,
        p_reach=p_reach,
        expected_power=expected_power,
        trait_fit=trait_fit,
        total_score=total_score,
        missing_units=missing,
        recommended_next_buys=_next_buys(archetype, state),
    )


def top_k_comps(
    state: GameState,
    pool: PoolTracker,
    archetypes: list[Archetype],
    set_: SetKnowledge,
    k: int = 3,
) -> list[CompCandidate]:
    candidates = [score_archetype(a, state, pool, set_) for a in archetypes]
    candidates.sort(key=lambda c: c.total_score, reverse=True)
    return candidates[:k]
