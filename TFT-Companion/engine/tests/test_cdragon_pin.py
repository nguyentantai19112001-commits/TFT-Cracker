"""Tests for CDragon URL pinning and startup prefix sanity check (Task 4).

verify_set_prefix() is the guard that catches CDragon /latest/ staleness
bugs before they silently corrupt the knowledge pack. These tests verify
it accepts correct data and raises on stale or mismatched data.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(_ROOT):
    sys.path.insert(0, str(_ROOT))

import pytest
from knowledge import verify_set_prefix, CDRAGON_PATCH, CDRAGON_BASE


def test_cdragon_patch_is_pinned():
    """CDRAGON_PATCH must not be 'latest'."""
    assert CDRAGON_PATCH != "latest", (
        "CDRAGON_PATCH must be a version string like '17.1', not 'latest'"
    )
    assert "." in CDRAGON_PATCH, "CDRAGON_PATCH must look like 'N.M' e.g. '17.1'"


def test_cdragon_base_uses_patch():
    """CDRAGON_BASE URL must contain the patch version, not /latest/."""
    assert "/latest/" not in CDRAGON_BASE
    assert CDRAGON_PATCH in CDRAGON_BASE


def test_correct_prefix_passes():
    """Majority TFT17_ data should pass without raising."""
    fake_data = {"items": [
        {"apiName": "TFT17_Jinx"},
        {"apiName": "TFT17_Akali"},
        {"apiName": "TFT17_Karma"},
    ]}
    verify_set_prefix(fake_data, expected_prefix="TFT17_")  # must not raise


def test_stale_data_raises():
    """Majority TFT13_ data should raise RuntimeError about mismatch."""
    fake_data = {"items": [
        {"apiName": "TFT13_Katarina"},
        {"apiName": "TFT13_Yorick"},
    ]}
    with pytest.raises(RuntimeError, match="Set prefix mismatch"):
        verify_set_prefix(fake_data, expected_prefix="TFT17_")


def test_empty_data_raises():
    """No apiNames at all should raise RuntimeError."""
    with pytest.raises(RuntimeError):
        verify_set_prefix({"items": []}, expected_prefix="TFT17_")


def test_no_tft_prefix_in_data_raises():
    """Data with apiNames but no TFT##_ prefix should raise RuntimeError."""
    fake_data = {"items": [
        {"apiName": "SomeOtherItem"},
        {"apiName": "AnotherItem"},
    ]}
    with pytest.raises(RuntimeError):
        verify_set_prefix(fake_data, expected_prefix="TFT17_")


def test_mixed_prefixes_majority_wins():
    """9 TFT17_ and 1 TFT13_ (legacy item) — majority is TFT17_, should pass."""
    fake_data = {"items": [
        *({"apiName": f"TFT17_Unit{i}"} for i in range(9)),
        {"apiName": "TFT13_LegacyItem"},
    ]}
    verify_set_prefix(fake_data, expected_prefix="TFT17_")  # must not raise


def test_sets_section_scanned():
    """Champions nested under sets.<id>.champions should count toward prefix."""
    fake_data = {"sets": {"17": {"champions": [
        {"apiName": "TFT17_Jinx"},
        {"apiName": "TFT17_Akali"},
    ]}}}
    verify_set_prefix(fake_data, expected_prefix="TFT17_")  # must not raise
