# Augie v2 — Architecture (90th-percentile build)

> Personal-use TFT coach. Goal: reliably catch the five failure modes that cost Gold/Plat
> players games. Scope stops well short of "solve TFT" — no neural nets, no combat
> simulation, no MCTS. All decisions flow from deterministic tools; the LLM narrates.

---

## 0. Scope ceiling

**What Augie v2 is built to do.** Catch these five mistakes every time they happen:

1. Leaking gold (breaking interest for no reason)
2. Leveling at the wrong time (too early, too late, wrong spike)
3. Breaking streaks accidentally (winning a round you should have lost, vice versa)
4. Over-rolling (rolling at bad P(hit) or at the wrong stage)
5. Ignoring HP danger (sitting on econ at 35 HP)

**What Augie v2 is explicitly not.** Not a solver. Not Challenger-level. Not a combat
simulator. Not a positional coach. Not a multi-user product. If you need those things,
build v3 — this document doesn't cover them.

---

## 1. The three layers

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — State Reader  (what's happening)                │
│  vision.py + state_builder.py + ocr_helpers.py  (EXISTING) │
│                            │                                │
│                            ▼                                │
│                      GameState                              │
│                            │                                │
├────────────────────────────┼────────────────────────────────┤
│  LAYER 2 — Deterministic Tools  (what's true / what's best) │
│                            │                                │
│    ┌───────────┬───────────┼───────────┬───────────────┐   │
│    ▼           ▼           ▼           ▼               ▼   │
│  knowledge/  econ.py    pool.py   comp_planner.py  rules.py│
│  (YAML)      P(hit)     contest    reachable       ~40     │
│              roll-EV    tracking   archetypes      rules   │
│    │           │           │           │               │   │
│    └───────────┴─────┬─────┴───────────┴───────────────┘   │
│                      ▼                                      │
│              recommender.py                                 │
│        scores 7 action types, picks top-3                  │
│                      │                                      │
├──────────────────────┼──────────────────────────────────────┤
│  LAYER 3 — Narrator  (what to say)                         │
│                      │                                      │
│                      ▼                                      │
│              advisor.py  (Haiku + tool-use)                │
│        picks final action from top-3, writes              │
│        one-liner + reasoning + confidence                   │
│                      │                                      │
│                      ▼                                      │
│              overlay.py  (PyQt, EXISTING + long-term panel) │
└─────────────────────────────────────────────────────────────┘
```

### Why three layers

- **Layer 1** is state. It must be right — bad state makes every downstream recommendation
  look random. Existing Augie already does this well (Vision for board/items/augments,
  LCU for level/HP, OCR as optimization). Don't rebuild it.
- **Layer 2** is math and rules. Pure Python, no LLM. This is where 90% of the tool's
  value lives. Every number comes from `knowledge/*.yaml`. Every rule is testable.
- **Layer 3** is wording. The LLM picks between top-3 near-equivalent options using
  qualitative context (scout info, comp cohesion, "feel") and writes the output. It does
  not compute numbers. That's why Haiku is enough.

---

## 2. The seven action types the recommender scores

The user can do exactly seven things at any decision point. The recommender generates
candidates of each type, scores them, returns top-3.

| Action | Parameters | Example |
|---|---|---|
| `BUY` | champion | "Buy the Jinx from shop slot 3" |
| `SELL` | unit | "Sell the 1-cost Vi to free bench" |
| `ROLL_TO` | gold_floor | "Roll until you hit 20 gold" |
| `LEVEL_UP` | — | "Buy XP to reach level 7 now" |
| `HOLD_ECON` | — | "Pass this round, take interest" |
| `SLAM_ITEM` | recipe, unit | "Build BF Sword + Cloak = Bloodthirster on Jinx" |
| `PIVOT_COMP` | archetype | "Drop Cypher, transition to Anima Squad" |

`SCOUT` and positioning are explicitly not action types in v2 — we don't have the data
to recommend them well.

---

## 3. The five scoring dimensions

Every action candidate gets five scores, each in `[-3, +3]`. Final score is the weighted
sum. Weights are hand-tuned in `knowledge/core.yaml` and revised after logged games.

| Dimension | What it measures | Example high-score case |
|---|---|---|
| `tempo` | Does this progress my board power this round? | Buying a 2-cost 2-star completion |
| `econ` | Does this preserve interest / streak gold? | Holding at 50g to cap interest |
| `hp_risk` | Does this reduce HP loss projection? | Rolling for stabilization at 30 HP |
| `board_strength` | Does this improve my expected fight outcome? | Slamming BT on main carry |
| `pivot_value` | Does this align with a reachable strong comp? | Buying a unit in the top-ranked comp |

The recommender's job is to compute these five scores for every candidate action and
pick the best. The LLM doesn't touch scores — it picks among equally-scored top-3
options and writes the verdict.

---

## 4. Runtime flow — one F9 press, end to end

```python
# Pseudocode (actual wiring lives in assistant_overlay.py PipelineWorker)

def handle_f9():
    # LAYER 1 — state
    png = vision.capture_screen()
    state: GameState = state_builder.build_state(png, client, game_id, trigger="hotkey")
    pool_tracker.observe_from_state(state)  # update contested-pool beliefs

    # LAYER 2 — deterministic
    fires: list[Fire] = rules.evaluate(state, econ, pool_tracker, knowledge)
    comps: list[CompCandidate] = comp_planner.top_k(state, pool_tracker, archetypes, k=3)
    actions: list[ActionCandidate] = recommender.top_k(
        state, fires, comps, econ, pool_tracker, knowledge, k=3
    )

    # LAYER 3 — narrator (streaming)
    for event, payload in advisor.advise_stream(
        state=state, fires=fires, comps=comps, actions=actions, client=client
    ):
        if event == "one_liner":   overlay.set_verdict(payload)
        elif event == "reasoning": overlay.set_reasoning(payload)
        elif event == "final":     overlay.set_final(payload)
```

### Cost + latency targets

| Stage | Target | Notes |
|---|---|---|
| Vision extract | ~3-5 s, $0.015 | Sonnet-4.6, unchanged from v1 |
| LCU read | <10 ms, $0 | Unchanged |
| Rules + econ + pool + recommender + comp_planner | <100 ms, $0 | All deterministic |
| Advisor (Haiku + tool-use) | ~2-4 s, $0.003 | Down from Sonnet in v1 |
| **Total** | **~5-9 s, ~$0.018** | vs v1's ~13-16 s, ~$0.02 |

---

## 5. Module map

| Module | Status | Purpose | Depends on |
|---|---|---|---|
| `schemas.py` | NEW (Phase 0) | Pydantic v2 types, the shared contract | — |
| `knowledge/` | NEW (Phase 0) | YAML playbook + loader | `schemas` |
| `econ.py` | NEW (Phase 1) | P(hit), roll-EV, level-EV, interest math | `knowledge`, `schemas` |
| `pool.py` | NEW (Phase 2) | Contested-pool point-estimate tracker | `knowledge`, `schemas` |
| `rules.py` | EXTEND (Phase 3) | 10 → ~40 rules using econ + pool + knowledge | `econ`, `pool`, `knowledge` |
| `comp_planner.py` | NEW (Phase 4) | Reachable archetypes ranked by P·power·fit | `econ`, `pool`, `knowledge` |
| `recommender.py` | NEW (Phase 5) | Scores 7 action types, returns top-3 | `econ`, `pool`, `comp_planner`, `rules`, `knowledge` |
| `advisor.py` | REFACTOR (Phase 6) | Haiku narrator with tool-use | `recommender`, `comp_planner` |
| `overlay.py` | EXTEND (Phase 7) | Add long-term panel | — |
| `vision.py` | UNCHANGED | Claude Vision screen reader | — |
| `state_builder.py` | MINOR PATCH (Phase 0) | Refactor dataclasses → Pydantic models | `schemas` |
| `db.py` | UNCHANGED | SQLite logging | — |
| `ocr_helpers.py` | UNCHANGED | LCU + OCR helpers | — |
| `session.py` | UNCHANGED | Game lifecycle | — |

---

## 6. File layout in the repo

```
TFT-Companion/
├── ARCHITECTURE.md                   ← THIS FILE
├── CLAUDE.md                          ← meta-rules for Claude Code
├── BUILD_ORDER.md                     ← phased sequence
├── STATE.md                           ← append-only progress log (sub-agents update)
│
├── schemas.py                         ← Phase 0: the frozen contract
├── knowledge/
│   ├── __init__.py                    ← Phase 0: loader
│   ├── core.yaml                      ← Phase 0: set-invariant numbers
│   ├── set_17.yaml                    ← Phase 0: Set 17 numbers
│   └── archetypes/                    ← Phase 4: hand-authored comps
│       ├── anima_squad.yaml
│       ├── exotech_jinx.yaml
│       └── ...
│
├── econ.py                            ← Phase 1
├── pool.py                            ← Phase 2
├── rules.py                           ← Phase 3: extended
├── comp_planner.py                    ← Phase 4
├── recommender.py                     ← Phase 5
├── advisor.py                         ← Phase 6: refactored
│
├── overlay.py                         ← Phase 7: long-term panel added
│
├── skills/                            ← per-module briefs for sub-agents
│   ├── knowledge/SKILL.md
│   ├── econ/SKILL.md
│   ├── pool/SKILL.md
│   ├── rules/SKILL.md
│   ├── comp_planner/SKILL.md
│   ├── recommender/SKILL.md
│   └── advisor/SKILL.md
│
├── tests/
│   ├── test_knowledge.py              ← per phase
│   ├── test_econ.py
│   ├── test_pool.py
│   ├── test_rules.py
│   ├── test_comp_planner.py
│   ├── test_recommender.py
│   ├── test_advisor.py
│   ├── test_smoke.py                  ← integration smoke test
│   └── fixtures/                      ← logged captures for regression
│       └── ...
│
└── (all existing Augie files unchanged except those listed above)
```

---

## 7. Known numbers you'll be building on

These come from the research pass. They live in `knowledge/*.yaml` but surface here for
architectural awareness:

**Set 17 shop odds** (row = level, col = cost 1..5, values sum to 100):
```
L3: [75, 25, 0, 0, 0]      L8:  [18, 25, 32, 22, 3]
L4: [55, 30, 15, 0, 0]     L9:  [10, 20, 25, 35, 10]
L5: [45, 33, 20, 2, 0]     L10: [5, 10, 20, 40, 25]
L6: [30, 40, 25, 5, 0]     L11: [1, 2, 12, 50, 35]
L7: [19, 30, 35, 10, 1]
```

**Set 17 pool sizes** (copies × distinct = total):
```
1-cost: 22 × 13 = 286    4-cost: 10 × 12 = 120
2-cost: 20 × 13 = 260    5-cost: 9 × 8 = 72
3-cost: 17 × 13 = 221
```

**Gold curve:** interest = min(5, floor(gold/10)). Streak bonus: 3-4 streak → +1g,
5 streak → +2g, 6+ streak → +3g. XP: 4g buys 4 XP. +2 free XP at round end.

**P(hit) formula** (canonical, used by wongkj12 / tftodds / every published calc):
```
p_slot = shop_odds[L][T] · k / R_T
p_refresh = 1 − (1 − p_slot)^5
p_N_gold = 1 − (1 − p_slot)^(5·floor(N/2))
```
where `k` = copies of target remaining, `R_T` = total same-cost copies remaining.

All of this is in `knowledge/set_17.yaml` and accessed via `knowledge.py` loader. No
module should read these numbers any other way.

---

## 8. What ships at each phase (you can stop at any phase with a better tool)

| Phase | Ships to user | Time |
|---|---|---|
| 0 | Nothing visible; shared contracts set up | 2-3 days |
| 1 | Advisor cites exact P(hit) numbers ("44% at 30g, L7") | 3-4 days |
| 2 | Contest warnings ("Jinx pool: 4/10 left, 3 opponents holding") | 2-3 days |
| 3 | 30 new rules firing (covers 5 failure modes end-to-end) | 1 week |
| 4 | Long-term comp target appears in overlay | 1 week |
| 5 | Recommender gives ranked top-3 actions with scores | 1 week |
| 6 | Advisor moves to Haiku + tool-use, cost drops 30% | 3 days |
| 7 | Overlay shows long-term panel + per-round panel | 2 days |

**Realistic end-to-end:** 5-6 weeks of focused work. Each phase is independently shippable.

---

## 9. The "talk to each other" protocol

This prevents sub-agent drift. Every SKILL.md enforces it:

1. **Every module imports types from `schemas.py` and only `schemas.py`.** No module
   redefines a type. No module passes raw dicts between layers.
2. **Every module's public API is declared in its SKILL.md.** If a public function isn't
   listed, it doesn't exist.
3. **Acceptance tests live in `tests/test_<module>.py` and are written first.** The
   SKILL.md shows the skeleton; the sub-agent fills it in.
4. **After each module, `STATE.md` gets an append-only entry.** Future sub-agents read
   STATE.md to know what already exists.
5. **Integration passes are separate sessions** where wires are added to
   `assistant_overlay.py`. Module-build sessions don't touch integration code.

If two modules need to communicate and the contract isn't in `schemas.py`, the answer is
always: add it to `schemas.py` with user approval, then rebuild from there. Never paper
over with ad-hoc dicts.

---

## 10. Decisions explicitly made (so they don't get re-litigated)

- Pydantic v2 for all new types. Existing dataclasses in `state_builder.py` migrate
  during Phase 0. No mixed dataclass/Pydantic state.
- Knowledge data in YAML (not JSON, not TOML). One file per set.
- Haiku for advisor, Sonnet-4.6 stays for vision. No model swaps without user approval.
- PyQt6 overlay stays. No Electron, no Tauri, no web UI.
- SQLite stays. No Postgres, no Redis.
- Tool-use pattern for advisor, not LangGraph, not agent framework.
- Archetypes hand-authored, not scraped (can scrape later if maintenance hurts).
- 1-ply action scoring, no MCTS.
- Weights in `core.yaml` hand-tuned in v2, can be fit to user's logs later.
- No combat simulation of any kind.

Re-open any of these only if a concrete failure forces the question.
