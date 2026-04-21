"""Orchestrator — phase 1 (rule-based agents only).

Runs 5 deterministic agents in parallel via asyncio.gather, returns
CoachResult. LLM agents (CompPicker, TempoAgent, ItemEconomy) are
stubbed as no-ops in this phase and will be wired in phase 2 (C10-C13).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import CoachResult
from engine.agents.situational_frame import SituationalFrameAgent, SituationalFrameInput
from engine.agents.bis_engine import BISEngineAgent, BISEngineInput, BoardUnit as BISBoardUnit
from engine.agents.micro_econ import MicroEconAgent, MicroEconInput
from engine.agents.holder_matrix import HolderMatrixAgent, HolderMatrixInput
from engine.agents.holder_matrix import BoardSlot as HolderBoardSlot
from engine.agents.augment_quality import AugmentQualityAgent, AugmentQualityInput

log = logging.getLogger(__name__)


# ── Shared agent context ──────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """Flat, pre-parsed game state consumed by all rule-based agents."""
    # Player state
    hp: int = 100
    gold: int = 0
    level: int = 4
    stage: tuple[int, int] = (2, 1)
    streak: int = 0
    interest_tier: int = 0
    board_strength: float = 0.5

    # Board / bench
    board_slots: list[dict] = field(default_factory=list)
    bench_components: list[str] = field(default_factory=list)
    item_recipes: dict[str, list[str]] = field(default_factory=dict)

    # Comp / augments
    augments_picked: list[str] = field(default_factory=list)
    augment_tiers: list[str] = field(default_factory=list)  # "S"/"G"/"P" per pick
    target_comp_apis: list[str] = field(default_factory=list)

    # BIS
    active_items: dict[str, list[str]] = field(default_factory=dict)


# ── Stub LLM agents ───────────────────────────────────────────────────────────

class _StubAgent(AgentBase):
    """No-op placeholder for LLM agents not yet implemented in phase 1."""
    def __init__(self, name: str, result_factory):
        self.name = name
        self._factory = result_factory

    async def _run_impl(self, ctx: Any) -> AgentResult:
        return self._factory()


# ── Orchestrator ──────────────────────────────────────────────────────────────

class CoachOrchestrator:
    """Runs 5 rule-based + 3 stub agents in parallel, returns CoachResult."""

    def __init__(self):
        self._frame_agent = SituationalFrameAgent()
        self._bis_agent = BISEngineAgent()
        self._econ_agent = MicroEconAgent()
        self._holder_agent = HolderMatrixAgent()
        self._augment_agent = AugmentQualityAgent()

        # LLM stubs (replaced in phase 2)
        from engine.agents.schemas import (
            CompPickerResult, TempoAgentResult, ItemEconomyResult
        )
        self._comp_agent = _StubAgent("comp_picker", CompPickerResult)
        self._tempo_agent = _StubAgent("tempo_agent", TempoAgentResult)
        self._item_econ_agent = _StubAgent("item_economy", ItemEconomyResult)

    async def run(self, ctx: AgentContext) -> CoachResult:
        """Run all agents; failures fall back rather than crashing."""
        frame_inp = _build_frame_input(ctx)
        bis_inp = _build_bis_input(ctx)
        econ_inp = _build_econ_input(ctx)
        holder_inp = _build_holder_input(ctx)
        aug_inp = _build_aug_input(ctx)

        results = await asyncio.gather(
            self._frame_agent.run(frame_inp),
            self._bis_agent.run(bis_inp),
            self._econ_agent.run(econ_inp),
            self._holder_agent.run(holder_inp),
            self._augment_agent.run(aug_inp),
            self._comp_agent.run(ctx),
            self._tempo_agent.run(ctx),
            self._item_econ_agent.run(ctx),
            return_exceptions=True,
        )

        from engine.agents.schemas import (
            SituationalFrameResult, BISEngineResult, MicroEconResult,
            HolderMatrixResult, AugmentQualityResult,
            CompPickerResult, TempoAgentResult, ItemEconomyResult,
        )

        def _safe(result, default_factory):
            if isinstance(result, Exception):
                log.warning("Agent failed: %s", result)
                return default_factory(used_fallback=True)
            return result

        frame, bis, econ, holders, augments, comp, tempo, item_econ = results

        return CoachResult(
            frame=_safe(frame, SituationalFrameResult),
            comp=_safe(comp, CompPickerResult),
            bis=_safe(bis, BISEngineResult),
            tempo=_safe(tempo, TempoAgentResult),
            econ=_safe(econ, MicroEconResult),
            item_econ=_safe(item_econ, ItemEconomyResult),
            holders=_safe(holders, HolderMatrixResult),
            augments=_safe(augments, AugmentQualityResult),
        )

    def run_sync(self, ctx: AgentContext) -> CoachResult:
        """Synchronous wrapper for use outside async contexts."""
        return asyncio.run(self.run(ctx))


# ── Input builders ────────────────────────────────────────────────────────────

def _build_frame_input(ctx: AgentContext) -> SituationalFrameInput:
    return SituationalFrameInput(
        hp=ctx.hp,
        gold=ctx.gold,
        level=ctx.level,
        stage=ctx.stage,
        streak=ctx.streak,
        interest_tier=ctx.interest_tier,
        augments_picked=ctx.augments_picked,
        board_strength=ctx.board_strength,
    )


def _build_bis_input(ctx: AgentContext) -> BISEngineInput:
    units: list[BISBoardUnit] = []
    for slot in ctx.board_slots:
        units.append(BISBoardUnit(
            api_name=slot.get("api_name", ""),
            display_name=slot.get("display_name", ""),
            cost=slot.get("cost", 1),
            star=slot.get("star", 1),
            items_held=slot.get("items_held", []),
            bis_trios=slot.get("bis_trios", []),
            value_class=slot.get("value_class", "B"),
            in_target_comp=slot.get("api_name", "") in ctx.target_comp_apis,
        ))
    return BISEngineInput(
        board=units,
        bench_components=ctx.bench_components,
        item_recipes=ctx.item_recipes,
    )


def _build_econ_input(ctx: AgentContext) -> MicroEconInput:
    target_levels = []
    if ctx.level < 8:
        target_levels.append(ctx.level + 1)
    if ctx.level < 9:
        target_levels.append(min(9, ctx.level + 2))

    roll_amounts = []
    if ctx.gold >= 20:
        roll_amounts.append(20)

    return MicroEconInput(
        gold=ctx.gold,
        level=ctx.level,
        streak=ctx.streak,
        stage=ctx.stage,
        target_levels=target_levels,
        roll_amounts=roll_amounts,
    )


def _build_holder_input(ctx: AgentContext) -> HolderMatrixInput:
    slots: list[HolderBoardSlot] = []
    for s in ctx.board_slots:
        slots.append(HolderBoardSlot(
            api_name=s.get("api_name", ""),
            display_name=s.get("display_name", ""),
            cost=s.get("cost", 1),
            star=s.get("star", 1),
            items_held=s.get("items_held", []),
        ))
    return HolderMatrixInput(
        board=slots,
        stage=ctx.stage,
        bench_components=ctx.bench_components,
        target_comp_apis=ctx.target_comp_apis,
        item_recipes=ctx.item_recipes,
    )


def _build_aug_input(ctx: AgentContext) -> AugmentQualityInput:
    upcoming = _next_armory(ctx.stage)
    return AugmentQualityInput(
        upcoming_stage=upcoming,
        prior_tiers=ctx.augment_tiers,
    )


def _next_armory(stage: tuple[int, int]) -> tuple[int, int]:
    """Return the next augment armory stage after the given stage."""
    armories = [(2, 1), (3, 2), (4, 2)]
    for armory in armories:
        if stage < armory:
            return armory
    return (4, 2)  # past all armories
