"""Deterministic rule engine.

Each Rule is a pure function (state) -> Optional[Fire]. Fires carry:
    rule_id, severity (0.0–1.0), action tag, human-readable message, data.

Rules are the CHEAP layer: zero API cost, sub-millisecond evaluation,
testable, auditable. They catch the obvious calls ("you're below interest
threshold", "HP critical") before the LLM reasoning layer even looks at
the state.

Rules are encoded from `data/tft_set17_rules.md` — the programmable ones.
Non-programmable rules (positioning, comp pivots) belong in the LLM layer.

Severity convention:
    1.0 = critical, needs action this round
    0.7 = important, act this phase
    0.4 = notable, worth a heads-up
    0.1 = info only
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Callable, Optional


@dataclass
class Fire:
    rule_id: str
    severity: float
    action: str           # short tag: "ROLL_DOWN", "HOLD_ECON", "LEVEL_UP", "INFO", ...
    message: str          # human-readable
    data: dict = None     # numeric context

    def to_dict(self) -> dict:
        return asdict(self)


# --- helpers ---

_STAGE_RE = re.compile(r"^(\d)-(\d)$")


def _parse_stage(stage: Optional[str]) -> Optional[tuple[int, int]]:
    if not stage:
        return None
    m = _STAGE_RE.match(stage.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _stage_key(stage: Optional[str]) -> float:
    """Stage as monotonic float: 3-2 → 3.2, 4-7 → 4.7."""
    p = _parse_stage(stage)
    return p[0] + p[1] / 10.0 if p else 0.0


# Expected level for stage on a balanced (not streaking hard) pace.
# Derived from rule 11 in tft_set17_rules.md.
EXPECTED_LEVEL = [
    (2.0, 4), (2.5, 5), (3.1, 6), (3.5, 7), (4.2, 7), (4.5, 8), (5.1, 8), (5.5, 9),
]


def expected_level(stage: Optional[str]) -> Optional[int]:
    k = _stage_key(stage)
    if k == 0.0:
        return None
    last = None
    for threshold, lvl in EXPECTED_LEVEL:
        if k >= threshold:
            last = lvl
    return last


# --- rules ---


def _econ_below_interest(state) -> Optional[Fire]:
    """Gold below 10 when not on a deep lose-streak = leaking interest."""
    gold = state.get("gold")
    streak = state.get("streak") or 0
    if gold is None or gold >= 10:
        return None
    if streak <= -3:  # deep lose-streak — acceptable to dip
        return None
    return Fire(
        rule_id="ECON_BELOW_INTEREST",
        severity=0.7,
        action="HOLD_GOLD",
        message=f"Gold {gold} < 10. No interest this round. Avoid dropping below 10 unless on deep lose-streak.",
        data={"gold": gold, "streak": streak},
    )


def _econ_interest_threshold_miss(state) -> Optional[Fire]:
    """Flag when gold is just below an interest threshold (e.g. 38 → roll 1 less to hit 40)."""
    gold = state.get("gold")
    if gold is None or gold >= 50:
        return None
    thresholds = [10, 20, 30, 40, 50]
    nearest_below = max((t for t in thresholds if gold >= t), default=0)
    nearest_above = min((t for t in thresholds if gold < t), default=50)
    if nearest_above - gold <= 2:
        return Fire(
            rule_id="ECON_INTEREST_NEAR_THRESHOLD",
            severity=0.4,
            action="HOLD_GOLD",
            message=f"Gold {gold}, only {nearest_above - gold}g to next interest tier ({nearest_above}g).",
            data={"gold": gold, "next_threshold": nearest_above},
        )
    return None


def _lose_streak_bonus(state) -> Optional[Fire]:
    streak = state.get("streak") or 0
    if streak > -2:
        return None
    bonus = 1 if streak >= -4 else (2 if streak == -5 else 3)
    return Fire(
        rule_id="STREAK_LOSE_BONUS",
        severity=0.1,
        action="INFO",
        message=f"Lose-streak {abs(streak)} → +{bonus}g/round bonus. Extend until HP drops ~40 or you can stabilize.",
        data={"streak": streak, "bonus_gold": bonus},
    )


def _win_streak_bonus(state) -> Optional[Fire]:
    streak = state.get("streak") or 0
    if streak < 2:
        return None
    bonus = 1 if streak <= 4 else (2 if streak == 5 else 3)
    return Fire(
        rule_id="STREAK_WIN_BONUS",
        severity=0.1,
        action="INFO",
        message=f"Win-streak {streak} → +{bonus}g/round. Push board strength to extend.",
        data={"streak": streak, "bonus_gold": bonus},
    )


def _hp_urgent(state) -> Optional[Fire]:
    hp = state.get("hp")
    if hp is None or hp >= 30:
        return None
    return Fire(
        rule_id="HP_URGENT",
        severity=1.0,
        action="ROLL_DOWN",
        message=f"HP {hp} — critical. Spend gold on board strength NOW; tempo > economy.",
        data={"hp": hp},
    )


def _hp_caution(state) -> Optional[Fire]:
    hp = state.get("hp")
    if hp is None or hp >= 50 or hp < 30:
        return None
    return Fire(
        rule_id="HP_CAUTION",
        severity=0.4,
        action="BOARD_CHECK",
        message=f"HP {hp} — verify board can win rounds. Plan a stabilization roll within 1–2 stages.",
        data={"hp": hp},
    )


def _level_pace_behind(state) -> Optional[Fire]:
    level = state.get("level")
    stage = state.get("stage")
    exp = expected_level(stage)
    if level is None or exp is None or level >= exp:
        return None
    return Fire(
        rule_id="LEVEL_PACE_BEHIND",
        severity=0.7 if exp - level >= 2 else 0.4,
        action="LEVEL_UP",
        message=f"Level {level} at {stage} — expected ~{exp}. Buy XP unless holding for a specific reroll spike.",
        data={"level": level, "stage": stage, "expected": exp},
    )


def _spike_round_next(state) -> Optional[Fire]:
    stage = state.get("stage")
    p = _parse_stage(stage)
    if not p:
        return None
    # Critical spike rounds (per rule 10): 3-2, 3-5, 4-1, 4-2, 4-5, 5-1
    spike_next = {
        (3, 1): "3-2", (3, 4): "3-5", (3, 7): "4-1",
        (4, 1): "4-2", (4, 4): "4-5", (4, 7): "5-1",
    }.get(p)
    if not spike_next:
        return None
    return Fire(
        rule_id="SPIKE_ROUND_NEXT",
        severity=0.4,
        action="PLAN_ROLL",
        message=f"Next round is {spike_next} — classic spike round. Plan your roll/level decision now.",
        data={"current": stage, "spike": spike_next},
    )


def _realm_of_gods_approaching(state) -> Optional[Fire]:
    """4-7 is the Armory / god-boon choice round."""
    stage = state.get("stage")
    p = _parse_stage(stage)
    if p != (4, 6):
        return None
    hp = state.get("hp") or 100
    streak = state.get("streak") or 0
    if hp < 40 or streak <= -3:
        pick = "loss-streak / Pengu 3-cost offer (Evelynn) — stabilize"
    elif streak >= 3:
        pick = "win-streak god (Soraka HP extend, Evelynn aggressive)"
    else:
        pick = "aligned god for your comp; Kayle if you have a completed item to Radiant"
    return Fire(
        rule_id="REALM_OF_GODS_NEXT",
        severity=0.7,
        action="PLAN_GOD_PICK",
        message=f"Next round 4-7 (Realm of the Gods). Given HP {hp} and streak {streak}, lean: {pick}.",
        data={"hp": hp, "streak": streak},
    )


def _trait_uncommitted(state) -> Optional[Fire]:
    """Stage ≥ 3-2 and fewer than 2 active non-single traits = board likely uncommitted."""
    p = _parse_stage(state.get("stage"))
    if not p or _stage_key(state.get("stage")) < 3.2:
        return None
    traits = state.get("active_traits") or []
    real_traits = [t for t in traits if (t.get("count") or 0) >= 2]
    if len(real_traits) >= 2:
        return None
    return Fire(
        rule_id="TRAIT_UNCOMMITTED",
        severity=0.4,
        action="COMMIT_DIRECTION",
        message=f"Only {len(real_traits)} trait(s) with 2+ units at {state.get('stage')}. Commit a direction — random boards fall off.",
        data={"active_traits": traits},
    )


ALL_RULES: list[Callable] = [
    _econ_below_interest,
    _econ_interest_threshold_miss,
    _lose_streak_bonus,
    _win_streak_bonus,
    _hp_urgent,
    _hp_caution,
    _level_pace_behind,
    _spike_round_next,
    _realm_of_gods_approaching,
    _trait_uncommitted,
]


def evaluate(state_dict: dict) -> list[Fire]:
    """Run every rule against the state. Return list of fires, highest severity first."""
    fires: list[Fire] = []
    for rule in ALL_RULES:
        try:
            f = rule(state_dict)
            if f:
                fires.append(f)
        except Exception as e:
            # Rules must never crash the pipeline. Log to DB eventually; for now skip.
            pass
    fires.sort(key=lambda f: f.severity, reverse=True)
    return fires
