# TASK_02_VALIDATION.md — State validation layer

> Protects the scorer from corrupted state that would produce confidently
> wrong advice. Every field that reaches the scorer has been validated.

---

## Goal

Before `recommender.top_k()` runs, validate that the `GameState` it will
score is internally consistent and within known bounds. If validation
fails, skip the scorer, log the bad state with full context, and display
"verifying state…" in the overlay instead of bad advice.

## Why this matters

The single worst failure mode for a live coach is NOT crashing — it's
confidently wrong advice from corrupted state. "Your HP is -43, recommend
rolling to 20g" has to never happen, even once. Validation is the cheapest
insurance against this.

## Prereq checks

```bash
pytest -q                          # confirm 99/99 from Task 1
git status                         # clean tree
```

## Files you may edit

- `validators.py` (new file)
- `assistant_overlay.py` (add the validation call before recommender)
- `tests/test_validators.py` (new)
- `STATE.md`

**Do NOT edit:** anything else. Validation is a gate in front of the
scorer, not a rewrite of the scorer.

## The validation model

```python
# validators.py
"""State validation before scorer.

Runs deterministic bounds and cross-field sanity checks on GameState.
On failure: log the bad state, return a ValidationFailure, let the
overlay display a neutral message instead of scoring corrupted state.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from schemas import GameState


@dataclass
class ValidationFailure:
    """One validation check that failed."""
    check_name: str
    field_path: str
    actual_value: object
    expected: str


@dataclass
class ValidationResult:
    ok: bool
    failures: list[ValidationFailure] = field(default_factory=list)

    @classmethod
    def pass_(cls) -> "ValidationResult":
        return cls(ok=True)

    @classmethod
    def fail(cls, failures: list[ValidationFailure]) -> "ValidationResult":
        return cls(ok=False, failures=failures)


def validate(state: GameState) -> ValidationResult:
    """Run all checks. Returns a combined result with every failure listed."""
    failures: list[ValidationFailure] = []
    _check_bounds(state, failures)
    _check_cross_field(state, failures)
    return ValidationResult(ok=not failures, failures=failures)


# --- Bounds checks ---

def _check_bounds(state: GameState, failures: list[ValidationFailure]) -> None:
    if not (0 <= state.gold <= 999):
        failures.append(ValidationFailure(
            "gold_bounds", "gold", state.gold, "0 <= gold <= 999"
        ))
    if not (-20 <= state.hp <= 100):
        # -20 tolerates display edge cases; anything more negative is broken OCR
        failures.append(ValidationFailure(
            "hp_bounds", "hp", state.hp, "-20 <= hp <= 100"
        ))
    if not (1 <= state.level <= 11):
        failures.append(ValidationFailure(
            "level_bounds", "level", state.level, "1 <= level <= 11"
        ))
    if state.xp_current < 0:
        failures.append(ValidationFailure(
            "xp_current_bounds", "xp_current", state.xp_current, "xp_current >= 0"
        ))
    if state.xp_needed < 0:
        failures.append(ValidationFailure(
            "xp_needed_bounds", "xp_needed", state.xp_needed, "xp_needed >= 0"
        ))
    # Stage must look like "N-M" with both in sensible ranges
    try:
        big, small = state.stage.split("-")
        big_i, small_i = int(big), int(small)
        if not (1 <= big_i <= 7 and 1 <= small_i <= 7):
            failures.append(ValidationFailure(
                "stage_format", "stage", state.stage, "'N-M' with 1-7"
            ))
    except (ValueError, AttributeError):
        failures.append(ValidationFailure(
            "stage_parse", "stage", state.stage, "parseable 'N-M' stage"
        ))


# --- Cross-field checks ---

def _check_cross_field(state: GameState, failures: list[ValidationFailure]) -> None:
    # XP numerator <= denominator when both are non-zero
    if state.xp_needed > 0 and state.xp_current > state.xp_needed:
        failures.append(ValidationFailure(
            "xp_ordering", "xp_current vs xp_needed",
            (state.xp_current, state.xp_needed),
            "xp_current <= xp_needed"
        ))
    # Board size <= level (game enforces this; if violated, OCR misread)
    if len(state.board) > state.level:
        failures.append(ValidationFailure(
            "board_size", "len(board) vs level",
            (len(state.board), state.level),
            "len(board) <= level"
        ))
    # Shop must be exactly 5 slots OR empty (carousel/god round)
    if state.shop and len(state.shop) != 5:
        failures.append(ValidationFailure(
            "shop_size", "len(shop)", len(state.shop),
            "5 slots or 0 (carousel/god round)"
        ))
    # Items per unit <= 3 for every unit on board
    for i, unit in enumerate(state.board):
        if len(unit.items) > 3:
            failures.append(ValidationFailure(
                "items_per_unit", f"board[{i}].items",
                unit.items,
                "<= 3 items per unit"
            ))
    # Augments <= 3
    if len(state.augments) > 3:
        failures.append(ValidationFailure(
            "augment_count", "len(augments)", len(state.augments),
            "<= 3 augments total"
        ))
    # Stage vs augment count: by 2-1 expect >=1, by 3-2 >=2, by 4-2 >=3
    # (This is a heuristic — OCR might miss an augment icon — so we warn, not fail)
    # Skip this check for now; it's observation-dependent.
```

## Integration into `PipelineWorker.run()`

Add this block AFTER `state_builder.build_state()` returns and BEFORE
`rules.evaluate()`:

```python
from validators import validate as validate_state

# ... existing state build ...

validation = validate_state(state)
if not validation.ok:
    # Log the bad state for later debugging
    logger.warning(
        "State validation failed, skipping scorer",
        failures=[f.__dict__ for f in validation.failures],
        state_hash=state.model_dump_json()[:200],  # truncated for log size
    )
    self.verdictReady.emit("⚠ verifying state — press F9 again in a moment")
    self.errorOccurred.emit("state_validation_failed")
    return

# Continue to rules → comp_planner → recommender → advisor as wired in Task 1
```

## Tests

```python
# tests/test_validators.py
import pytest
from validators import validate, ValidationResult
from schemas import GameState, BoardUnit, ShopSlot


def _valid_state(**overrides) -> GameState:
    base = dict(
        stage="3-2", gold=30, hp=70, level=6,
        xp_current=5, xp_needed=36, streak=0, set_id="17",
    )
    base.update(overrides)
    return GameState(**base)


def test_valid_state_passes():
    assert validate(_valid_state()).ok


def test_negative_gold_fails():
    state = _valid_state()
    state.gold = -5
    result = validate(state)
    assert not result.ok
    assert any(f.check_name == "gold_bounds" for f in result.failures)


def test_hp_over_100_fails():
    state = _valid_state()
    state.hp = 150
    result = validate(state)
    assert not result.ok


def test_hp_slightly_negative_passes():
    """HP between 0 and -20 tolerated (end-of-game display edge)."""
    state = _valid_state()
    state.hp = -5
    assert validate(state).ok


def test_level_12_fails():
    state = _valid_state()
    state.level = 12
    assert not validate(state).ok


def test_board_larger_than_level_fails():
    state = _valid_state(level=3)
    state.board = [BoardUnit(champion="Jinx", star=1) for _ in range(5)]
    result = validate(state)
    assert not result.ok
    assert any(f.check_name == "board_size" for f in result.failures)


def test_xp_current_exceeds_needed_fails():
    state = _valid_state(xp_current=100, xp_needed=36)
    assert not validate(state).ok


def test_shop_with_3_slots_fails():
    state = _valid_state()
    state.shop = [ShopSlot(champion="Jinx", cost=2) for _ in range(3)]
    assert not validate(state).ok


def test_empty_shop_ok():
    """Carousel or god rounds have no shop — that's valid."""
    state = _valid_state()
    state.shop = []
    assert validate(state).ok


def test_four_items_on_unit_fails():
    state = _valid_state()
    state.board = [BoardUnit(
        champion="Jinx", star=2,
        items=["BF Sword", "Recurve Bow", "Tear", "Cloak"]
    )]
    assert not validate(state).ok


def test_four_augments_fails():
    state = _valid_state()
    state.augments = ["A", "B", "C", "D"]
    assert not validate(state).ok


def test_malformed_stage_fails():
    state = _valid_state(stage="three-two")
    assert not validate(state).ok


def test_multiple_failures_all_reported():
    state = _valid_state(gold=-5, hp=150, level=12)
    result = validate(state)
    assert not result.ok
    assert len(result.failures) >= 3  # all three bounds violations caught
```

## Acceptance gate

1. `pytest -q` shows 112/112 passing (99 + 13 new validation tests).
2. Manual test: modify a test fixture to have invalid state (e.g. `hp=-50`)
   and verify the overlay shows "verifying state…" instead of bad advice.
3. Revert manual test; confirm validation doesn't fire on valid states.
4. `git diff --stat` shows changes ONLY in `validators.py` (new),
   `assistant_overlay.py`, `tests/test_validators.py`, `STATE.md`.

## Commit message

```
Task 2: add state validation layer before scorer

- New validators.py with bounds + cross-field sanity checks
- PipelineWorker skips scorer on validation failure, shows safe UI message
- 13 new tests covering all validation paths

Tests: 99 → 112 passing.
```

## STATE.md entry

Standard format, include measured count and any notes.
