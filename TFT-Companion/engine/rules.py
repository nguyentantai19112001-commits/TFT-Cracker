"""rules.py — Augie v2 rule engine (Phase 3).

40 deterministic rules. Each function: (state, econ_mod, pool_tracker, km) -> Fire | None.
evaluate() runs all rules, swallowing exceptions so one bad rule can't crash the pipeline.
Numbers come from knowledge/ YAML — no hardcoded constants except severity tiers.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable, Optional

# game_assets is in the parent directory (TFT-Companion/).
_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
import game_assets

from schemas import Fire, GameState, TraitActivation

_COST_BY_CHAMP: dict[str, int] = {
    name: info["cost"] for name, info in game_assets.CHAMPIONS.items()
}

# ──────────────────────────────────────────────────────────────────────────────
# Stage helpers
# ──────────────────────────────────────────────────────────────────────────────

_STAGE_RE = re.compile(r"^(\d+)-(\d+)$")


def _parse_stage(stage: Optional[str]) -> Optional[tuple[int, int]]:
    if not stage:
        return None
    m = _STAGE_RE.match(stage.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _stage_key(stage: Optional[str]) -> float:
    p = _parse_stage(stage)
    return p[0] + p[1] / 10.0 if p else 0.0


# Expected level by stage (balanced pace).
_EXPECTED_LEVEL_TABLE = [
    (2.0, 4), (2.5, 5), (3.1, 6), (3.5, 7), (4.2, 7), (4.5, 8), (5.1, 8), (5.5, 9),
]


def _expected_level(stage: Optional[str]) -> Optional[int]:
    k = _stage_key(stage)
    if k == 0.0:
        return None
    last = None
    for threshold, lvl in _EXPECTED_LEVEL_TABLE:
        if k >= threshold:
            last = lvl
    return last


# ──────────────────────────────────────────────────────────────────────────────
# Primary-target heuristic (Phase 3 — no comp_planner yet)
# ──────────────────────────────────────────────────────────────────────────────

def _infer_primary_target(state: GameState) -> Optional[str]:
    candidates = [u for u in state.board if u.star < 2]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda u: _COST_BY_CHAMP.get(u.champion, 0) * (1 + 0.5 * len(u.items)),
    ).champion


# ──────────────────────────────────────────────────────────────────────────────
# Economy rules
# ──────────────────────────────────────────────────────────────────────────────

def _econ_below_interest(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.gold >= 10:
        return None
    if state.streak <= -3:
        return None
    return Fire(
        rule_id="ECON_BELOW_INTEREST", severity=0.7, action="HOLD_ECON",
        message=f"Gold {state.gold} < 10. Losing interest this round. Don't drop below 10 unless deep loss-streak.",
        data={"gold": state.gold, "streak": state.streak},
    )


def _econ_interest_near_threshold(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.gold >= 50:
        return None
    thresholds = [10, 20, 30, 40, 50]
    nearest_above = min((t for t in thresholds if state.gold < t), default=50)
    gap = nearest_above - state.gold
    if gap > 2:
        return None
    return Fire(
        rule_id="ECON_INTEREST_NEAR_THRESHOLD", severity=0.4, action="HOLD_ECON",
        message=f"Gold {state.gold} — only {gap}g to next interest tier ({nearest_above}g). Hold {gap}g.",
        data={"gold": state.gold, "next_threshold": nearest_above, "gap": gap},
    )


def _econ_over_cap_waste(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.gold < 55:
        return None
    if _stage_key(state.stage) < 4.1:
        return None
    return Fire(
        rule_id="ECON_OVER_CAP_WASTE", severity=0.7, action="SPEND",
        message=f"Gold {state.gold} ≥ 55 past stage 4-1. Interest capped at 5. Spend on board now.",
        data={"gold": state.gold, "stage": state.stage},
    )


def _econ_round_loss_momentum(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """Warn when on a loss streak but board may accidentally win (breaking streak)."""
    if state.streak > -3:
        return None
    exp = _expected_level(state.stage)
    if exp is None:
        return None
    # Proxy for "board exceeds expectation": more units than level suggests
    if len(state.board) <= exp:
        return None
    return Fire(
        rule_id="ECON_ROUND_LOSS_MOMENTUM", severity=0.7, action="HOLD_BOARD",
        message=f"Loss streak {abs(state.streak)} active. Board may be too strong to lose — "
                "consider whether to extend streak vs stabilize.",
        data={"streak": state.streak, "board_count": len(state.board)},
    )


def _econ_win_streak_maintain(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """Warn when on a win streak but board may accidentally lose (breaking streak)."""
    if state.streak < 3:
        return None
    exp = _expected_level(state.stage)
    if exp is None:
        return None
    if len(state.board) >= exp - 1:
        return None
    return Fire(
        rule_id="ECON_WIN_STREAK_MAINTAIN", severity=0.5, action="PUSH_BOARD",
        message=f"Win streak {state.streak} active. Board looks thin — push units to maintain streak.",
        data={"streak": state.streak, "board_count": len(state.board)},
    )


def _econ_interest_cap_hold(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """INFO: at 50g, interest is maxed — any spend is gold-neutral on interest."""
    if state.gold < 50 or state.gold > 54:
        return None
    return Fire(
        rule_id="ECON_INTEREST_CAP_HOLD", severity=0.1, action="INFO",
        message=f"Gold {state.gold} — interest capped at 5g. Safe to spend down to 50g.",
        data={"gold": state.gold},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Leveling rules
# ──────────────────────────────────────────────────────────────────────────────

def _level_pace_behind(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    exp = _expected_level(state.stage)
    if exp is None or state.level >= exp:
        return None
    severity = 0.7 if exp - state.level >= 2 else 0.4
    return Fire(
        rule_id="LEVEL_PACE_BEHIND", severity=severity, action="LEVEL_UP",
        message=f"Level {state.level} at {state.stage} — expected ~{exp}. Buy XP unless holding for reroll spike.",
        data={"level": state.level, "stage": state.stage, "expected": exp},
    )


def _level_pace_ahead(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    exp = _expected_level(state.stage)
    if exp is None or state.level <= exp + 1:
        return None
    return Fire(
        rule_id="LEVEL_PACE_AHEAD", severity=0.4, action="HOLD_ECON",
        message=f"Level {state.level} at {state.stage} — ahead of pace ({exp}). Good, but watch econ.",
        data={"level": state.level, "stage": state.stage, "expected": exp},
    )


def _level_spike_window(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """1 XP buy away from leveling AND next round is a spike."""
    try:
        core = km.load_core()
        set_ = km.load_set(state.set_id)
        xp_needed = km.xp_for_next_level(core, state.level) - state.xp_current
        if xp_needed > core.xp_per_buy:
            return None
        spike = km.spike_round_next(set_, state.stage)
        if spike is None:
            return None
    except Exception:
        return None
    return Fire(
        rule_id="LEVEL_SPIKE_WINDOW", severity=0.5, action="LEVEL_UP",
        message=f"One XP buy levels you up, and next round is {spike['stage']} spike. Level now.",
        data={"xp_remaining": xp_needed, "spike_round": spike["stage"]},
    )


def _level_ev_positive(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    target = _infer_primary_target(state)
    if target is None or pt is None or econ_mod is None:
        return None
    try:
        pool_state = pt.to_pool_state(target)
        if pool_state is None:
            return None
        set_ = km.load_set(state.set_id)
        core = km.load_core()
        decision = econ_mod.level_vs_roll(state, target, pool_state, core, set_)
        if decision.recommended != "LEVEL" or decision.p_hit_delta <= 0.15:
            return None
    except Exception:
        return None
    return Fire(
        rule_id="LEVEL_EV_POSITIVE", severity=0.6, action="LEVEL_UP",
        message=f"Leveling raises P(2-copy {target}) by {decision.p_hit_delta:.0%}. Level first.",
        data={"target": target, "p_hit_delta": decision.p_hit_delta},
    )


def _level_ev_negative(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    target = _infer_primary_target(state)
    if target is None or pt is None or econ_mod is None:
        return None
    try:
        pool_state = pt.to_pool_state(target)
        if pool_state is None:
            return None
        set_ = km.load_set(state.set_id)
        core = km.load_core()
        decision = econ_mod.level_vs_roll(state, target, pool_state, core, set_)
        if decision.gold_to_level <= 0.4 * state.gold:
            return None
        if decision.p_hit_delta >= 0.05:
            return None
    except Exception:
        return None
    return Fire(
        rule_id="LEVEL_EV_NEGATIVE", severity=0.5, action="HOLD_ECON",
        message=f"Leveling costs {decision.gold_to_level}g for only {decision.p_hit_delta:.0%} P(hit) gain. Hold.",
        data={"gold_to_level": decision.gold_to_level, "p_hit_delta": decision.p_hit_delta},
    )


def _level_near_cap(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.level < 10:
        return None
    return Fire(
        rule_id="LEVEL_NEAR_CAP", severity=0.1, action="INFO",
        message=f"Level {state.level} — near cap. Focus spending on rolls and board.",
        data={"level": state.level},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Rolling rules
# ──────────────────────────────────────────────────────────────────────────────

def _roll_ev_negative(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    target = _infer_primary_target(state)
    if target is None or pt is None or econ_mod is None or state.gold < 10:
        return None
    try:
        pool_state = pt.to_pool_state(target)
        if pool_state is None:
            return None
        set_ = km.load_set(state.set_id)
        r = econ_mod.analyze_roll(target, state.level, state.gold, pool_state, set_)
        if r.p_hit_at_least_2 >= 0.25:
            return None
    except Exception:
        return None
    return Fire(
        rule_id="ROLL_EV_NEGATIVE", severity=0.8, action="HOLD_ECON",
        message=f"Rolling for {target} at L{state.level} with {state.gold}g → {r.p_hit_at_least_2:.0%} P(2-copy). "
                "Odds too low. Hold or level first.",
        data={"target": target, "p_hit_at_least_2": r.p_hit_at_least_2},
    )


def _roll_ev_strong(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    target = _infer_primary_target(state)
    if target is None or pt is None or econ_mod is None or state.gold < 10:
        return None
    try:
        pool_state = pt.to_pool_state(target)
        if pool_state is None:
            return None
        set_ = km.load_set(state.set_id)
        r = econ_mod.analyze_roll(target, state.level, state.gold, pool_state, set_)
        if r.p_hit_at_least_2 <= 0.75:
            return None
    except Exception:
        return None
    return Fire(
        rule_id="ROLL_EV_STRONG", severity=0.4, action="ROLL_TO",
        message=f"Rolling for {target} at L{state.level} with {state.gold}g → {r.p_hit_at_least_2:.0%} P(2-copy). Green light.",
        data={"target": target, "p_hit_at_least_2": r.p_hit_at_least_2},
    )


def _roll_hp_panic(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.hp >= 30 or state.gold < 10:
        return None
    return Fire(
        rule_id="ROLL_HP_PANIC", severity=1.0, action="ROLL_TO",
        message=f"HP {state.hp} critical and {state.gold}g available. Roll for board strength NOW.",
        data={"hp": state.hp, "gold": state.gold},
    )


def _roll_not_on_level(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """Target champion doesn't appear in shop at current level."""
    target = _infer_primary_target(state)
    if target is None:
        return None
    cost = _COST_BY_CHAMP.get(target)
    if cost is None:
        return None
    try:
        set_ = km.load_set(state.set_id)
        odds = km.shop_odds(set_, state.level)
        if odds[cost - 1] > 0:
            return None
    except Exception:
        return None
    return Fire(
        rule_id="ROLL_NOT_ON_LEVEL", severity=1.0, action="LEVEL_UP",
        message=f"{target} (cost {cost}) has 0% shop odds at L{state.level}. Level up before rolling.",
        data={"target": target, "cost": cost, "level": state.level},
    )


def _roll_odds_favored_next_level(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    target = _infer_primary_target(state)
    if target is None or pt is None or econ_mod is None or state.gold < 10:
        return None
    try:
        pool_state = pt.to_pool_state(target)
        if pool_state is None:
            return None
        set_ = km.load_set(state.set_id)
        r_now = econ_mod.analyze_roll(target, state.level, state.gold, pool_state, set_)
        r_next = econ_mod.analyze_roll(target, state.level + 1, state.gold, pool_state, set_)
        if r_now.p_hit_at_least_2 == 0 or r_next.p_hit_at_least_2 <= 2 * r_now.p_hit_at_least_2:
            return None
    except Exception:
        return None
    return Fire(
        rule_id="ROLL_ODDS_FAVORED_NEXT_LEVEL", severity=0.5, action="LEVEL_UP",
        message=f"P(2-copy {target}) doubles at L{state.level + 1} ({r_now.p_hit_at_least_2:.0%} → {r_next.p_hit_at_least_2:.0%}). "
                "Level first.",
        data={"target": target, "p_now": r_now.p_hit_at_least_2, "p_next": r_next.p_hit_at_least_2},
    )


def _roll_poverty_trap(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.gold >= 4:
        return None
    return Fire(
        rule_id="ROLL_POVERTY_TRAP", severity=0.6, action="HOLD_ECON",
        message=f"Gold {state.gold} — can't afford a reroll (costs 2g). Build to at least 4g before considering action.",
        data={"gold": state.gold},
    )


# ──────────────────────────────────────────────────────────────────────────────
# HP rules
# ──────────────────────────────────────────────────────────────────────────────

def _hp_urgent(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.hp >= 30:
        return None
    return Fire(
        rule_id="HP_URGENT", severity=1.0, action="ROLL_TO",
        message=f"HP {state.hp} — critical. Spend gold on board strength NOW; tempo > economy.",
        data={"hp": state.hp},
    )


def _hp_caution(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.hp >= 50 or state.hp < 30:
        return None
    return Fire(
        rule_id="HP_CAUTION", severity=0.4, action="BOARD_CHECK",
        message=f"HP {state.hp} — verify board can win rounds. Plan a stabilization roll within 1-2 stages.",
        data={"hp": state.hp},
    )


def _hp_danger_zone(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.hp >= 40 or abs(state.streak) >= 3:
        return None
    return Fire(
        rule_id="HP_DANGER_ZONE", severity=0.7, action="ROLL_TO",
        message=f"HP {state.hp} < 40 with no streak cushion. Prioritize board over econ.",
        data={"hp": state.hp, "streak": state.streak},
    )


def _hp_lose_streak_cap(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.streak > -3 or state.hp >= 35:
        return None
    return Fire(
        rule_id="HP_LOSE_STREAK_CAP", severity=0.8, action="ROLL_TO",
        message=f"HP {state.hp} with {abs(state.streak)}-game loss streak. Too low to keep streaking — stabilize now.",
        data={"hp": state.hp, "streak": state.streak},
    )


def _hp_comfortable(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.hp <= 85:
        return None
    return Fire(
        rule_id="HP_COMFORTABLE", severity=0.1, action="INFO",
        message=f"HP {state.hp} — comfortable. Econ and tempo decisions take priority over board insurance.",
        data={"hp": state.hp},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Streak rules
# ──────────────────────────────────────────────────────────────────────────────

def _streak_lose_bonus(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.streak > -2:
        return None
    n = abs(state.streak)
    bonus = 1 if n <= 4 else (2 if n == 5 else 3)
    return Fire(
        rule_id="STREAK_LOSE_BONUS", severity=0.1, action="INFO",
        message=f"Loss streak {n} → +{bonus}g/round bonus. Extend if HP allows.",
        data={"streak": state.streak, "bonus_gold": bonus},
    )


def _streak_win_bonus(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.streak < 2:
        return None
    bonus = 1 if state.streak <= 4 else (2 if state.streak == 5 else 3)
    return Fire(
        rule_id="STREAK_WIN_BONUS", severity=0.1, action="INFO",
        message=f"Win streak {state.streak} → +{bonus}g/round. Push board to extend.",
        data={"streak": state.streak, "bonus_gold": bonus},
    )


def _streak_lose_cap_approaching(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.streak != -5 or state.hp <= 35:
        return None
    return Fire(
        rule_id="STREAK_LOSE_CAP_APPROACHING", severity=0.5, action="PLAN_STAB",
        message="Loss streak at -5 (max bonus tier). Plan stabilization within 2 rounds before HP drops below 35.",
        data={"streak": state.streak, "hp": state.hp},
    )


def _streak_win_cap_approaching(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.streak != 5:
        return None
    return Fire(
        rule_id="STREAK_WIN_CAP_APPROACHING", severity=0.4, action="PUSH_BOARD",
        message="Win streak at 5 (max bonus tier). Push board — won't gain more streak gold, aim for winout.",
        data={"streak": state.streak},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Trait / comp rules
# ──────────────────────────────────────────────────────────────────────────────

def _trait_uncommitted(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if _stage_key(state.stage) < 3.2:
        return None
    real_traits = [t for t in state.active_traits if t.count >= 2]
    if len(real_traits) >= 2:
        return None
    return Fire(
        rule_id="TRAIT_UNCOMMITTED", severity=0.4, action="COMMIT_DIRECTION",
        message=f"Only {len(real_traits)} trait(s) with 2+ units at {state.stage}. Commit a direction.",
        data={"active_traits": len(state.active_traits)},
    )


def _trait_vertical_over_invest(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """3+ copies of same champion without trait payoff."""
    champ_counts: dict[str, int] = {}
    for unit in list(state.board) + list(state.bench):
        champ_counts[unit.champion] = champ_counts.get(unit.champion, 0) + 1
    active_trait_names = {t.trait for t in state.active_traits if t.count >= 2}
    for champ, count in champ_counts.items():
        if count < 3:
            continue
        # Check if this champion contributes to any active trait
        champ_in_trait = any(
            champ in t.trait or t.trait in champ  # rough proxy
            for t in state.active_traits if t.count >= 2
        )
        if not champ_in_trait:
            return Fire(
                rule_id="TRAIT_VERTICAL_OVER_INVEST", severity=0.4, action="PIVOT_COMP",
                message=f"Holding {count}x {champ} but it's not driving any active trait. Consider pivoting.",
                data={"champion": champ, "count": count},
            )
    return None


def _comp_unreachable(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """Stub — requires comp_planner (Phase 4). Always silent."""
    return None


def _comp_item_fit_broken(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """Stub — requires comp_planner (Phase 4). Always silent."""
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Item rules
# ──────────────────────────────────────────────────────────────────────────────

def _item_slam_mandate(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if _stage_key(state.stage) < 3.2:
        return None
    n = len(state.item_components_on_bench)
    if n < 3:
        return None
    return Fire(
        rule_id="ITEM_SLAM_MANDATE", severity=0.5, action="SLAM_ITEM",
        message=f"{n} unbuilt components on bench at {state.stage}. Slam items — components are worth more on board.",
        data={"components": n, "stage": state.stage},
    )


def _item_wrong_carrier(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    """Completed item on a <3-cost unit that isn't in an active trait breakpoint."""
    active_trait_names = {t.trait for t in state.active_traits if t.count >= 2}
    for unit in state.board:
        if not unit.items:
            continue
        cost = _COST_BY_CHAMP.get(unit.champion, 3)
        if cost >= 3:
            continue
        # Low-cost unit with items — check if it's driving a trait
        if not any(t in unit.champion for t in active_trait_names):
            return Fire(
                rule_id="ITEM_WRONG_CARRIER", severity=0.3, action="ITEM_REPLAN",
                message=f"{unit.champion} (cost {cost}) is holding items but isn't a key trait unit. Replan item carriers.",
                data={"champion": unit.champion, "cost": cost, "items": unit.items},
            )
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Stage / mechanic rules
# ──────────────────────────────────────────────────────────────────────────────

def _spike_round_next(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    p = _parse_stage(state.stage)
    if not p:
        return None
    spike_next = {
        (3, 1): "3-2", (3, 4): "3-5", (3, 7): "4-1",
        (4, 1): "4-2", (4, 4): "4-5", (4, 7): "5-1",
    }.get(p)
    if not spike_next:
        return None
    return Fire(
        rule_id="SPIKE_ROUND_NEXT", severity=0.4, action="PLAN_ROLL",
        message=f"Next round is {spike_next} — classic spike. Plan your roll/level decision now.",
        data={"current": state.stage, "spike": spike_next},
    )


def _realm_of_gods_approaching(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if _parse_stage(state.stage) != (4, 6):
        return None
    if state.hp < 40 or state.streak <= -3:
        pick = "stabilization pick (Thresh or cheap Evelynn offer)"
    elif state.streak >= 3:
        pick = "win-streak god (Soraka or Ekko)"
    elif state.completed_items_on_bench:
        pick = "Kayle — you have a completed item to Radiant"
    else:
        pick = "comp-aligned: Ahri (neutral), Varus (AD board), Aurelion Sol (AP board), Yasuo (Challenger/melee)"
    return Fire(
        rule_id="REALM_OF_GODS_NEXT", severity=0.7, action="PLAN_GOD_PICK",
        message=f"Next round 4-7 (Realm of the Gods). Lean: {pick}.",
        data={"hp": state.hp, "streak": state.streak},
    )


def _stage_3_1_decision_point(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.stage != "3-1":
        return None
    return Fire(
        rule_id="STAGE_3_1_DECISION_POINT", severity=0.3, action="INFO",
        message="Stage 3-1: key inflection — decide now whether to roll for 3-star or save for 4-1 level spike.",
        data={"stage": state.stage, "gold": state.gold, "level": state.level},
    )


def _stage_4_2_fastspike(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if state.stage != "4-2" or state.level < 8:
        return None
    return Fire(
        rule_id="STAGE_4_2_FASTSPIKE", severity=0.4, action="PLAN_ROLL",
        message=f"Stage 4-2 at L{state.level} — fast-8 spike window. Roll if you have 30-50g and a target.",
        data={"stage": state.stage, "level": state.level, "gold": state.gold},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Board rules
# ──────────────────────────────────────────────────────────────────────────────

def _board_weak_for_stage(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if _stage_key(state.stage) < 3.2:
        return None
    if len(state.board) >= state.level - 2:
        return None
    return Fire(
        rule_id="BOARD_WEAK_FOR_STAGE", severity=0.6, action="ROLL_TO",
        message=f"Only {len(state.board)} units on board at {state.stage} (L{state.level}). Board is under-strength.",
        data={"board_count": len(state.board), "level": state.level, "stage": state.stage},
    )


def _board_under_cap(state: GameState, econ_mod, pt, km) -> Optional[Fire]:
    if len(state.board) >= state.level:
        return None
    return Fire(
        rule_id="BOARD_UNDER_CAP", severity=0.3, action="BUY",
        message=f"Board has {len(state.board)} units but L{state.level} allows {state.level}. Buy units to fill cap.",
        data={"board_count": len(state.board), "level": state.level},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Rule registry + evaluate
# ──────────────────────────────────────────────────────────────────────────────

ALL_RULES: list[Callable] = [
    # Economy (6)
    _econ_below_interest,
    _econ_interest_near_threshold,
    _econ_over_cap_waste,
    _econ_round_loss_momentum,
    _econ_win_streak_maintain,
    _econ_interest_cap_hold,
    # Leveling (6)
    _level_pace_behind,
    _level_pace_ahead,
    _level_spike_window,
    _level_ev_positive,
    _level_ev_negative,
    _level_near_cap,
    # Rolling (7)
    _roll_ev_negative,
    _roll_ev_strong,
    _roll_hp_panic,
    _roll_not_on_level,
    _roll_odds_favored_next_level,
    _roll_poverty_trap,
    # HP (5)
    _hp_urgent,
    _hp_caution,
    _hp_danger_zone,
    _hp_lose_streak_cap,
    _hp_comfortable,
    # Streak (4)
    _streak_lose_bonus,
    _streak_win_bonus,
    _streak_lose_cap_approaching,
    _streak_win_cap_approaching,
    # Trait / comp (4)
    _trait_uncommitted,
    _trait_vertical_over_invest,
    _comp_unreachable,
    _comp_item_fit_broken,
    # Item (2)
    _item_slam_mandate,
    _item_wrong_carrier,
    # Stage / mechanic (4)
    _spike_round_next,
    _realm_of_gods_approaching,
    _stage_3_1_decision_point,
    _stage_4_2_fastspike,
    # Board (2)
    _board_weak_for_stage,
    _board_under_cap,
]


def evaluate(
    state: GameState,
    econ_mod,
    pool_tracker,
    knowledge_mod,
) -> list[Fire]:
    """Run every rule. Returns fires sorted by severity descending."""
    fires: list[Fire] = []
    for rule in ALL_RULES:
        try:
            f = rule(state, econ_mod, pool_tracker, knowledge_mod)
            if f:
                fires.append(f)
        except Exception:
            pass
    fires.sort(key=lambda f: f.severity, reverse=True)
    return fires
