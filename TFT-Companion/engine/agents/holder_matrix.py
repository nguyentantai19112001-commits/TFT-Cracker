"""Agent 7 — HolderMatrix (rule-based, <20ms).

Pure lookup against item_holders.yaml. For each board unit at the current
stage, returns: preferred item family, stage role, and whether current items
are appropriate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from engine.agents.base import AgentBase, AgentResult
from engine.agents.schemas import HolderAssignment, HolderMatrixResult

_HOLDERS_PATH = Path(__file__).parent.parent / "knowledge" / "item_holders.yaml"
_HOLDERS_CACHE: dict | None = None


@dataclass
class BoardSlot:
    api_name: str
    display_name: str
    cost: int = 1
    star: int = 1
    items_held: list[str] = field(default_factory=list)  # completed item IDs


@dataclass
class HolderMatrixInput:
    board: list[BoardSlot]
    stage: tuple[int, int]
    bench_components: list[str] = field(default_factory=list)
    target_comp_apis: list[str] = field(default_factory=list)  # preferred comp unit list
    item_recipes: dict[str, list[str]] = field(default_factory=dict)


# ── Family → item preference tables (fallback when YAML has no full BIS) ─────
_FAMILY_ITEMS: dict[str, list[str]] = {
    "AD_crit":  ["InfinityEdge", "LastWhisper", "GiantSlayer", "DeathbladeSword"],
    "AD":       ["HextechGunblade", "Deathblade", "StatikkShiv", "GuinsoosRageblade"],
    "AP":       ["JeweledGauntlet", "ArchangelsStaff", "HextechGunblade", "BlueBuff"],
    "AP_mana":  ["BlueBuff", "ArchangelsStaff", "Morellonomicon", "Rabadon"],
    "AS":       ["GuinsoosRageblade", "StatikkShiv"],
    "tank":     ["Warmogs", "Bramble", "Sunfire", "Gargoyle"],
    "utility":  ["Redemption", "Locket", "ZzRotPortal"],
}


class HolderMatrixAgent(AgentBase):
    name = "holder_matrix"
    timeout_ms = 300

    async def _run_impl(self, ctx: Any) -> HolderMatrixResult:
        inp: HolderMatrixInput = ctx
        return _compute(inp)

    def _fallback(self, ctx: Any) -> AgentResult:
        return HolderMatrixResult(used_fallback=True)


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_holders(path: Path | None = None) -> dict:
    global _HOLDERS_CACHE
    if _HOLDERS_CACHE is not None and path is None:
        return _HOLDERS_CACHE
    target = path or _HOLDERS_PATH
    with target.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if path is None:
        _HOLDERS_CACHE = data
    return data


def reset_holders_cache() -> None:
    global _HOLDERS_CACHE
    _HOLDERS_CACHE = None


# ── Pure computation ──────────────────────────────────────────────────────────

def _compute(inp: HolderMatrixInput) -> HolderMatrixResult:
    holders = _load_holders()
    stage_key = _stage_key(inp.stage)

    assignments: list[HolderAssignment] = []
    primary_families: dict[str, str] = {}  # api → family (for conflict detection)

    for slot in inp.board:
        entry = holders.get(slot.api_name)
        if entry is None:
            # Unknown unit — default to unknown family, hold_only
            asm = HolderAssignment(
                unit_api=slot.api_name,
                unit_display=slot.display_name,
                preferred_family="utility",
                preferred_items_given_components=[],
                stage_role="hold_only",
                current_holding_good=True,
            )
        else:
            family = entry.get("primary_family", "utility")
            stage_role = _resolve_stage_role(entry, stage_key)
            preferred = _preferred_items(family, inp.bench_components, inp.item_recipes)
            good = _current_items_ok(slot.items_held, family, entry.get("avoid", []))

            asm = HolderAssignment(
                unit_api=slot.api_name,
                unit_display=slot.display_name,
                preferred_family=family,
                preferred_items_given_components=preferred[:3],
                stage_role=stage_role,
                current_holding_good=good,
            )
            primary_families[slot.api_name] = family

        assignments.append(asm)

    conflicts = _detect_conflicts(inp.board, assignments, primary_families)

    return HolderMatrixResult(assignments=assignments, conflicts=conflicts)


def _stage_key(stage: tuple[int, int]) -> str:
    """Map game stage to item_holders.yaml stage field key."""
    s, _ = stage
    if s <= 2:
        return "stage_2"
    if s == 3:
        return "stage_3"
    if s == 4:
        return "stage_4"
    return "stage_5_plus"


def _resolve_stage_role(entry: dict, stage_key: str) -> str:
    """Read stage_role from holder entry; fall back to hold_only."""
    role = entry.get(stage_key)
    if role in ("skip", "hold_only", "secondary", "primary"):
        return role
    return "hold_only"


def _preferred_items(
    family: str,
    bench_components: list[str],
    recipes: dict[str, list[str]],
) -> list[str]:
    """Return items from the family's preference list that are buildable or high priority."""
    candidates = _FAMILY_ITEMS.get(family, [])
    if not bench_components or not recipes:
        return candidates[:3]

    from collections import Counter
    bench = Counter(bench_components)

    buildable: list[str] = []
    others: list[str] = []
    for item in candidates:
        comps = recipes.get(item, [])
        if len(comps) == 2:
            needed_0 = bench.get(comps[0], 0) >= 1
            needed_1 = bench.get(comps[1], 0) >= (1 if comps[0] != comps[1] else 2)
            if needed_0 and needed_1:
                buildable.append(item)
                continue
        others.append(item)

    return (buildable + others)[:3]


def _current_items_ok(items_held: list[str], family: str, avoid: list[str]) -> bool:
    """True if no current item violates the avoid list for this unit.

    Avoid list entries should be full item IDs (e.g. "InfinityEdge").
    Also matches avoid tags that appear as exact prefix or suffix to handle
    shortcode aliases.
    """
    avoid_set = {a.lower() for a in avoid}
    for item in items_held:
        item_lower = item.lower()
        # Exact match
        if item_lower in avoid_set:
            return False
        # Avoid tag is contained at start of item name (shortcode prefix)
        for tag in avoid_set:
            if item_lower.startswith(tag):
                return False
    return True


def _detect_conflicts(
    board: list[BoardSlot],
    assignments: list[HolderAssignment],
    primary_families: dict[str, str],
) -> list[str]:
    """Find units competing for the same primary item family."""
    from collections import Counter
    family_count: Counter = Counter(primary_families.values())

    conflicts: list[str] = []
    for family, count in family_count.items():
        if count >= 2 and family in ("AD_crit", "AP"):
            # Multiple primary carries competing — report conflict
            units = [api for api, f in primary_families.items() if f == family]
            conflicts.append(f"{family} contested by: {', '.join(units)}")

    return conflicts
