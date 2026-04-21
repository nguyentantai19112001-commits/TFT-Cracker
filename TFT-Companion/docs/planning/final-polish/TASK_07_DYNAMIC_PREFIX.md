# TASK_07_DYNAMIC_PREFIX.md — Dynamic `TFT##_` prefix detection

> Remove all hardcoded `"TFT17_"` string literals from code. Detect the
> active prefix from the loaded CDragon data at runtime. Make Set 18
> migration a YAML change, not a code change.

---

## Prereq checks

```bash
pytest -q                          # 124/124 (or whatever after Task 6)
grep -rn 'TFT17_' --include='*.py' . | grep -v 'test'
    # capture every hardcoded TFT17_ in non-test .py files
```

Task 4 introduced a sanity check with `expected_prefix="TFT17_"` — that
usage is INTENTIONAL (it's verifying a hardcoded expectation at startup).
Do not remove that one. Everything else (parsing, filtering, dispatch)
should use the dynamically detected prefix.

## Files you may edit

- `knowledge/__init__.py` — add prefix detection function and caching
- Any other .py file with hardcoded `TFT17_` in logic (not tests)
- `tests/test_dynamic_prefix.py` (new)
- `STATE.md`

## The change

### Detection + caching

In `knowledge/__init__.py`:

```python
from typing import Optional
from collections import Counter

_ACTIVE_PREFIX: Optional[str] = None


def detect_active_prefix(cdragon_data: dict) -> str:
    """Scan apiNames, return the most common TFT##_ prefix.

    Called once per set load, result cached in _ACTIVE_PREFIX.
    """
    api_names: list[str] = []
    # Scan likely sections: items, sets.*.champions, sets.*.traits
    if "items" in cdragon_data and isinstance(cdragon_data["items"], list):
        api_names.extend(x.get("apiName", "") for x in cdragon_data["items"])
    if "sets" in cdragon_data and isinstance(cdragon_data["sets"], dict):
        for s in cdragon_data["sets"].values():
            if isinstance(s, dict):
                api_names.extend(c.get("apiName", "") for c in s.get("champions", []))
                api_names.extend(t.get("apiName", "") for t in s.get("traits", []))

    prefixes = Counter()
    for name in api_names:
        if name.startswith("TFT") and "_" in name:
            pfx = name.split("_", 1)[0] + "_"
            prefixes[pfx] += 1

    if not prefixes:
        raise RuntimeError("No TFT##_ apiNames found in CDragon data")

    top, _ = prefixes.most_common(1)[0]
    return top


def get_active_prefix() -> str:
    """Return the cached active TFT##_ prefix. Raises if not yet loaded."""
    if _ACTIVE_PREFIX is None:
        raise RuntimeError(
            "Active prefix not initialized — call load_set() first"
        )
    return _ACTIVE_PREFIX


def _cache_active_prefix(data: dict) -> None:
    global _ACTIVE_PREFIX
    _ACTIVE_PREFIX = detect_active_prefix(data)
```

Call `_cache_active_prefix(cdragon_data)` inside `load_set()` right
after fetching the data and before `verify_set_prefix()` (which already
exists from Task 4).

### Replace hardcoded usages

For every hardcoded `"TFT17_"` you found in grep:

```python
# BEFORE
if unit_id.startswith("TFT17_"):
    ...

# AFTER
from knowledge import get_active_prefix
if unit_id.startswith(get_active_prefix()):
    ...
```

Or, if the hardcode is in a module that imports knowledge circularly,
pass the prefix as a parameter.

### Tests

```python
# tests/test_dynamic_prefix.py
import pytest
from knowledge import detect_active_prefix


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
    """Champions nested under sets.<id>.champions should count."""
    data = {"sets": {"17": {"champions": [
        {"apiName": "TFT17_Jinx"},
        {"apiName": "TFT17_Akali"},
    ]}}}
    assert detect_active_prefix(data) == "TFT17_"
```

## Acceptance gate

1. `grep -rn 'TFT17_' --include='*.py' .` in non-test .py files: returns
   at most ONE match (the `expected_prefix="TFT17_"` sanity check from
   Task 4). All other matches replaced with `get_active_prefix()`.
2. All existing tests still pass.
3. New prefix tests pass (4/4).
4. Startup still works: `python -c "import knowledge; knowledge.load_set('17')"`
   completes without error.

## Commit message

```
Task 7: detect TFT##_ prefix dynamically instead of hardcoding

- knowledge.detect_active_prefix + get_active_prefix cached at load
- All hardcoded "TFT17_" in production code replaced with dynamic call
- Task-4's sanity-check expected_prefix remains hardcoded (that's its job)
- 4 new tests covering detection edge cases

Tests: +4. Set 18 migration becomes a YAML change, not a code change.
```
