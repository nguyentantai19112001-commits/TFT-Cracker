"""Agent output schemas — Pydantic v2 models for all 8 agents.

These are the contracts the UI reads. Nothing else.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from engine.agents.base import AgentResult


# ── Agent 1 — SituationalFrame ────────────────────────────────────────────────

class SituationalFrameResult(AgentResult):
    agent_name: str = "situational_frame"
    game_tag: Literal["winning", "stable", "losing", "salvage", "dying"] = "stable"
    ev_avg_placement: float = 4.5
    ev_confidence: float = 0.5
    hp_tier: Literal["healthy", "warn", "danger", "critical"] = "healthy"
    econ_tier: Literal["ahead", "on_curve", "behind", "broken"] = "on_curve"
    frame_sentence: str = "On curve — standard play."
    frame_posture: Literal["greed", "stabilize", "salvage", "all_in"] = "stabilize"
    top_signal: str = ""


# ── Agent 2 — CompPicker ──────────────────────────────────────────────────────

class UnitRef(BaseModel):
    api_name: str
    display_name: str
    cost: int

class TraitBP(BaseModel):
    trait: str
    count: int
    breakpoint: int

class CompOption(BaseModel):
    archetype_id: str = ""
    display_name: str = ""
    tier: Literal["S", "A", "B", "C"] = "B"
    fit_score: float = 0.0
    missing_units: list[UnitRef] = Field(default_factory=list)
    core_units_held: list[UnitRef] = Field(default_factory=list)
    primary_carry: str = ""
    secondary_carry: str | None = None
    active_breakpoints: list[TraitBP] = Field(default_factory=list)
    bis_summary: dict[str, list[str]] = Field(default_factory=dict)
    why_this_fits: str = ""
    why_not_the_others: str = ""

class CompPickerResult(AgentResult):
    agent_name: str = "comp_picker"
    top_comp: CompOption = Field(default_factory=CompOption)
    alternates: list[CompOption] = Field(default_factory=list)
    stage_gate: str = ""


# ── Agent 3 — BISEngine ───────────────────────────────────────────────────────

class UnitBIS(BaseModel):
    api_name: str
    display_name: str
    cost: int
    current_star: int = 1
    items_currently_held: list[str] = Field(default_factory=list)
    bis_trio_ideal: list[str] = Field(default_factory=list)
    bis_trio_realistic: list[str] = Field(default_factory=list)
    delta_components: list[str] = Field(default_factory=list)
    delta_count: int = 0
    value_score: float = 0.0
    value_label: Literal["S", "A", "B", "C"] = "C"

class ItemSlam(BaseModel):
    item_id: str
    components: list[str]
    best_holder_api: str
    blocks_bis: bool = False
    urgency: Literal["now", "soon", "later"] = "later"

class BISEngineResult(AgentResult):
    agent_name: str = "bis_engine"
    priority_units: list[UnitBIS] = Field(default_factory=list)
    all_units: list[UnitBIS] = Field(default_factory=list)
    slammable_now: list[ItemSlam] = Field(default_factory=list)
    components_held: dict[str, int] = Field(default_factory=dict)
    wasted_components: list[str] = Field(default_factory=list)


# ── Agent 4 — TempoAgent ──────────────────────────────────────────────────────

class TempoAgentResult(AgentResult):
    agent_name: str = "tempo_agent"
    verdict_template: str = "hold"
    verdict_slots: dict[str, Any] = Field(default_factory=dict)
    verdict_display: str = "→ Hold"
    subline: str = ""
    action_priority: Literal["critical", "high", "medium", "low"] = "medium"


# ── Agent 5 — MicroEcon ───────────────────────────────────────────────────────

class EconSnapshot(BaseModel):
    gold: int
    level: int
    streak: int
    stage: tuple[int, int]
    interest: int
    econ_tier: str

class EconScenario(BaseModel):
    id: str
    action: str
    gold_before: int
    gold_after: int
    interest_delta: int
    opportunity_cost: float
    recommendation_score: float

class MicroEconResult(AgentResult):
    agent_name: str = "micro_econ"
    current: EconSnapshot | None = None
    scenarios: list[EconScenario] = Field(default_factory=list)
    best_scenario: str = ""
    one_liner: str = ""


# ── Agent 6 — ItemEconomy ─────────────────────────────────────────────────────

class ItemSlamRec(BaseModel):
    item_id: str
    components_used: list[str]
    holder_api: str
    holder_display: str
    is_bis: bool = False
    bis_alternative: str | None = None
    value_estimate: str = ""

class ItemEconomyResult(AgentResult):
    agent_name: str = "item_economy"
    decision: Literal["slam_now", "hold", "gamble"] = "hold"
    slam: ItemSlamRec | None = None
    hold_reason: str | None = None
    reasoning: str = ""
    risk_tag: Literal["safe", "moderate", "risky"] = "safe"


# ── Agent 7 — HolderMatrix ────────────────────────────────────────────────────

class HolderAssignment(BaseModel):
    unit_api: str
    unit_display: str
    preferred_family: Literal["AD", "AP", "AD_crit", "AP_mana", "tank", "utility"]
    preferred_items_given_components: list[str] = Field(default_factory=list)
    stage_role: Literal["skip", "hold_only", "secondary", "primary"] = "hold_only"
    current_holding_good: bool = True

class HolderMatrixResult(AgentResult):
    agent_name: str = "holder_matrix"
    assignments: list[HolderAssignment] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


# ── Agent 8 — AugmentQuality ──────────────────────────────────────────────────

class TierProbabilities(BaseModel):
    silver: float
    gold: float
    prismatic: float
    expected_value_tier: Literal["S", "G", "P"] = "G"

class AugmentRec(BaseModel):
    api_name: str
    display_name: str
    tier: Literal["silver", "gold", "prismatic"]
    fit_score: float
    why: str
    warning: str | None = None

class AugmentQualityResult(AgentResult):
    agent_name: str = "augment_quality"
    upcoming_stage: tuple[int, int] = (2, 1)
    tier_probabilities: TierProbabilities | None = None
    recommendations_per_tier: dict[str, list[AugmentRec]] = Field(default_factory=dict)
    top_overall_picks: list[AugmentRec] = Field(default_factory=list)
    probability_conditional_on_history: str = ""


# ── Orchestrator output ───────────────────────────────────────────────────────

class CoachResult(BaseModel):
    """Full 8-agent output. UI reads this."""
    frame: SituationalFrameResult = Field(default_factory=SituationalFrameResult)
    comp: CompPickerResult = Field(default_factory=CompPickerResult)
    bis: BISEngineResult = Field(default_factory=BISEngineResult)
    tempo: TempoAgentResult = Field(default_factory=TempoAgentResult)
    econ: MicroEconResult = Field(default_factory=MicroEconResult)
    item_econ: ItemEconomyResult = Field(default_factory=ItemEconomyResult)
    holders: HolderMatrixResult = Field(default_factory=HolderMatrixResult)
    augments: AugmentQualityResult = Field(default_factory=AugmentQualityResult)
