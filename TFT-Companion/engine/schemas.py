"""schemas.py — The frozen contract for Augie v2.

Every module in the new pipeline imports its types from this file. Do NOT add, remove,
or change fields without explicit user approval (see CLAUDE.md hard rule #3).

This file is intentionally small. If you think a field is missing, ask first.

Types are Pydantic v2. Existing Augie dataclass code in `state_builder.py` migrates to
these during Phase 0.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# State primitives
# ==============================================================================

class BoardUnit(BaseModel):
    """A champion on the board, bench, or in a shop slot."""
    model_config = ConfigDict(frozen=True)

    champion: str                  # full display name, e.g. "Jinx"
    star: Literal[1, 2, 3] = 1
    items: list[str] = Field(default_factory=list)
    # hex position is optional — Match-V1 doesn't give it, scouting does for own board
    position: Optional[tuple[int, int]] = None  # (row 0-3, col 0-6)


class ShopSlot(BaseModel):
    """One of the 5 shop slots."""
    model_config = ConfigDict(frozen=True)

    champion: str
    cost: int                      # 1..5
    locked: bool = False


class TraitActivation(BaseModel):
    """A trait that's currently active on the board."""
    model_config = ConfigDict(frozen=True)

    trait: str                     # e.g. "Anima Squad"
    count: int                     # units contributing
    tier: Literal["inactive", "bronze", "silver", "gold", "prismatic", "chromatic"]


# ==============================================================================
# GameState — the canonical runtime state
# ==============================================================================

class GameStateSummary(BaseModel):
    """Compact snapshot stored in temporal history. Don't bloat every call."""
    stage: str
    gold: int
    hp: int
    level: int
    streak: int
    board_hash: str                # sha1 of sorted board unit list


class GameState(BaseModel):
    """The canonical live state. Built by state_builder.py every F9 press."""
    # --- Core scalar state ---
    stage: str                     # "3-2"
    round: Optional[str] = None    # "3-2 PvP" | "3-2 Krug" | etc.
    gold: int
    hp: int
    level: int
    xp_current: int = 0
    xp_needed: int = 0
    streak: int = 0                # positive = win streak, negative = loss streak
    set_id: str                    # "17"

    # --- Board state ---
    board: list[BoardUnit] = Field(default_factory=list)
    bench: list[BoardUnit] = Field(default_factory=list)
    shop: list[ShopSlot] = Field(default_factory=list)

    active_traits: list[TraitActivation] = Field(default_factory=list)
    augments: list[str] = Field(default_factory=list)
    item_components_on_bench: list[str] = Field(default_factory=list)
    completed_items_on_bench: list[str] = Field(default_factory=list)

    # --- Temporal ---
    previous_states: list[GameStateSummary] = Field(default_factory=list)

    # --- Provenance ---
    capture_id: Optional[int] = None
    game_id: Optional[int] = None
    source_confidence: dict[str, float] = Field(default_factory=dict)  # per-field 0-1


# ==============================================================================
# Pool / contested tracking
# ==============================================================================

class PoolState(BaseModel):
    """Input to econ calculations — contested-pool snapshot for one target."""
    model_config = ConfigDict(frozen=True)

    copies_of_target_remaining: int     # k in the math
    same_cost_copies_remaining: int     # R_T in the math
    distinct_same_cost: int             # d


class PoolBelief(BaseModel):
    """Output from pool.py for a single champion."""
    champion: str
    k_estimate: int
    k_lower_90: int
    k_upper_90: int
    r_t_estimate: int
    r_t_total: int                      # never decreases — set-fixed
    last_updated_round: Optional[str] = None


# ==============================================================================
# Econ outputs
# ==============================================================================

class RollAnalysis(BaseModel):
    """Output of econ.analyze_roll()."""
    target_champion: str
    level: int
    gold_spent: int
    p_hit_at_least_1: float             # 0..1
    p_hit_at_least_2: float
    p_hit_at_least_3: float
    expected_copies_seen: float
    variance_copies: float
    expected_gold_to_first_hit: float   # inf if k == 0
    method: Literal["markov", "hypergeo", "iid"]


class LevelDecision(BaseModel):
    """Output of econ.level_vs_roll()."""
    current_level: int
    current_xp: int
    xp_needed_next: int
    gold_to_level: int
    gold_lost_interest: float
    p_hit_delta: float                  # P(hit target) at L+1 minus at L
    recommended: Literal["LEVEL", "HOLD", "ROLL"]
    reasoning: str


# ==============================================================================
# Rules layer
# ==============================================================================

class Fire(BaseModel):
    """A rule fire. Matches existing Augie contract."""
    rule_id: str
    severity: float                     # 0..1, 1.0 = critical
    action: str                         # "ROLL_TO", "HOLD_ECON", "LEVEL_UP", etc.
    message: str                        # short, for overlay
    data: dict = Field(default_factory=dict)   # structured context


# ==============================================================================
# Comp planner
# ==============================================================================

class Archetype(BaseModel):
    """A reachable endgame comp, loaded from knowledge/archetypes/*.yaml."""
    archetype_id: str                   # "anima_squad", "exotech_jinx", ...
    display_name: str
    target_level: int                   # typical capped level
    core_units: list[str]               # must-have endgame units
    optional_units: list[str] = Field(default_factory=list)
    required_traits: list[tuple[str, int]] = Field(default_factory=list)  # (trait, count)
    ideal_items: dict[str, list[str]] = Field(default_factory=dict)  # champion -> items
    tier: Literal["S", "A", "B", "C"] = "B"
    playstyle: Literal["fast8", "reroll", "standard"] = "standard"


class CompCandidate(BaseModel):
    """Output of comp_planner.top_k_comps() — ranked reachable comp."""
    archetype: Archetype
    p_reach: float                      # 0..1, probability we can assemble it
    expected_power: float               # relative score, 0..1
    trait_fit: float                    # overlap with current augments/items
    total_score: float                  # weighted combination
    missing_units: list[str]
    recommended_next_buys: list[str]


# ==============================================================================
# Recommender
# ==============================================================================

class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    ROLL_TO = "ROLL_TO"
    LEVEL_UP = "LEVEL_UP"
    HOLD_ECON = "HOLD_ECON"
    SLAM_ITEM = "SLAM_ITEM"
    PIVOT_COMP = "PIVOT_COMP"


class ActionScores(BaseModel):
    """The 5 scoring dimensions. Each in [-3, +3]."""
    tempo: float
    econ: float
    hp_risk: float
    board_strength: float
    pivot_value: float

    @property
    def total(self) -> float:
        """Unweighted sum. Weighted version uses knowledge/core.yaml weights."""
        return self.tempo + self.econ + self.hp_risk + self.board_strength + self.pivot_value


class ActionCandidate(BaseModel):
    """A scored action the user could take right now."""
    action_type: ActionType
    params: dict = Field(default_factory=dict)  # e.g. {"champion": "Jinx"} or {"gold_floor": 20}
    scores: ActionScores
    total_score: float                  # weighted sum using knowledge weights
    human_summary: str                  # "Roll to 20g for Jinx 2-star"
    reasoning_tags: list[str] = Field(default_factory=list)


# ==============================================================================
# Advisor final output
# ==============================================================================

class AdvisorVerdict(BaseModel):
    """What advisor.py emits to the overlay."""
    one_liner: str                      # <=120 chars imperative
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    tempo_read: Literal["AHEAD", "ON_PACE", "BEHIND", "CRITICAL"]
    primary_action: ActionType
    chosen_candidate: ActionCandidate   # which of the top-K recommender picked
    reasoning: str                      # 2-4 sentences
    considerations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data_quality_note: Optional[str] = None


# ==============================================================================
# Knowledge pack types (loaded from YAML)
# ==============================================================================

class PoolInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    copies_per_champ: int
    distinct: int

    @property
    def total(self) -> int:
        return self.copies_per_champ * self.distinct


class XPThreshold(BaseModel):
    model_config = ConfigDict(frozen=True)
    from_level: int
    to_level: int
    xp: int


class StreakBracket(BaseModel):
    model_config = ConfigDict(frozen=True)
    low: int                            # inclusive
    high: int                           # inclusive
    bonus: int                          # gold


class SpikeInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    stage: str
    archetype: str                      # which archetype spikes here


class ScoringWeights(BaseModel):
    """Weights for the 5 scoring dimensions. Used by recommender.py."""
    model_config = ConfigDict(frozen=True)
    tempo: float = 1.0
    econ: float = 1.0
    hp_risk: float = 1.5                # HP matters more than tempo at low HP
    board_strength: float = 1.2
    pivot_value: float = 0.8


class CoreKnowledge(BaseModel):
    """Loaded from knowledge/core.yaml. Set-invariant."""
    xp_cost_per_buy: int = 4
    xp_per_buy: int = 4
    passive_xp_per_round: int = 2
    interest_cap: int = 5
    interest_per_10_gold: int = 1
    streak_brackets: list[StreakBracket]
    xp_thresholds: list[XPThreshold]
    scoring_weights: ScoringWeights


class SetKnowledge(BaseModel):
    """Loaded from knowledge/set_N.yaml. Per-set."""
    set_id: str
    name: str
    patch: str
    released: str                       # iso date
    shop_odds: dict[int, list[float]]   # level -> [p1, p2, p3, p4, p5] summing to 100
    pool_sizes: dict[int, PoolInfo]     # cost -> PoolInfo
    gated_units: list[dict] = Field(default_factory=list)  # 5-cost unlockables
    spike_rounds: list[SpikeInfo] = Field(default_factory=list)
    mechanic_hooks: dict = Field(default_factory=dict)  # e.g. realm_of_the_gods block
    champions: list[dict] = Field(default_factory=list)  # cost/name catalog from YAML
    traits: list[dict] = Field(default_factory=list)     # trait names + breakpoints
