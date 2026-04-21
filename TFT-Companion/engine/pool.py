"""pool.py — Pool tracker for Augie v2 (Phase 2).

Maintains point estimates of copies remaining based on own holdings only.
Opponent scouting is v2.5 scope — not in v2. No Bayesian inference; point
estimates only. Call reset() on new game.
"""
from __future__ import annotations

import sys
from pathlib import Path

# game_assets lives one directory up (TFT-Companion/), not inside augie-v2/.
_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

import game_assets

from schemas import BoardUnit, PoolBelief, PoolState, SetKnowledge, ShopSlot

_STAR_COPIES = {1: 1, 2: 3, 3: 9}


class PoolTracker:
    """Per-game tracker. Instantiate once at game start, observe throughout."""

    def __init__(self, set_: SetKnowledge) -> None:
        self._set = set_
        self._cost_by_champ: dict[str, int] = {
            name: info["cost"] for name, info in game_assets.CHAMPIONS.items()
        }
        self._copies_per_champ: dict[str, int] = {
            name: set_.pool_sizes[cost].copies_per_champ
            for name, cost in self._cost_by_champ.items()
            if cost in set_.pool_sizes
        }
        self._r_t_total: dict[str, int] = {
            name: set_.pool_sizes[cost].total
            for name, cost in self._cost_by_champ.items()
            if cost in set_.pool_sizes
        }
        self._k_estimate: dict[str, int] = dict(self._copies_per_champ)
        self._own_count: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Observation API
    # ------------------------------------------------------------------

    def observe_own_board(self, board: list[BoardUnit], bench: list[BoardUnit]) -> None:
        """Register our own holdings. Call every F9 to stay in sync."""
        current: dict[str, int] = {}
        for unit in list(board) + list(bench):
            current[unit.champion] = current.get(unit.champion, 0) + _STAR_COPIES.get(unit.star, 1)

        prior = self._own_count
        all_champs = set(current) | set(prior)
        for champ in all_champs:
            delta = current.get(champ, 0) - prior.get(champ, 0)
            if delta != 0 and champ in self._k_estimate:
                self._k_estimate[champ] = max(
                    0,
                    min(self._copies_per_champ[champ], self._k_estimate[champ] - delta),
                )
        self._own_count = current

    def observe_shop(self, shop: list[ShopSlot]) -> None:
        """No-op in v2. Hook for future Bayesian extension."""

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def belief_for(self, champion: str) -> PoolBelief:
        if champion not in self._k_estimate:
            raise KeyError(f"Unknown champion: {champion!r}")
        k = self._k_estimate[champion]
        # Flat uncertainty of ±2 — no opponent data in v2, so we can't shrink this.
        uncertainty = 2
        cap = self._copies_per_champ[champion]
        cost = self._cost_by_champ[champion]
        r_t_est = sum(
            self._k_estimate[c]
            for c, co in self._cost_by_champ.items()
            if co == cost and c in self._k_estimate
        )
        return PoolBelief(
            champion=champion,
            k_estimate=k,
            k_lower_90=max(0, k - uncertainty),
            k_upper_90=min(cap, k + uncertainty),
            r_t_estimate=r_t_est,
            r_t_total=self._r_t_total.get(champion, 0),
            last_updated_round=None,
        )

    def to_pool_state(self, champion: str) -> PoolState:
        """Convert belief into PoolState for econ.analyze_roll."""
        b = self.belief_for(champion)
        cost = self._cost_by_champ[champion]
        distinct = self._set.pool_sizes[cost].distinct
        return PoolState(
            copies_of_target_remaining=b.k_estimate,
            same_cost_copies_remaining=b.r_t_estimate,
            distinct_same_cost=distinct,
        )

    def reset(self) -> None:
        """Clear all beliefs — call when a new game starts."""
        self._k_estimate = dict(self._copies_per_champ)
        self._own_count = {}
