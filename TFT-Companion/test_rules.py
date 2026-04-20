"""Unit tests for rules.py and scoring.py — deterministic layer.

Run: py test_rules.py
No API, no network. Pure logic checks.
"""

from __future__ import annotations

import sys

import rules
import scoring


def _state(**kw) -> dict:
    base = {
        "stage": None, "gold": None, "hp": None, "level": None,
        "xp": None, "streak": 0,
        "board": [], "bench": [], "shop": [],
        "active_traits": [], "augments": [],
    }
    base.update(kw)
    return base


def _fire_ids(state: dict) -> set:
    return {f.rule_id for f in rules.evaluate(state)}


FAILS: list[str] = []


def case(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


def test_rules():
    print("\n--- rules ---")

    # HP_URGENT at hp < 30
    ids = _fire_ids(_state(hp=28, gold=20, stage="4-1"))
    case("HP<30 triggers HP_URGENT", "HP_URGENT" in ids)

    # HP_CAUTION at 30 <= hp < 50
    ids = _fire_ids(_state(hp=40, stage="3-2"))
    case("HP 40 triggers HP_CAUTION not HP_URGENT",
         "HP_CAUTION" in ids and "HP_URGENT" not in ids)

    # HP healthy at 60
    ids = _fire_ids(_state(hp=60, stage="3-2"))
    case("HP 60 triggers neither HP rule",
         "HP_CAUTION" not in ids and "HP_URGENT" not in ids)

    # ECON_BELOW_INTEREST at gold < 10 without lose-streak
    ids = _fire_ids(_state(gold=5, streak=0))
    case("gold 5 streak 0 triggers ECON_BELOW_INTEREST",
         "ECON_BELOW_INTEREST" in ids)

    # ECON_BELOW_INTEREST suppressed on deep lose-streak
    ids = _fire_ids(_state(gold=5, streak=-4))
    case("gold 5 streak -4 suppresses ECON_BELOW_INTEREST",
         "ECON_BELOW_INTEREST" not in ids)

    # ECON_INTEREST_NEAR_THRESHOLD at 38g
    ids = _fire_ids(_state(gold=38))
    case("gold 38 triggers ECON_INTEREST_NEAR_THRESHOLD",
         "ECON_INTEREST_NEAR_THRESHOLD" in ids)

    # no threshold miss at 34g (>2 away from 40)
    ids = _fire_ids(_state(gold=34))
    case("gold 34 does NOT trigger threshold miss",
         "ECON_INTEREST_NEAR_THRESHOLD" not in ids)

    # streak bonuses
    case("streak -3 fires STREAK_LOSE_BONUS",
         "STREAK_LOSE_BONUS" in _fire_ids(_state(streak=-3)))
    case("streak 4 fires STREAK_WIN_BONUS",
         "STREAK_WIN_BONUS" in _fire_ids(_state(streak=4)))
    case("streak 0 fires neither streak rule",
         {"STREAK_WIN_BONUS", "STREAK_LOSE_BONUS"}.isdisjoint(_fire_ids(_state(streak=0))))

    # level pace behind
    ids = _fire_ids(_state(stage="4-2", level=6))
    case("stage 4-2 level 6 triggers LEVEL_PACE_BEHIND",
         "LEVEL_PACE_BEHIND" in ids)

    # level pace on track
    ids = _fire_ids(_state(stage="4-2", level=8))
    case("stage 4-2 level 8 does NOT trigger LEVEL_PACE_BEHIND",
         "LEVEL_PACE_BEHIND" not in ids)

    # SPIKE_ROUND_NEXT at 3-1
    ids = _fire_ids(_state(stage="3-1"))
    case("stage 3-1 triggers SPIKE_ROUND_NEXT",
         "SPIKE_ROUND_NEXT" in ids)

    # Realm of the Gods at 4-6
    ids = _fire_ids(_state(stage="4-6", hp=70, streak=0))
    case("stage 4-6 triggers REALM_OF_GODS_NEXT",
         "REALM_OF_GODS_NEXT" in ids)

    # trait uncommitted at 3-3 with 1 committed trait
    ids = _fire_ids(_state(stage="3-3",
                           active_traits=[{"trait": "Meeple", "count": 1}]))
    case("stage 3-3 with 1x singleton trait triggers TRAIT_UNCOMMITTED",
         "TRAIT_UNCOMMITTED" in ids)

    # trait committed
    ids = _fire_ids(_state(stage="3-3",
                           active_traits=[{"trait": "Meeple", "count": 3},
                                          {"trait": "Shepherd", "count": 3}]))
    case("stage 3-3 with 2x 3-count traits does NOT trigger TRAIT_UNCOMMITTED",
         "TRAIT_UNCOMMITTED" not in ids)

    # severity ordering: HP_URGENT should come first
    fires = rules.evaluate(_state(hp=15, gold=3, stage="4-2", level=6, streak=-2))
    case("HP_URGENT is top of severity-sorted fires",
         fires and fires[0].rule_id == "HP_URGENT")


def test_scoring():
    print("\n--- scoring ---")

    empty = scoring.compute_board_strength(_state(stage="3-2"))
    case("empty board score is 0.0", empty["score"] == 0.0)
    case("empty board confidence is HIGH", empty["confidence"] == "HIGH")

    all_unknown = scoring.compute_board_strength(_state(
        stage="3-2",
        board=[{"champion": "Unknown", "star": 1, "items": []}] * 6,
    ))
    case("all-unknown board flagged LOW confidence",
         all_unknown["confidence"] == "LOW")
    case("all-unknown board has unknown_units == total_units",
         all_unknown["unknown_units"] == all_unknown["total_units"])

    # A known champion must produce a non-zero score if it exists in game_assets.
    # Use a common one likely to exist; fall back if not.
    import game_assets
    known_champ = next(
        (name for name, data in game_assets.CHAMPIONS.items() if data.get("cost")),
        None,
    )
    if known_champ:
        s = scoring.compute_board_strength(_state(
            stage="3-2",
            board=[{"champion": known_champ, "star": 2, "items": ["Bloodthirster"]}],
        ))
        case(f"known champ {known_champ} 2* produces >0 score", s["score"] > 0)
        case(f"known champ sets MEDIUM/HIGH confidence",
             s["confidence"] in ("MEDIUM", "HIGH"))

    # trait multiplier applies
    with_traits = scoring.compute_board_strength(_state(
        stage="3-2",
        board=[{"champion": "Unknown", "star": 2, "items": []}],
        active_traits=[{"trait": "Meeple", "count": 3},
                       {"trait": "Shepherd", "count": 3},
                       {"trait": "Arbiter", "count": 2}],
    ))
    case("trait_mult > 1 when traits active", with_traits["trait_mult"] > 1.0)


def main() -> int:
    print("=== rules + scoring unit tests ===")
    test_rules()
    test_scoring()
    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)}")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
