"""Agent 3 — BISEngine (rule-based, <50ms).

For each carry on board, computes the ideal BIS trio, the realistic trio
given held components, delta components still needed, and a value-priority
ranking across all carries.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import BISEngineResult, ItemSlam, UnitBIS
from engine.knowledge.loader import constants


@dataclass
class BoardUnit:
    api_name: str
    display_name: str
    cost: int
    star: int = 1
    items_held: list[str] = field(default_factory=list)   # completed item IDs
    bis_trios: list[list[str]] = field(default_factory=list)  # ordered preference lists
    value_class: str = "B"      # S / A / B / C / utility
    in_target_comp: bool = False


@dataclass
class BISEngineInput:
    board: list[BoardUnit]
    bench_components: list[str]                 # e.g. ["BF", "BF", "Rod", "Cloak"]
    item_recipes: dict[str, list[str]]          # item_id → [comp1, comp2]


class BISEngineAgent(AgentBase):
    name = "bis_engine"
    timeout_ms = 500

    async def _run_impl(self, ctx: Any) -> BISEngineResult:
        inp: BISEngineInput = ctx
        return _compute(inp)

    def _fallback(self, ctx: Any) -> AgentResult:
        return BISEngineResult(used_fallback=True)


# ── Pure deterministic computation ────────────────────────────────────────────

def _compute(inp: BISEngineInput) -> BISEngineResult:
    k = constants()
    class_weights: dict[str, float] = k["value_class_weights"]
    cost_weights: dict[int, float] = {int(c): float(v) for c, v in k["cost_weights"].items()}

    bench = Counter(inp.bench_components)
    components_held: dict[str, int] = dict(bench)

    unit_results: list[UnitBIS] = []
    for unit in inp.board:
        u = _score_unit(unit, bench, inp.item_recipes, class_weights, cost_weights)
        unit_results.append(u)

    unit_results.sort(key=lambda u: u.value_score, reverse=True)
    priority_units = unit_results[:2]

    slammable = _find_slammable(inp, unit_results)
    wasted = _find_wasted(bench, unit_results, inp.item_recipes)

    return BISEngineResult(
        priority_units=priority_units,
        all_units=unit_results,
        slammable_now=slammable,
        components_held=components_held,
        wasted_components=wasted,
    )


def _score_unit(
    unit: BoardUnit,
    bench: Counter,
    recipes: dict[str, list[str]],
    class_weights: dict[str, float],
    cost_weights: dict[int, float],
) -> UnitBIS:
    # Already-on-unit components (reconstructed from held items)
    on_unit: Counter = Counter()
    for item_id in unit.items_held:
        for comp in recipes.get(item_id, []):
            on_unit[comp] += 1

    available = bench + on_unit

    # Pick the best trio: fewest remaining components needed
    best_trio: list[str] = []
    best_delta: list[str] = []
    best_delta_count = 999

    ideal_trio: list[str] = unit.bis_trios[0] if unit.bis_trios else []

    for trio in unit.bis_trios:
        needed = _components_for_trio(trio, recipes)
        delta = needed - available
        delta_count = sum(delta.values())
        if delta_count < best_delta_count:
            best_delta_count = delta_count
            best_trio = trio
            best_delta = list(delta.elements())

    if not best_trio:
        best_trio = ideal_trio

    # Value score
    cw = class_weights.get(unit.value_class, 0.45)
    tw = cost_weights.get(unit.cost, 0.65)
    star_mult = 1.0 + 0.5 * (unit.star - 1)
    comp_bonus = 1.2 if unit.in_target_comp else 1.0
    # Keep raw_score uncapped for ranking; value_label uses capped form
    raw_score = cw * tw * star_mult * comp_bonus
    value_score = round(raw_score, 4)

    capped = min(1.0, raw_score)
    if capped >= 0.85:
        value_label = "S"
    elif capped >= 0.65:
        value_label = "A"
    elif capped >= 0.45:
        value_label = "B"
    else:
        value_label = "C"

    return UnitBIS(
        api_name=unit.api_name,
        display_name=unit.display_name,
        cost=unit.cost,
        current_star=unit.star,
        items_currently_held=unit.items_held,
        bis_trio_ideal=ideal_trio,
        bis_trio_realistic=best_trio,
        delta_components=best_delta,
        delta_count=best_delta_count if best_delta_count < 999 else 0,
        value_score=value_score,
        value_label=value_label,
    )


def _components_for_trio(trio: list[str], recipes: dict[str, list[str]]) -> Counter:
    """All components needed to craft all 3 items in the trio."""
    needed: Counter = Counter()
    for item_id in trio:
        for comp in recipes.get(item_id, []):
            needed[comp] += 1
    return needed


def _find_slammable(inp: BISEngineInput, units: list[UnitBIS]) -> list[ItemSlam]:
    """Items buildable from current bench components, ordered by urgency."""
    bench = Counter(inp.bench_components)
    slams: list[ItemSlam] = []

    for item_id, comps in inp.item_recipes.items():
        if len(comps) != 2:
            continue
        if bench.get(comps[0], 0) >= 1 and bench.get(comps[1], 0) >= (1 if comps[0] != comps[1] else 2):
            # Find best holder
            holder_api = _best_holder(item_id, units)
            if holder_api is None:
                continue
            blocks = _blocks_bis(item_id, comps, inp, units)
            urgency = "now" if not blocks else "soon"
            slams.append(ItemSlam(
                item_id=item_id,
                components=comps,
                best_holder_api=holder_api,
                blocks_bis=blocks,
                urgency=urgency,
            ))

    slams.sort(key=lambda s: (0 if s.urgency == "now" else 1, s.blocks_bis))
    return slams


def _best_holder(item_id: str, units: list[UnitBIS]) -> str | None:
    """Return the api_name of the unit that most wants this item."""
    for unit in units:  # already sorted by value_score desc
        if item_id in unit.bis_trio_realistic or item_id in unit.bis_trio_ideal:
            return unit.api_name
    return units[0].api_name if units else None


def _blocks_bis(
    item_id: str,
    comps: list[str],
    inp: BISEngineInput,
    units: list[UnitBIS],
) -> bool:
    """True if building this item would leave the priority unit short ≥2 components."""
    if not units:
        return False
    top = units[0]
    if item_id in top.bis_trio_realistic:
        return False
    bench = Counter(inp.bench_components)
    needed = _components_for_trio(top.bis_trio_realistic, inp.item_recipes)
    # subtract the components we'd consume
    used = Counter(comps)
    bench_after = bench - used
    delta = max(0, sum((needed - bench_after).values()))
    return delta >= 2


def _find_wasted(
    bench: Counter,
    units: list[UnitBIS],
    recipes: dict[str, list[str]],
) -> list[str]:
    """Components on bench that don't contribute to any priority unit's realistic trio."""
    if not units:
        return []
    useful: set[str] = set()
    for u in units[:2]:  # only check priority units
        useful.update(_components_for_trio(u.bis_trio_realistic, recipes).keys())
    wasted: list[str] = []
    for comp, count in bench.items():
        if comp not in useful:
            wasted.extend([comp] * count)
    return wasted
