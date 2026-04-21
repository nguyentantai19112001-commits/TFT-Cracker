# TASK_04_CDRAGON_PIN.md — Pin Community Dragon URLs to patch version

> Replace `/latest/` with `/17.1/` everywhere. Add a startup sanity check that
> verifies the active `TFT##_` prefix in returned data matches expectations.

---

## Why this matters

Community Dragon's `/latest/` endpoint has a known staleness lag — confirmed
during earlier research, it returned Set 13 items in the top of the array
5 days after Set 17.1 launched. This silently corrupts the knowledge pack
for the first week of every new set.

## Prereq checks

```bash
pytest -q                          # 117/117
git status                         # clean
grep -rn "communitydragon\.org/latest" .
    # capture every occurrence — you'll fix each
```

## Files you may edit

- Any file containing `raw.communitydragon.org/latest` (usually data
  fetcher scripts or knowledge loader)
- Optionally: `knowledge/__init__.py` to add the sanity check
- `tests/test_cdragon_pin.py` (new, tiny)
- `STATE.md`

## The change

### Part 1 — replace URLs

Find every `raw.communitydragon.org/latest/...` and replace with
`raw.communitydragon.org/17.1/...`.

If a config-driven pattern already exists (e.g. a `CDRAGON_VERSION`
constant), prefer that. Otherwise add one in the knowledge loader:

```python
# knowledge/__init__.py or wherever the CDragon fetches live
CDRAGON_PATCH = "17.1"
CDRAGON_BASE = f"https://raw.communitydragon.org/{CDRAGON_PATCH}"
```

Any time CDragon is fetched, use `CDRAGON_BASE` + the path suffix.

### Part 2 — sanity check on startup

Add a function that runs once at knowledge load:

```python
def verify_set_prefix(cdragon_data: dict, expected_prefix: str = "TFT17_") -> None:
    """Verify the active TFT set prefix in CDragon data matches expectation.

    Looks at the first 20 champions/items/augments and counts prefix frequencies.
    Raises RuntimeError if expected prefix isn't the majority — this catches
    CDragon staleness bugs (/latest/ returning Set 13 data, prefix mismatch
    after Set 18 rolls, etc.).
    """
    from collections import Counter

    sample_api_names: list[str] = []
    for section in ("items", "sets"):
        if section in cdragon_data:
            raw = cdragon_data[section]
            if isinstance(raw, dict):
                # sets is dict of {set_id: {champions: [...]}}; take first set's champs
                for v in raw.values():
                    if isinstance(v, dict) and "champions" in v:
                        sample_api_names.extend(c.get("apiName", "") for c in v["champions"][:20])
                        break
            elif isinstance(raw, list):
                sample_api_names.extend(x.get("apiName", "") for x in raw[:20])

    if not sample_api_names:
        raise RuntimeError("CDragon data has no apiName fields — data schema changed")

    # Count prefixes (TFT17_, TFT16_, etc.)
    prefixes = Counter()
    for name in sample_api_names:
        if name.startswith("TFT"):
            pfx = name.split("_", 1)[0] + "_"
            prefixes[pfx] += 1

    if not prefixes:
        raise RuntimeError(f"No TFT##_ prefixes found in sample of {len(sample_api_names)}")

    top_prefix, top_count = prefixes.most_common(1)[0]
    if top_prefix != expected_prefix:
        raise RuntimeError(
            f"Set prefix mismatch: expected {expected_prefix}, found {top_prefix} "
            f"(distribution: {dict(prefixes)}). "
            f"This usually means CDragon /latest/ is stale OR you need to update "
            f"CDRAGON_PATCH in knowledge/__init__.py."
        )
```

Call `verify_set_prefix(data)` inside `load_set("17")` after fetching.

### Part 3 — tests

```python
# tests/test_cdragon_pin.py
import pytest
from knowledge import verify_set_prefix


def test_correct_prefix_passes():
    fake_data = {"items": [
        {"apiName": "TFT17_Jinx"},
        {"apiName": "TFT17_Akali"},
        {"apiName": "TFT17_Karma"},
    ]}
    verify_set_prefix(fake_data, expected_prefix="TFT17_")  # no raise


def test_stale_data_raises():
    fake_data = {"items": [
        {"apiName": "TFT13_Katarina"},
        {"apiName": "TFT13_Yorick"},
    ]}
    with pytest.raises(RuntimeError, match="Set prefix mismatch"):
        verify_set_prefix(fake_data, expected_prefix="TFT17_")


def test_empty_data_raises():
    with pytest.raises(RuntimeError):
        verify_set_prefix({"items": []}, expected_prefix="TFT17_")


def test_mixed_prefixes_picks_majority():
    """If 9/10 are TFT17_ and 1/10 is TFT13_ (legacy), pass."""
    fake_data = {"items": [
        *({"apiName": f"TFT17_Unit{i}"} for i in range(9)),
        {"apiName": "TFT13_Legacy"},
    ]}
    verify_set_prefix(fake_data, expected_prefix="TFT17_")
```

## Acceptance gate

1. `grep -rn "communitydragon\.org/latest" .` returns zero matches in .py files.
2. `pytest -q` shows 121/121 passing (117 + 4 new).
3. Manual verification: start the app, confirm it loads Set 17 data
   without raising the sanity-check error.

## Commit message

```
Task 4: pin Community Dragon URLs to patch 17.1

- Replaced all /latest/ references with /17.1/ via CDRAGON_PATCH constant
- Added verify_set_prefix() sanity check that runs at knowledge load
- Raises clear error if CDragon returns stale or mismatched-set data

Tests: 117 → 121. Prevents silent knowledge-pack corruption at set boundary.
```
