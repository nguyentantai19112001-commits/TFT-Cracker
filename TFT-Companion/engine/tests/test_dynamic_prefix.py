"""Tests for dynamic TFT##_ prefix detection (Task 7).

detect_active_prefix() scans CDragon apiNames and returns the dominant prefix.
get_active_prefix() returns the cached value set by load_set() or _cache_active_prefix().
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest
from knowledge import detect_active_prefix, get_active_prefix, load_set


def test_detects_tft17_majority():
    data = {"items": [
        {"apiName": "TFT17_Jinx"},
        {"apiName": "TFT17_Akali"},
        {"apiName": "TFT17_Karma"},
        {"apiName": "TFT13_LegacyItem"},
    ]}
    assert detect_active_prefix(data) == "TFT17_"


def test_detects_different_prefix():
    """If Set 18 data is loaded, detection returns TFT18_."""
    data = {"items": [
        {"apiName": "TFT18_NewChamp1"},
        {"apiName": "TFT18_NewChamp2"},
        {"apiName": "TFT18_NewItem"},
    ]}
    assert detect_active_prefix(data) == "TFT18_"


def test_no_prefix_raises():
    data = {"items": [{"apiName": ""}, {"apiName": "NoPrefix"}]}
    with pytest.raises(RuntimeError):
        detect_active_prefix(data)


def test_sets_section_also_scanned():
    """Champions nested under sets.<id>.champions should count toward the prefix."""
    data = {"sets": {"17": {"champions": [
        {"apiName": "TFT17_Jinx"},
        {"apiName": "TFT17_Akali"},
    ]}}}
    assert detect_active_prefix(data) == "TFT17_"


def test_load_set_populates_prefix():
    """load_set() must populate _ACTIVE_PREFIX so get_active_prefix() works."""
    load_set("17")
    prefix = get_active_prefix()
    assert prefix == "TFT17_", f"expected TFT17_, got {prefix}"


def test_cache_active_prefix_overrides():
    """_cache_active_prefix() with CDragon data overrides the YAML-derived prefix."""
    from knowledge import _cache_active_prefix
    fake_data = {"items": [
        {"apiName": "TFT18_Jinx"},
        {"apiName": "TFT18_Akali"},
        {"apiName": "TFT18_Karma"},
    ]}
    _cache_active_prefix(fake_data)
    assert get_active_prefix() == "TFT18_"
    # Restore so other tests aren't poisoned
    from knowledge import _cache_active_prefix as _cap
    _cap({"items": [{"apiName": "TFT17_Restore"}]})


def test_traits_section_also_scanned():
    """Traits nested under sets.<id>.traits should count toward the prefix."""
    data = {"sets": {"17": {"traits": [
        {"apiName": "TFT17_Sugarcraft"},
        {"apiName": "TFT17_Witchcraft"},
    ]}}}
    assert detect_active_prefix(data) == "TFT17_"
