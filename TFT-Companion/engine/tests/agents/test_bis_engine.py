"""Tests for Agent 3 — BISEngine (component-delta, value ranking, slam detection)."""
from __future__ import annotations

import asyncio
import pytest

from engine.agents.bis_engine import (
    BISEngineAgent,
    BISEngineInput,
    BoardUnit,
    _compute,
    _components_for_trio,
)
from engine.agents.schemas import BISEngineResult
from engine.knowledge.loader import reset_cache


# ── Test item recipes (small, known-correct subset) ───────────────────────────
# comp IDs: BF, RB, Rod, Tear, Glove, Vest, Belt, Cloak
RECIPES: dict[str, list[str]] = {
    "GuinsoosRageblade":  ["RB", "Rod"],
    "JeweledGauntlet":    ["Glove", "Rod"],
    "HextechGunblade":    ["BF", "Rod"],
    "ArchangelsStaff":    ["Tear", "Rod"],
    "BlueBuff":           ["Tear", "Tear"],
    "InfinityEdge":       ["BF", "Glove"],
    "Rabadon":            ["Rod", "Rod"],
    "Warmogs":            ["Belt", "Belt"],
    "Bramble":            ["Vest", "Vest"],
    "StatikkShiv":        ["Tear", "RB"],
}

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


def _carry(
    api="TFT17_Vex",
    display="Vex",
    cost=3,
    star=2,
    items=None,
    trios=None,
    value_class="S",
    in_comp=True,
) -> BoardUnit:
    return BoardUnit(
        api_name=api,
        display_name=display,
        cost=cost,
        star=star,
        items_held=items or [],
        bis_trios=trios or [["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]],
        value_class=value_class,
        in_target_comp=in_comp,
    )


def inp(units: list[BoardUnit], bench: list[str]) -> BISEngineInput:
    return BISEngineInput(board=units, bench_components=bench, item_recipes=RECIPES)


def run(i: BISEngineInput) -> BISEngineResult:
    return asyncio.run(BISEngineAgent().run(ctx=i))


# ── _components_for_trio ──────────────────────────────────────────────────────

def test_trio_components_no_items():
    needed = _components_for_trio([], RECIPES)
    assert dict(needed) == {}


def test_trio_components_single_item():
    needed = _components_for_trio(["GuinsoosRageblade"], RECIPES)
    assert needed["RB"] == 1 and needed["Rod"] == 1


def test_trio_components_full_trio():
    trio = ["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]
    needed = _components_for_trio(trio, RECIPES)
    # RB+Rod, Glove+Rod, Tear+Rod → Rod×3, RB, Glove, Tear
    assert needed["Rod"] == 3
    assert needed["RB"] == 1
    assert needed["Glove"] == 1
    assert needed["Tear"] == 1


def test_trio_unknown_item_skipped():
    needed = _components_for_trio(["NonExistentItem"], RECIPES)
    assert dict(needed) == {}


# ── Exact BIS available ───────────────────────────────────────────────────────

def test_exact_bis_zero_delta():
    # All 6 components for [Guinsoos, JG, Archangels] available
    unit = _carry(trios=[["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]])
    i = inp([unit], ["RB", "Rod", "Glove", "Rod", "Tear", "Rod"])
    r = run(i)
    assert r.all_units[0].delta_count == 0
    assert r.all_units[0].bis_trio_realistic == ["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]


def test_exact_bis_partial_items_on_unit():
    # Unit already holds GuinsoosRageblade (consumed RB+Rod); bench has Glove+Rod+Tear+Rod
    unit = _carry(
        items=["GuinsoosRageblade"],
        trios=[["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]],
    )
    i = inp([unit], ["Glove", "Rod", "Tear", "Rod"])
    r = run(i)
    assert r.all_units[0].delta_count == 0


# ── Realistic trio differs from ideal ─────────────────────────────────────────

def test_realistic_differs_from_ideal():
    # Ideal: [Guinsoos, JG, Archangels] needs Rod×3, RB, Glove, Tear
    # Backup: [InfinityEdge, BlueBuff, HextechGunblade] needs BF×2, Glove, Tear×2, Rod
    # Bench only has [BF, Glove, BF, Tear, Tear, Rod] → backup achievable, ideal not
    ideal = ["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]
    backup = ["InfinityEdge", "BlueBuff", "HextechGunblade"]
    unit = _carry(trios=[ideal, backup])
    bench = ["BF", "Glove", "BF", "Tear", "Tear", "Rod"]
    i = inp([unit], bench)
    r = run(i)
    assert r.all_units[0].bis_trio_ideal == ideal
    assert r.all_units[0].bis_trio_realistic == backup
    assert r.all_units[0].delta_count == 0


def test_partial_components_picks_best_trio():
    # 4 of 6 components for ideal available, 2 of 6 for backup
    # Ideal partial: needs Rod×3 RB Glove Tear — bench: Rod Rod Rod RB = 4/6 components
    # So delta_count for ideal = 2 (missing Glove and Tear)
    ideal = ["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]
    backup = ["Rabadon", "Rabadon", "Rabadon"]  # needs Rod×6 — we have 3 → delta 3
    unit = _carry(trios=[ideal, backup])
    bench = ["RB", "Rod", "Rod", "Rod"]  # 4 comps, all for ideal
    i = inp([unit], bench)
    r = run(i)
    # ideal delta=2 (missing Glove, Tear) vs backup delta=3 → ideal wins as realistic
    assert r.all_units[0].bis_trio_realistic == ideal
    assert r.all_units[0].delta_count == 2


# ── Item-starved scenario ─────────────────────────────────────────────────────

def test_item_starved_high_delta():
    unit = _carry(trios=[["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]])
    i = inp([unit], [])  # empty bench
    r = run(i)
    assert r.all_units[0].delta_count == 6  # need all 6 components


def test_item_starved_no_slammable():
    unit = _carry()
    i = inp([unit], [])
    r = run(i)
    assert r.slammable_now == []


# ── Multiple carries competing for same components ────────────────────────────

def test_priority_ranking_star_matters():
    unit_1star = _carry(api="TFT17_A", display="A", cost=4, star=1, value_class="S", in_comp=True)
    unit_2star = _carry(api="TFT17_B", display="B", cost=4, star=2, value_class="S", in_comp=True)
    i = inp([unit_1star, unit_2star], [])
    r = run(i)
    assert r.priority_units[0].api_name == "TFT17_B"  # 2★ first


def test_priority_ranking_value_class_matters():
    s_class = _carry(api="TFT17_S", display="S", cost=3, star=2, value_class="S", in_comp=True)
    c_class = _carry(api="TFT17_C", display="C", cost=3, star=2, value_class="C", in_comp=True)
    i = inp([s_class, c_class], [])
    r = run(i)
    assert r.priority_units[0].api_name == "TFT17_S"


def test_priority_ranking_in_comp_bonus():
    in_comp = _carry(api="TFT17_A", display="A", cost=3, star=2, value_class="A", in_comp=True)
    off_comp = _carry(api="TFT17_B", display="B", cost=3, star=2, value_class="A", in_comp=False)
    i = inp([in_comp, off_comp], [])
    r = run(i)
    assert r.priority_units[0].api_name == "TFT17_A"


def test_max_two_priority_units():
    units = [_carry(api=f"TFT17_{x}", display=str(x), cost=3) for x in range(5)]
    i = inp(units, [])
    r = run(i)
    assert len(r.priority_units) == 2


# ── Slammable detection ───────────────────────────────────────────────────────

def test_slammable_when_both_components_held():
    unit = _carry(trios=[["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]])
    i = inp([unit], ["RB", "Rod"])  # can build GuinsoosRageblade
    r = run(i)
    item_ids = [s.item_id for s in r.slammable_now]
    assert "GuinsoosRageblade" in item_ids


def test_slammable_requires_both_components():
    unit = _carry()
    i = inp([unit], ["RB"])  # only one component
    r = run(i)
    item_ids = [s.item_id for s in r.slammable_now]
    assert "GuinsoosRageblade" not in item_ids


def test_slammable_double_component_item():
    unit = _carry(trios=[["BlueBuff"]])
    i = inp([unit], ["Tear", "Tear"])  # BlueBuff = Tear + Tear
    r = run(i)
    item_ids = [s.item_id for s in r.slammable_now]
    assert "BlueBuff" in item_ids


def test_slammable_double_component_requires_two():
    unit = _carry(trios=[["BlueBuff"]])
    i = inp([unit], ["Tear"])  # only one Tear — not enough
    r = run(i)
    item_ids = [s.item_id for s in r.slammable_now]
    assert "BlueBuff" not in item_ids


# ── Wasted components ─────────────────────────────────────────────────────────

def test_wasted_components_detected():
    unit = _carry(trios=[["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]])
    # Warmogs needs Belt+Belt — irrelevant to this unit's trio
    i = inp([unit], ["Belt", "Belt"])
    r = run(i)
    assert "Belt" in r.wasted_components


def test_no_wasted_when_all_useful():
    unit = _carry(trios=[["GuinsoosRageblade", "JeweledGauntlet", "ArchangelsStaff"]])
    i = inp([unit], ["RB", "Rod"])  # both useful for Guinsoos
    r = run(i)
    assert r.wasted_components == []


# ── Output structure ──────────────────────────────────────────────────────────

def test_components_held_dict():
    unit = _carry()
    i = inp([unit], ["BF", "BF", "Rod"])
    r = run(i)
    assert r.components_held == {"BF": 2, "Rod": 1}


def test_result_serializes():
    unit = _carry()
    i = inp([unit], ["Rod", "RB"])
    r = run(i)
    d = r.model_dump()
    assert "priority_units" in d
    assert "all_units" in d
    assert "slammable_now" in d


# ── Determinism ───────────────────────────────────────────────────────────────

def test_deterministic():
    unit = _carry()
    i = inp([unit], ["RB", "Rod", "Glove", "Tear"])
    r1 = run(i)
    r2 = run(i)
    assert r1.model_dump() == r2.model_dump()


# ── Value label thresholds ────────────────────────────────────────────────────

def test_value_label_s_for_5cost_2star():
    unit = _carry(api="TFT17_X", cost=5, star=2, value_class="S", in_comp=True)
    i = inp([unit], [])
    r = run(i)
    assert r.all_units[0].value_label == "S"


def test_value_label_c_for_utility():
    unit = _carry(api="TFT17_Y", cost=1, star=1, value_class="utility", in_comp=False)
    i = inp([unit], [])
    r = run(i)
    assert r.all_units[0].value_label == "C"


# ── Empty board ───────────────────────────────────────────────────────────────

def test_empty_board():
    i = inp([], ["Rod", "BF"])
    r = run(i)
    assert r.all_units == []
    assert r.priority_units == []
    assert r.slammable_now == []
    assert r.wasted_components == []
