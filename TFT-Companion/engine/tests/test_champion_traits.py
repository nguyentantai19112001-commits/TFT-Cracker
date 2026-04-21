"""Regression tests for the champion → traits mapping (Phase B).

These tests lock the migration performed by scripts/fill_champion_traits.py.
If any test here fails, the YAML data has drifted from its expected state.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ENGINE):
    sys.path.insert(0, str(_ENGINE))

import pytest
from knowledge import load_set

SET17 = load_set("17")
KNOWN_TRAIT_NAMES = {t["name"] for t in SET17.traits}
EXPECTED_CHAMPION_COUNT = 63  # locked at Phase B migration — 14+13+13+13+10


# ── Test 1 ─────────────────────────────────────────────────────────────────

def test_every_champion_has_at_least_one_trait():
    """Every playable champion in set_17 must have ≥1 trait after migration."""
    missing = [
        c["name"]
        for c in SET17.champions
        if not c.get("traits")
    ]
    assert not missing, (
        f"{len(missing)} champion(s) have no traits populated: {missing}"
    )


# ── Test 2 ─────────────────────────────────────────────────────────────────

def test_every_trait_name_resolves():
    """Every trait name in champion.traits must exist in set_17.traits.

    Guards against typos introduced by the migration (e.g. "Dark star" vs
    "Dark Star", or "N.O.V.A" vs "N.O.V.A.").
    """
    bad: list[str] = []
    for champ in SET17.champions:
        for trait in champ.get("traits", []):
            if trait not in KNOWN_TRAIT_NAMES:
                bad.append(f"{champ['name']}: unknown trait '{trait}'")
    assert not bad, "\n".join(bad)


# ── Test 3 ─────────────────────────────────────────────────────────────────

def test_champion_count_unchanged():
    """Champion count must remain exactly 63 (locked at Phase B migration).

    If this fails, a champion was accidentally added or deleted from set_17.yaml.
    """
    assert len(SET17.champions) == EXPECTED_CHAMPION_COUNT, (
        f"Expected {EXPECTED_CHAMPION_COUNT} champions, got {len(SET17.champions)}"
    )


# ── Test 4 ─────────────────────────────────────────────────────────────────

def test_miss_fortune_excludes_choose_trait():
    """Miss Fortune's traits must NOT include 'Choose Trait' (artifact filter).

    'Choose Trait' is a UI mechanic artifact in the source JSON. The migration
    script filters it via ARTIFACT_TRAITS before writing to YAML.
    """
    champ_map = {c["name"]: c for c in SET17.champions}
    assert "Miss Fortune" in champ_map, "Miss Fortune missing from champions list"
    mf_traits = champ_map["Miss Fortune"].get("traits", [])
    assert "Choose Trait" not in mf_traits, (
        f"Artifact trait 'Choose Trait' leaked into Miss Fortune's traits: {mf_traits}"
    )
    assert "Gun Goddess" in mf_traits, (
        f"Miss Fortune should have 'Gun Goddess' trait, got: {mf_traits}"
    )


# ── Test 5 ─────────────────────────────────────────────────────────────────

def test_no_champion_has_empty_traits_list():
    """No champion may have traits: [] — that is a migration bug.

    After migration every champion either has traits populated (≥1 item) or
    the field is absent entirely. An empty list means the script wrote []
    instead of skipping the champion, which the safeguard should prevent.
    """
    empty = [
        c["name"]
        for c in SET17.champions
        if "traits" in c and c["traits"] == []
    ]
    assert not empty, (
        f"Champions with empty traits list (migration bug): {empty}"
    )
