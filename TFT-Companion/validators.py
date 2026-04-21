"""validators.py — State validation before the v2 scorer.

Runs deterministic bounds and cross-field sanity checks on a
schemas.GameState before it reaches rules → comp_planner → recommender.

On failure: every check that fired is listed in ValidationResult.failures.
The caller (PipelineWorker) logs the bad state and shows a neutral UI
message instead of scoring corrupted data.

Why this matters:
    The worst failure mode for a live coach is NOT crashing — it's
    confidently wrong advice from corrupted state. "Your HP is -43,
    recommend rolling to 20g" must never happen. Validation is the
    cheapest insurance against bad OCR output reaching the scorer.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from schemas import GameState


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class ValidationFailure:
    """One validation check that fired."""
    check_name:   str
    field_path:   str
    actual_value: object
    expected:     str


@dataclass
class ValidationResult:
    ok:       bool
    failures: list[ValidationFailure] = field(default_factory=list)

    @classmethod
    def pass_(cls) -> "ValidationResult":
        return cls(ok=True)

    @classmethod
    def fail(cls, failures: list[ValidationFailure]) -> "ValidationResult":
        return cls(ok=False, failures=failures)


# ── Public entry point ─────────────────────────────────────────────────────────

def validate(state: GameState) -> ValidationResult:
    """Run all checks. Returns a combined result with every failure listed.

    Runs all checks even if the first one fires — callers get the full
    picture in a single call, which makes debugging bad OCR faster.
    """
    failures: list[ValidationFailure] = []
    _check_bounds(state, failures)
    _check_cross_field(state, failures)
    return ValidationResult(ok=not failures, failures=failures)


# ── Bounds checks ──────────────────────────────────────────────────────────────

def _check_bounds(state: GameState, failures: list[ValidationFailure]) -> None:
    if not (0 <= state.gold <= 999):
        failures.append(ValidationFailure(
            "gold_bounds", "gold", state.gold, "0 <= gold <= 999",
        ))

    if not (-20 <= state.hp <= 100):
        # -20 tolerates end-of-game display edge cases where HP shows slightly
        # negative before the loss screen resolves. More negative than that is
        # a broken OCR read.
        failures.append(ValidationFailure(
            "hp_bounds", "hp", state.hp, "-20 <= hp <= 100",
        ))

    if not (1 <= state.level <= 11):
        failures.append(ValidationFailure(
            "level_bounds", "level", state.level, "1 <= level <= 11",
        ))

    if state.xp_current < 0:
        failures.append(ValidationFailure(
            "xp_current_bounds", "xp_current", state.xp_current, "xp_current >= 0",
        ))

    if state.xp_needed < 0:
        failures.append(ValidationFailure(
            "xp_needed_bounds", "xp_needed", state.xp_needed, "xp_needed >= 0",
        ))

    # Stage must look like "N-M" with both parts in [1, 7]
    try:
        big_str, small_str = state.stage.split("-", 1)
        big_i, small_i = int(big_str), int(small_str)
        if not (1 <= big_i <= 7 and 1 <= small_i <= 7):
            failures.append(ValidationFailure(
                "stage_format", "stage", state.stage, "'N-M' where both parts in [1, 7]",
            ))
    except (ValueError, AttributeError):
        failures.append(ValidationFailure(
            "stage_parse", "stage", state.stage, "parseable 'N-M' stage string",
        ))


# ── Cross-field checks ─────────────────────────────────────────────────────────

def _check_cross_field(state: GameState, failures: list[ValidationFailure]) -> None:
    # XP numerator must not exceed denominator (when both are non-zero)
    if state.xp_needed > 0 and state.xp_current > state.xp_needed:
        failures.append(ValidationFailure(
            "xp_ordering",
            "xp_current vs xp_needed",
            (state.xp_current, state.xp_needed),
            "xp_current <= xp_needed",
        ))

    # Board size must not exceed level (TFT enforces this in-game)
    if len(state.board) > state.level:
        failures.append(ValidationFailure(
            "board_size",
            "len(board) vs level",
            (len(state.board), state.level),
            "len(board) <= level",
        ))

    # Shop must be exactly 5 slots or empty (carousel / god round has no shop)
    if state.shop and len(state.shop) != 5:
        failures.append(ValidationFailure(
            "shop_size", "len(shop)", len(state.shop),
            "5 slots or 0 (carousel / god round)",
        ))

    # Each unit on the board can hold at most 3 items
    for i, unit in enumerate(state.board):
        if len(unit.items) > 3:
            failures.append(ValidationFailure(
                "items_per_unit",
                f"board[{i}].items",
                unit.items,
                "<= 3 items per unit",
            ))

    # At most 3 augments across the whole game
    if len(state.augments) > 3:
        failures.append(ValidationFailure(
            "augment_count", "len(augments)", len(state.augments),
            "<= 3 augments total",
        ))
