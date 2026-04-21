import pytest
from econ import analyze_roll, level_vs_roll, interest_projection, expected_gold_to_first_hit
from schemas import PoolState, GameState
from knowledge import load_core, load_set

SET17 = load_set("17")
CORE = load_core()

# --- analyze_roll ---

def test_uncontested_4cost_50g_l8():
    """50g at L8 for uncontested 4-cost — full pool (10×13=130 total)."""
    pool = PoolState(copies_of_target_remaining=10, same_cost_copies_remaining=130, distinct_same_cost=13)
    r = analyze_roll("Jinx", level=8, gold=50, pool=pool, set_=SET17)
    assert r.p_hit_at_least_2 > 0.60  # Markov gives ~0.64 for this config
    assert r.p_hit_at_least_2 < 0.75
    assert r.p_hit_at_least_1 > r.p_hit_at_least_2

def test_contested_drops_p_hit():
    """Same roll, but 3 opponents each hold 2 Jinx. k drops 10 → 4. R_T = 130 - 6 = 124."""
    pool = PoolState(copies_of_target_remaining=4, same_cost_copies_remaining=124, distinct_same_cost=13)
    r = analyze_roll("Jinx", 8, 50, pool, SET17)
    assert r.p_hit_at_least_2 < 0.55

def test_zero_copies():
    pool = PoolState(copies_of_target_remaining=0, same_cost_copies_remaining=100, distinct_same_cost=12)
    r = analyze_roll("Jinx", 8, 50, pool, SET17)
    assert r.p_hit_at_least_1 == 0.0
    assert r.p_hit_at_least_2 == 0.0

def test_zero_gold():
    pool = PoolState(copies_of_target_remaining=10, same_cost_copies_remaining=130, distinct_same_cost=13)
    r = analyze_roll("Jinx", 8, 0, pool, SET17)
    assert r.p_hit_at_least_1 == 0.0

def test_methods_agree():
    """markov, hypergeo, iid must agree within 2% for k >= 3."""
    pool = PoolState(copies_of_target_remaining=8, same_cost_copies_remaining=100, distinct_same_cost=13)
    results = {m: analyze_roll("X", 8, 40, pool, SET17, method=m) for m in ["markov", "hypergeo", "iid"]}
    ps = [r.p_hit_at_least_2 for r in results.values()]
    assert max(ps) - min(ps) < 0.02

def test_expected_copies_consistency():
    """E[copies] should match the analytical expected value for iid."""
    pool = PoolState(copies_of_target_remaining=10, same_cost_copies_remaining=130, distinct_same_cost=13)
    r = analyze_roll("Jinx", 8, 50, pool, SET17, method="iid")
    # 25 rolls * 5 slots * 0.22 * 10/130 = 2.12 expected copies
    assert 1.8 < r.expected_copies_seen < 2.5

def test_1cost_reroll_deep():
    """1-cost reroll at L5: full pool (22×14=308). 30g should give decent P(3-star)."""
    pool = PoolState(copies_of_target_remaining=22, same_cost_copies_remaining=308, distinct_same_cost=14)
    r = analyze_roll("Caitlyn", 5, 30, pool, SET17)
    assert r.p_hit_at_least_3 > 0.40  # Markov gives ~0.45 for 30g at L5 uncontested

# --- level_vs_roll ---

def test_level_when_pace_behind():
    state = GameState(stage="4-2", round=None, gold=50, hp=70, level=6,
                      xp_current=0, xp_needed=36, streak=0, set_id="17")
    d = level_vs_roll(state, target=None, pool=None, core=CORE, set_=SET17)
    assert d.recommended == "LEVEL"

def test_roll_when_hp_critical():
    state = GameState(stage="4-2", round=None, gold=40, hp=20, level=7,
                      xp_current=0, xp_needed=48, streak=0, set_id="17")
    d = level_vs_roll(state, target=None, pool=None, core=CORE, set_=SET17)
    assert d.recommended == "ROLL"

def test_hold_when_low_gold_high_hp():
    state = GameState(stage="3-3", round=None, gold=24, hp=80, level=6,
                      xp_current=0, xp_needed=36, streak=0, set_id="17")
    d = level_vs_roll(state, target=None, pool=None, core=CORE, set_=SET17)
    assert d.recommended == "HOLD"

# --- interest_projection ---

def test_interest_projection_basic():
    proj = interest_projection(starting_gold=30, rounds_ahead=3, streak=0, core=CORE)
    # round 1: 30 + 5 base + 3 interest = 38 (minus any spend, which is 0)
    # round 2: 38 + 5 + 3 = 46
    # round 3: 46 + 5 + 4 = 55
    assert len(proj) == 3
    assert proj[0] == 38
    assert proj[2] >= 55

def test_interest_capped():
    proj = interest_projection(starting_gold=60, rounds_ahead=2, streak=0, core=CORE)
    # Interest always 5 max
    assert proj[0] == 60 + 5 + 5  # base + capped interest

def test_streak_bonus_applied():
    """5-streak adds +2 per round."""
    proj_streak = interest_projection(30, 2, streak=5, core=CORE)
    proj_no_streak = interest_projection(30, 2, streak=0, core=CORE)
    assert proj_streak[0] > proj_no_streak[0]  # +2 more gold
