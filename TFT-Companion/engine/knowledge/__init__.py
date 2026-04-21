"""knowledge — YAML loader + query helpers for Augie v2.

All set-specific and set-invariant numbers live in `knowledge/*.yaml`. Every
downstream module accesses them through the helpers here — nobody re-reads YAML.

See `skills/knowledge/SKILL.md` for the public-API contract. Types are in
`schemas.py` (frozen per CLAUDE.md hard rule #3).

CDragon versioning
------------------
CDRAGON_PATCH is "latest" while Set 17 is the active LoL patch's TFT set.
/latest/ is safe here because Set 17 IS the current live set; verify_set_prefix()
guards against staleness: if /latest/ ever rolls to the next set's data before
we update this constant, the prefix mismatch will raise at startup rather than
silently corrupting the knowledge pack. Pin to a specific LoL patch (e.g. "16.8")
only when /latest/ becomes stale during a patch transition.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

import yaml

from schemas import CoreKnowledge, PoolInfo, SetKnowledge

_HERE = Path(__file__).parent

_CORE: Optional[CoreKnowledge] = None
_SET_CACHE: dict[str, SetKnowledge] = {}

# ── CDragon URL constants ──────────────────────────────────────────────────────
# "latest" while Set 17 is active; pin to a specific patch (e.g. "16.8") only
# if /latest/ becomes stale at a set boundary. verify_set_prefix() is the guard.
CDRAGON_PATCH = "latest"
CDRAGON_BASE  = f"https://raw.communitydragon.org/{CDRAGON_PATCH}"

# ── Active TFT set prefix (detected at runtime) ───────────────────────────────
_ACTIVE_PREFIX: Optional[str] = None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_core(path: Path | None = None) -> CoreKnowledge:
    """Load and cache `knowledge/core.yaml`. Singleton."""
    global _CORE
    if _CORE is not None and path is None:
        return _CORE
    target = path or (_HERE / "core.yaml")
    with target.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    core = CoreKnowledge.model_validate(raw)
    if path is None:
        _CORE = core
    return core


def load_set(set_id: str, path: Path | None = None) -> SetKnowledge:
    """Load and cache `knowledge/set_<set_id>.yaml`.

    Also caches the active TFT##_ prefix from set_id so get_active_prefix()
    works in the YAML-only path. _cache_active_prefix(cdragon_data) overrides
    this with the live-detected prefix when CDragon data is available.
    """
    global _ACTIVE_PREFIX
    key = str(set_id)
    if key in _SET_CACHE and path is None:
        return _SET_CACHE[key]
    target = path or (_HERE / f"set_{key}.yaml")
    with target.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    # Normalize: set_id must be a string even if the YAML wrote it as an int.
    if "set_id" in raw:
        raw["set_id"] = str(raw["set_id"])
    s = SetKnowledge.model_validate(raw)
    if path is None:
        _SET_CACHE[key] = s
    # Derive prefix from set_id (YAML path). CDragon path overrides via _cache_active_prefix().
    if _ACTIVE_PREFIX is None:
        _ACTIVE_PREFIX = f"TFT{key}_"
    return s


# ---------------------------------------------------------------------------
# Query helpers — callers use these, not raw dict access
# ---------------------------------------------------------------------------

def shop_odds(set_: SetKnowledge, level: int) -> list[float]:
    """Return `[p_1, p_2, p_3, p_4, p_5]` as fractions summing to 1.0.

    Level clamped to [1, 11].
    """
    clamped = max(1, min(11, level))
    percents = set_.shop_odds[clamped]
    return [round(p / 100.0, 6) for p in percents]


def pool_size(set_: SetKnowledge, cost: int) -> PoolInfo:
    """Return PoolInfo for a cost tier 1..5."""
    if cost not in set_.pool_sizes:
        raise KeyError(f"no pool_size for cost {cost} in set {set_.set_id}")
    return set_.pool_sizes[cost]


def xp_to_reach(core: CoreKnowledge, level: int) -> int:
    """Cumulative XP needed from L1 to reach `level`."""
    if level < 2 or level > 11:
        raise ValueError(f"xp_to_reach expects level in [2, 11], got {level}")
    total = 0
    for thr in core.xp_thresholds:
        total += thr.xp
        if thr.to_level == level:
            return total
    raise ValueError(f"no threshold chain reaches level {level}")


def xp_for_next_level(core: CoreKnowledge, current_level: int) -> int:
    """XP needed from `current_level` to `current_level + 1`."""
    for thr in core.xp_thresholds:
        if thr.from_level == current_level:
            return thr.xp
    raise ValueError(f"no threshold from level {current_level}")


def streak_bonus(core: CoreKnowledge, streak: int) -> int:
    """Bonus gold for a streak. Win/loss symmetric — uses |streak|."""
    n = abs(streak)
    for br in core.streak_brackets:
        if br.low <= n <= br.high:
            return br.bonus
    return 0


def interest(core: CoreKnowledge, gold: int) -> int:
    """Interest earned at start of round. Capped at `core.interest_cap`."""
    if gold < 0:
        return 0
    raw = gold // 10 * core.interest_per_10_gold
    return min(core.interest_cap, raw)


def spike_round_next(set_: SetKnowledge, current_stage: str) -> dict | None:
    """If the *next* round is a known spike, return `{stage, archetype}`. Else None."""
    nxt = _next_stage(current_stage)
    if nxt is None:
        return None
    for sp in set_.spike_rounds:
        if sp.stage == nxt:
            return {"stage": sp.stage, "archetype": sp.archetype}
    return None


# ---------------------------------------------------------------------------
# Stage helper
# ---------------------------------------------------------------------------

def _next_stage(stage: str) -> str | None:
    """`"X-Y"` -> `"X-(Y+1)"` up to Y=7, then `"(X+1)-1"`. Returns None on bad input."""
    try:
        x_str, y_str = stage.split("-", 1)
        x = int(x_str)
        y = int(y_str)
    except (ValueError, AttributeError):
        return None
    if y < 7:
        return f"{x}-{y + 1}"
    return f"{x + 1}-1"


# ---------------------------------------------------------------------------
# CDragon sanity check and dynamic prefix detection (Tasks 4 & 7)
# ---------------------------------------------------------------------------

def verify_set_prefix(cdragon_data: dict, expected_prefix: str = "TFT17_") -> None:
    """Verify the active TFT set prefix in CDragon data matches expectation.

    Samples up to 20 apiNames from items or sets.*.champions, counts prefix
    frequencies, and raises RuntimeError if the majority prefix isn't
    expected_prefix. Catches CDragon /latest/ staleness bugs and set-boundary
    mismatches before they silently corrupt the knowledge pack.

    Args:
        cdragon_data:    Parsed JSON from the CDragon TFT endpoint.
        expected_prefix: The prefix we expect to be dominant (e.g. "TFT17_").

    Raises:
        RuntimeError: if the dominant prefix doesn't match, or if no apiNames
                      are found at all (CDragon schema changed).
    """
    sample_api_names: list[str] = []
    for section in ("items", "sets"):
        if section not in cdragon_data:
            continue
        raw = cdragon_data[section]
        if isinstance(raw, list):
            sample_api_names.extend(x.get("apiName", "") for x in raw[:20])
        elif isinstance(raw, dict):
            for v in raw.values():
                if isinstance(v, dict) and "champions" in v:
                    sample_api_names.extend(
                        c.get("apiName", "") for c in v["champions"][:20]
                    )
                    break

    if not sample_api_names:
        raise RuntimeError(
            "CDragon data has no apiName fields — data schema may have changed"
        )

    prefixes: Counter[str] = Counter()
    for name in sample_api_names:
        if name.startswith("TFT") and "_" in name:
            pfx = name.split("_", 1)[0] + "_"
            prefixes[pfx] += 1

    if not prefixes:
        raise RuntimeError(
            f"No TFT##_ prefixes found in sample of {len(sample_api_names)} apiNames. "
            f"Sample: {sample_api_names[:5]}"
        )

    top_prefix, top_count = prefixes.most_common(1)[0]
    if top_prefix != expected_prefix:
        raise RuntimeError(
            f"Set prefix mismatch: expected {expected_prefix}, found {top_prefix} "
            f"(distribution: {dict(prefixes)}). "
            f"This usually means CDragon /latest/ is stale OR CDRAGON_PATCH in "
            f"knowledge/__init__.py needs updating to match the new set."
        )


def detect_active_prefix(cdragon_data: dict) -> str:
    """Scan apiNames from CDragon data and return the most common TFT##_ prefix.

    Used to avoid hardcoding "TFT17_" in production code. Called once at set
    load time; result cached in _ACTIVE_PREFIX.

    Args:
        cdragon_data: Parsed JSON from the CDragon TFT endpoint.

    Returns:
        The dominant prefix string, e.g. "TFT17_" or "TFT18_".

    Raises:
        RuntimeError: if no TFT##_ prefixes are found.
    """
    api_names: list[str] = []
    if "items" in cdragon_data and isinstance(cdragon_data["items"], list):
        api_names.extend(x.get("apiName", "") for x in cdragon_data["items"])
    if "sets" in cdragon_data and isinstance(cdragon_data["sets"], dict):
        for s in cdragon_data["sets"].values():
            if isinstance(s, dict):
                api_names.extend(c.get("apiName", "") for c in s.get("champions", []))
                api_names.extend(t.get("apiName", "") for t in s.get("traits", []))

    prefixes: Counter[str] = Counter()
    for name in api_names:
        if name.startswith("TFT") and "_" in name:
            pfx = name.split("_", 1)[0] + "_"
            prefixes[pfx] += 1

    if not prefixes:
        raise RuntimeError("No TFT##_ apiNames found in CDragon data")

    top, _ = prefixes.most_common(1)[0]
    return top


def get_active_prefix() -> str:
    """Return the cached active TFT##_ prefix.

    Populated by _cache_active_prefix() which is called from load_set().
    Raises if load_set() hasn't been called yet.
    """
    if _ACTIVE_PREFIX is None:
        raise RuntimeError(
            "Active prefix not initialized — call load_set() before get_active_prefix()"
        )
    return _ACTIVE_PREFIX


def _cache_active_prefix(data: dict) -> None:
    """Store the dominant prefix from CDragon data into the module-level cache."""
    global _ACTIVE_PREFIX
    try:
        _ACTIVE_PREFIX = detect_active_prefix(data)
    except RuntimeError:
        pass  # offline / YAML-only path — prefix stays None until a live fetch
