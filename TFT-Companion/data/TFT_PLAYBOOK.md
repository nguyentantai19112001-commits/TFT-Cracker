# Augie Playbook — TFT Set 17 Space Gods

> **Freshness stamp.** Last audited **2026-04-20** against Patch 17.1b sources (BunnyMuffins, Mobalytics, tftacademy, Riot patch notes, tactics.tools). Sections 1–5 are largely set-agnostic frameworks. Sections 6.3–6.5 are the fastest to rot as the meta shifts; re-audit weekly.

**Purpose.** This doc is the single source of truth for how the live advisor thinks about a TFT board. Every heuristic the coach uses — stage benchmarks, item-slam rules, comp archetypes, unit-valuation math — should be traceable back to a line in here. You review it, you correct it, you extend it; then the assistant extracts what it needs into structured data.

**How to read it.** Sections go from most abstract (the math of the game) to most concrete (Set 17 lists + editable tables). Skim the top, dig into the tables. Everything marked `[VERIFY]` is my best guess and needs your eyes. Everything marked `[YOU]` is a call that's genuinely yours to make (playstyle, risk tolerance).

**How to edit it.** Just edit in Markdown. When you change a number in a table, that's the new truth. When the playbook YAML is generated, it mirrors these tables 1:1.

---

## Part 1 — TFT as Math

TFT looks like a cards-and-coins game, but under the hood it's a resource conversion puzzle with three meters and one clock.

### 1.1 The Four Resources

| Resource | What it buys you | Conversion rate (approx) |
|---|---|---|
| **Gold (G)** | Shop rolls, XP, direct board power | 1G ≈ 0.02 board-strength early, scales down late |
| **HP** | Time. More rounds to find upgrades. | 1 HP ≈ 0.1G of "future options" pre-stage-4, steeper after |
| **Components / Items** | Guaranteed damage/tank regardless of rolls | 1 component ≈ 3–5G of equivalent board power |
| **Tempo (board strength)** | Damage dealt, streaks, HP preserved | Non-linear — underlevel → HP bleed; overlevel → G waste |

**The game rewards optimal conversion.** Everything you do — rolling, leveling, buying XP, slamming items, levelling — is trading one resource for another. A player who does this math intuitively and converts at the right stage is a high-elo player. A player who hoards one resource (e.g. sitting on 80G with a 40HP deficit) is bleeding EV.

### 1.2 The Clock

The clock is not time-in-seconds. It's **round count**, and it runs whether you're ready or not.

- **Stages 1–3** (rounds 1-1 → 3-7): setup. Cheap unit, cheap lessons. Damage dealt is small (2–10 per loss). This is where you *build the engine*, not drive.
- **Stage 4** (4-1 → 4-7): execution. Damage is 15–25 per loss. This is the highest-variance period — most eliminations happen here.
- **Stages 5+**: closeout. Lobby has contracted. Either you have a scaled board or you're bleeding out.

**The clock is more important than any single resource.** If you can't answer "what must be true by 4-2?", you don't have a plan — you have a fantasy.

### 1.3 Lobby-Relative, Not Absolute

Your HP only matters relative to the lobby. 40 HP at 4-2 is catastrophic if the lobby average is 70. 40 HP at 4-2 is *fine* if the average is 35 — you're just mid-pack.

The coach must read lobby HP when visible. Every "should I roll / should I level" answer flips depending on lobby state. When lobby state isn't visible (planning phase), the advisor falls back to stage benchmarks in §4.

### 1.4 The Meta-Equation

> **Placement = f(Board Strength over rounds) conditioned on (Resources spent, Lobby pressure).**

Board strength must track (or exceed) the stage damage curve or you bleed. Spending too many resources to stay on curve depletes late-game options. The game is solved — in principle — by finding the minimum resource cost that keeps your board on-curve through round N, then converting leftovers into endgame power.

This is the only equation the coach needs to internalize. Everything else is operationalizing it.

---

## Part 2 — Board Strength: The Math

"Board strength" sounds vague. It's actually a sum over units.

### 2.1 Unit Contribution Score

Every unit has a per-combat contribution you can score from 0–10 along four axes:

```
U.contribution = w_dmg × DMG(U) + w_ehp × EHP(U) + w_cc × CC(U) + w_util × UTIL(U)
```

Where:

- **DMG**: damage output per combat, split into **DMG_ST** (single-target) and **DMG_AOE** (area).
- **EHP**: effective HP (tank value: base HP × armor/MR multiplier).
- **CC**: crowd control (stuns, knockups, silences) — counted as damage prevented.
- **UTIL**: trait-activation value (sometimes the *reason* a unit is on board is to turn on a trait, not to fight).

Weights shift with stage:

| Stage | w_dmg (ST) | w_dmg (AOE) | w_ehp | w_cc | w_util |
|---|---|---|---|---|---|
| 2–3 | 0.4 | 0.3 | 0.2 | 0.05 | 0.05 |
| 4   | 0.3 | 0.4 | 0.2 | 0.07 | 0.03 |
| 5+  | 0.2 | 0.45 | 0.2 | 0.1 | 0.05 |

**Why AOE scales with stage.** Early game, boards are 4–6 units scattered across hexes — single-target damage picks them off fast. Late game, boards are 8–10 units clustered for trait synergies — one well-placed AOE wipes them. Your 7.8-damage single-target carry loses to a 7.0-AOE carry on 5-5 every time, because the 7.0 is multiplied by targets hit.

**This matches your example.** A 2★ 4-cost single-target carry at "base 7 / items 7.8" ceiling is beaten in late game by any 2★ 4-cost AOE at "base 6 / items 8" — because the AOE's 8 hits 3 targets while the 7.8 hits one.

### 2.2 Star-Level Multipliers

| Star | Base stat multiplier | Practical "value" multiplier |
|---|---|---|
| 1★  | ×1.0 | 1.0 |
| 2★  | ×1.8 | 2.0 (ability scales better than stats alone) |
| 3★  | ×3.2 | 4.0–6.0 (ability scaling becomes absurd; 3★ 1-costs outclass 2★ 4-costs in many matchups) |

**Rule of thumb.** A 3★ 1-cost ≈ 2★ 3-cost in board contribution. A 3★ 3-cost ≈ 2★ 5-cost. This is why reroll comps can beat fast-8 boards — they trade economy for star concentration.

### 2.3 Item Multipliers

Items multiply unit contribution, not add to it.

| Item status | DMG multiplier | Cost / Risk |
|---|---|---|
| No items | ×1.0 | — |
| One slam (suboptimal) | ×1.3–1.5 | Low (~30–50% boost for free-to-slam component) |
| Two slams | ×1.6–1.9 | Medium |
| BiS 3-item | ×2.2–2.5 | High (requires holding components) |
| BiS 3-item + Radiant | ×2.8–3.3 | Very high — Kayle God offering, Armory, etc. |

**Consequence.** A 2★ carry with two suboptimal items (×1.7) usually beats a 2★ carry with BiS-1 (×1.3) on the same round. That's the tempo case. A 2★ carry with BiS (×2.3) crushes everything. That's the greed case. The question is always: can you survive long enough to build BiS?

### 2.4 Trait Synergy Multipliers

Traits don't just "do things" — they multiply unit contribution. Set 17 trait breakpoints (from Community Dragon data, reliable):

| Trait | Breakpoints | Type |
|---|---|---|
| Anima | 3, 6 | Medium-vertical |
| Arbiter | 2, 3 | Horizontal flex |
| Bastion | 2, 4, 6 | Tank vertical |
| Brawler | 2, 4, 6 | Tank vertical |
| Bulwark | 1 | Unique |
| Challenger | 2, 3, 4, 5 | AS flex |
| Conduit | 2, 3, 4, 5 | AP flex |
| Dark Lady | 1 | Unique (Vex) |
| Dark Star | 2, 4, 6, 9 | Vertical + ult trigger |
| Divine Duelist | 1 | Unique (Fiora) |
| Doomer | 1 | Unique (Vex trait) |
| Eradicator | 1 | Unique |
| Factory New | 1 | Unique (Graves) |
| Fateweaver | 2, 4 | Flex |
| Galaxy Hunter | 1 | Unique (Zed) |
| Gun Goddess | 1 | Unique (Miss Fortune) |
| Marauder | 2, 4, 6 | Front/mid vertical |
| Mecha | 3, 4, 6 | Vertical |
| Meeple | 3, 5, 7, 10 | Deep vertical |
| N.O.V.A. | 2, 5 | Executioner |
| Oracle | 1 | Unique (Tahm) |
| Party Animal | 1 | Unique (Blitz) |
| Primordian | 2, 3 | Tight vertical |
| Psionic | 2, 4 | AP/utility flex |
| Redeemer | 1 | Unique (Rhaast) |
| Replicator | 2, 4 | Cast-doubling |
| Rogue | 2, 3, 4, 5 | Damage flex |
| Shepherd | 3, 5, 7 | Vertical |
| Sniper | 2, 3, 4 | Backline AD |
| Space Groove | 1, 3, 5, 7, 10 | Deep vertical (HQ trait) |
| Stargazer | 3, 5, 7 | Vertical + hex placement |
| Timebreaker | 2, 3, 4 | Win-streak AS |
| Vanguard | 2, 4, 6 | Front tank |
| Voyager | 2, 3, 4, 5, 6 | Flex/unique |

Synergy multiplier estimate:

| Trait state | Contribution multiplier |
|---|---|
| No trait active | ×1.0 |
| First tier (e.g. Brawler 2) | ×1.15 |
| Mid tier (e.g. Brawler 4) | ×1.35 |
| Cap tier (e.g. Brawler 6) | ×1.65 |
| Capstone unique (Meeple 10, Space Groove 10) | ×1.9–2.2 |

These are approximations — real impact varies wildly by trait. Meeple 10 (evolves a unit into Mega Meeple) is worth more than Brawler 2 (generic HP buff). [VERIFY against actual trait variable values in `data/set_data.json` during implementation.]

### 2.5 Composite Board Strength

```
BoardStrength(board) =
    Σ_{u in board} [ contribution(u, stage) × star_mult(u) × item_mult(u) ]
  × Π_{t in active_traits} trait_mult(t, tier)
```

Normalize to 0–100 against stage-appropriate baseline. Baseline tables live in §4.

---

## Part 3 — Economy Math

### 3.1 Interest Curve

Every 10G up to 50G grants +1G interest per round. Max interest = +5G/round at 50G+.

| Gold | Interest/round |
|---|---|
| 0–9 | +0 |
| 10–19 | +1 |
| 20–29 | +2 |
| 30–39 | +3 |
| 40–49 | +4 |
| 50+ | +5 |

**Implication.** Dropping from 50 → 40 loses 1G/round forever (until you re-hit 50). Dropping from 50 → 20 loses 3G/round. The cost of a roll spree is not just "10G" — it's "10G plus N × interest forgone".

### 3.2 Streak Income

| Streak | Bonus gold/round |
|---|---|
| 2–4 W or L | +1 |
| 5 W or L | +2 |
| 6+ W or L | +3 |

Space Gods (Set 17) keeps loss-streak bonuses; they combine with interest.

**Max passive income per round** = 5 (interest) + 3 (streak) + 5 (round base) = **13G** on an active streak at 50G+. A streak break costs ~2G/round for 2–3 rounds — small, but real.

### 3.3 XP Cost Table

**[VERIFY — live patch notes]** Patch 17.1 official notes list no XP cost adjustments. Historical baseline is XP-to-9 ≈ 68–76. The internal 50-rule doc's "8→9 = 28 XP" looks like a typo and is NOT trustworthy. Treat the numbers below as Set-15/16 carryover; fix when confirmed from live client.

| Level | XP to reach (historical baseline) | Gold-to-buy-XP (2G = 4XP) |
|---|---|---|
| 4 | 8 XP | ≈ 4G |
| 5 | 12 XP | ≈ 6G |
| 6 | 20 XP | ≈ 10G |
| 7 | 36 XP | ≈ 18G |
| 8 | 48 XP | ≈ 24G |
| 9 | 68–76 XP | ≈ 34–38G |
| 10 | 84–100 XP | ≈ 42–50G |

The "cost to reach a level from the previous" is *additional* XP from zero, i.e. if the game gives you 2 XP per round naturally, buying is cheaper than the sticker price. These numbers are for planning, not exactness; the coach should never say "you need exactly 36G to reach 9" without patch-note confirmation.

### 3.4 Shop Odds by Level (Set 17)

| Level | 1★ | 2★ | 3★ | 4★ | 5★ |
|---|---|---|---|---|---|
| 3 | 75% | 25% | 0 | 0 | 0 |
| 4 | 55% | 30% | 15% | 0 | 0 |
| 5 | 45% | 33% | 20% | 2% | 0 |
| 6 | 25% | 40% | 30% | 5% | 0 |
| 7 | 19% | 30% | 40% | 10% | 1% |
| 8 | 17% | 24% | 32% | 24% | 3% |
| 9 | 15% | 18% | 25% | 30% | 12% |
| 10 | 5% | 10% | 20% | 40% | 25% |

**Consequence.** At level 7 you see a 4-cost 10% of the time per slot = ~50% chance per shop. At level 8 that jumps to ~75% per shop. This is why the "fast 8 spike at 4-2" works — four shops at level 8 = ~99% you see every 4-cost you want once.

### 3.5 Pool Depth (Copies in Pool)

| Cost | Copies per champion in pool |
|---|---|
| 1 | 30 |
| 2 | 25 |
| 3 | 18 |
| 4 | 10 |
| 5 | 9 (with multiple 5★ — reduced per champ) |

**Contest math.** If 3 players roll down for the same 2★ 3-cost, you need 6 of 18 copies, but 12 are already dispersed. You may hit 9/10 times — unless one opponent is already 2★. Then you compete for the last 9 copies and two of you go home 1★.

**Rule.** Never commit to a 3-cost reroll line past 3-2 without scouting contest (§5.7). For 4-costs, "contested" means ≥2 other boards playing the unit, because pool = 10.

### 3.6 Roll EV

Expected copies hit per roll (2G per roll = 5 units shown):

```
E[copies per roll] =
    5 × P(cost | level) × (available_in_pool / total_pool_at_cost)
```

At Level 8, rolling for Viktor (3-cost) with 14 copies left in pool:
- P(3-cost per slot at Lv 8) = 32%
- P(Viktor per 3-cost slot) = 14 / 250 ≈ 5.6%
- E[Viktor per roll] = 5 × 0.32 × 0.056 ≈ 0.09

So each 2G roll gives you ~1/11 chance to see a Viktor. You need ~11 rolls (22G) to expect 1 copy. To 2★ Viktor from 0, that's ~66G. With 40G starting pool, you're 26G short. **Don't start the rolldown.**

The coach does this math explicitly when prompted. User doesn't need to.

---

## Part 4 — Stage Benchmarks (The Curve)

These tables say "where should I be if I'm on a healthy, mixed-streak line?" Deviations are signals to adjust.

### 4.1 Healthy Curve (Mixed Streak)

| Round | Level target | Gold target | HP floor | Board quality |
|---|---|---|---|---|
| 2-1 | 4 | 10–15 | 95–100 | 4 units, 1 slammed item |
| 2-5 | 5 | 20–25 | 85–95 | 5 units, 2 items |
| 3-1 | 5–6 | 30–40 | 75–85 | 5–6 units, starting vertical |
| 3-2 | 6 | 40–50 | 70–80 | Level 6 roll if pair-heavy; else save |
| 3-5 | 6–7 | 50+ | 60–75 | 2 items on main carry; pivot decision |
| 4-1 | 7 | 50+ | 55–70 | Main carry 2★; frontline stable |
| 4-2 | 7–8 | 30–50 | 45–65 | If fast-8: rolldown. If reroll: holding 50G |
| 4-5 | 8 | 20–40 | 35–55 | 2 2★ 4-costs; 2 items BiS on carry |
| 5-1 | 8–9 | 30–50 | 25–45 | Decision: 9 now or spike 4-cost |
| 5-5 | 9 | 20–40 | 15–35 | 5-cost hunting; BiS + 1 |

### 4.2 Fast-8 Benchmark (Greed Line)

The player your example describes — sub-40 HP at 4-3, level 8, 30+ gold, 2× 2★ 4-cost with optimal items — is **running a greed line**. Targets:

| Round | Level | Gold | HP | Board |
|---|---|---|---|---|
| 4-1 | 7 | 60+ | 55+ | 2★ 3-cost backline + tank, 1 item slammed |
| 4-2 | 8 | 30–50 | 40–55 | **Spike round.** Rolldown to stabilize 2★ 4-costs |
| 4-3 | 8 | 10–30 | 30–50 | 2× 2★ 4-cost, BiS carry, 2nd carry 1–2 items |
| 4-5 | 8 | 30–50 | 30–45 | Board capped, prepping for 9 |
| 5-1 | 9 | 10–30 | 25–40 | Scouting for 5-cost; roll 20G for 4★ upgrades |
| 5-5 | 9 | 30–50 | 15–35 | Full 9-board, carry 3★ or 5-cost replace |

### 4.3 Reroll Benchmarks (1-cost, 2-cost, 3-cost)

| Archetype | Hold level | Roll window | Goal |
|---|---|---|---|
| 1-cost reroll | Lv 5 | 3-1 to 3-5 | 3★ main carry by 3-5; 3★ support by 4-1 |
| 2-cost reroll | Lv 6 | 3-2 to 4-1 | 3★ main carry by 4-1; 3★ secondary by 4-5 |
| 3-cost reroll ("Rogue Diff", etc.) | Lv 7 | 3-5 to 4-2 | 3★ main by 4-2; 3★ secondary by 4-5 |

**The reroll trade.** You spend 20–40G early (forgoing interest) to spike a 3★ that out-damages any 2★ 4-cost. If you hit the 3★, you win. If you miss (pool contested, bad RNG), you're stuck with under-leveled board and under-item carries — you lose two ways.

### 4.4 Damage Taken (Lobby-Average Range per Round)

Approximate damage per loss:

| Stage | Damage per loss (no streak) |
|---|---|
| 2 | 2–5 |
| 3 | 6–10 |
| 4 | 12–18 |
| 5 | 16–22 |
| 6 | 20–28 |
| 7+ | 25–35 |

Loss streaks compound: 4–5 losses in a row in stage 4 = ~75 HP. This is why "just lose streak to 6-loss God offering" is a real strategy: you lose 50–70 HP by 4-7 but collect +12G of streak-income over ~6 rounds + Evelynn/Soraka HP/God offering. Net: you're still alive, have more gold, and have a big anchor pick.

---

## Part 5 — Decision Trees

### 5.1 Level vs Roll vs Save (primary loop)

```
start: after combat, planning phase
├── HP ≤ 25? → roll down to stabilize (tempo > everything)
├── HP 25–50 and off-curve? → roll if a 2G roll has E[improvement] > 0.3
├── HP 50+ and on-curve? → save, hit interest breakpoint
└── HP 50+ and ahead of curve? → push level for spike
```

### 5.2 Slam vs Save Items

Slam if **ALL three** are true:
1. Item slots itself decently on a unit currently on board (DMG or EHP ×1.3+ for its role).
2. Holding the components costs board power (the components aren't combinable into a much better item within 2–3 rounds).
3. You are on-curve or behind; you're not in a position to greed.

Save if:
- You have an anchor carry in view (on board or pair on bench) and the best-in-slot is one component away.
- You're on a win streak with HP > 70 and plenty of board already.
- You're playing a known greed line (fast-9, slow-rolling for 3★ 4-cost).

**Universal slammables** (items that rarely hurt you to build because they fit dozens of carries):
- Infinity Edge / Giant Slayer (AD) — slottable on any AD carry
- Jeweled Gauntlet / Archangel's (AP) — slottable on most AP carries
- Warmog's / Bramble Vest (tank) — slottable on any frontliner
- Sunfire Cape — anti-heal + tank + AOE burn (triple-duty)
- Morellonomicon — grievous wounds answer to healing comps
- Red Buff — cheap grievous + on-hit

**Usually-hold components**:
- Spatula — conditional on trait need; rarely slam without plan
- Tear — BL/Blue Buff often the difference; don't slam into Hand of Justice if a 1-cost mage carry is your line

**Set 17 Psionic items (NEW category, Artifact-like):**
These are completed single-slot items from Armory offerings; they do NOT require components. Rules for using them:

| Item | What it does | Slam rule |
|---|---|---|
| Drone Uplink | Summons a drone dealing 25% of attacks; 2nd drone at 4 Psionic | S-tier on any ranged AD carry; elevates Shepherd Viktor to S-tier |
| Malware Matrix | −15 Armor/AS debuff; 3rd attack cleaves at 4 Psionic | Slam on any AD carry with attack speed (Kai'Sa, Caitlyn) |
| Biomatter Preserver | +5% max HP + 3 healing orbs (18% missing HP each 5s); +22% healing at 4 Psionic | Slam on frontline Psionic (Gragas, Viktor off-tank) |
| Sympathetic Implant | +20% AP, +2 MP5, +1 MP5/5s; 20% true damage at 4 Psionic | Slam on AP carry — Sona / Viktor BiS-adjacent |

Psionic items drop from god offerings and the 4-7 Armory. They do NOT combine with components. If you're offered one and have a Psionic on board (Gragas, Pyke, Viktor, Zoe, Master Yi, Sona), take it.

### 5.3 Damage Type Decision

Before committing a main carry, ask what the lobby has:

| Lobby pattern | Counter priority |
|---|---|
| Heavy tank lobby (multiple Brawler/Bastion vertical) | AOE magic + anti-heal (Viktor, Nunu, Morello) |
| Heavy backline burst (Sniper/Rogue) | Frontline MR + peel (Shen, Dragon's Claw) |
| Heavy sustain (Primordian healing + lifesteal) | Morellonomicon + anti-heal |
| Heavy AOE mages | Spread positioning + Banshee's |
| Melee-heavy (assassins, Rogue) | Cluster tanks for AOE procs; place carry in corner |

Your example (AOE beats single-target in late game) maps to row 1 of this table — when the lobby has mega-tanks, single-target just can't break through. Your planner should flag this pattern and either force-pivot items toward %HP shred, or accept a top-4 ceiling.

### 5.4 Tempo vs Greed (Playstyle Classifier)

| You are playing tempo if | You are playing greed if |
|---|---|
| HP < 60 by 3-5 | HP > 70 by 3-5 |
| Lose streak active | Win streak active |
| Items all slammed | Holding 3+ components |
| Gold 30–50, rolling freely | Gold 50+, saving for spike |
| Not committed to final carry | Clear final carry identified |

**Implication for coach.** Every rule has a "tempo weight" and "greed weight". On a tempo read, the coach suggests slam+play; on a greed read, the coach suggests hold+spike. When reads conflict, the coach states the conflict rather than picking one side.

### 5.5 Commit vs Flex

| Signal | Commit to line | Flex longer |
|---|---|---|
| Augment locks you in (e.g. Hero aug, trait-specific crown) | X | |
| Uncontested key unit on 2★ early | X | |
| Strong offered God matches your line | X | |
| Items are generic (BF, Tear, Rod) | | X |
| Pair-count is low (0–1 pairs in traits) | | X |
| Contested scout (2+ other boards on your line) | | X (pivot) |

### 5.6 Stage-by-Stage Decision Flowchart (Water Park Tactics, adapted)

A high-elo thinking process restated as a branching tree. Coach walks this on every F9 press and reports which branch it landed on.

#### Stage 1 — "Hold the right things, decide the line"

Always hold:
- 1-cost units that can be rerolled (candidates for 3★ line)
- Units that can 5-win-streak you right now
- Trait-unique / econ units (Set 17: God-Blessed, Party Animal Blitz, Bulwark Shen if you see one early — rare but hold)

Then the player is in one of four states:

| State | Response |
|---|---|
| Hit 2★ 1-costs + good components + uncontested + good aug | **Evaluate for reroll.** Are copies out? (<3 = bad). Do you have HP+copies? If yes → commit at 3-1 for 3★. |
| Strong board, 5-streak potential | **Play Aggressive.** Slam tempo items, push level, hold next-in pairs, scout, position for streak. |
| No clear line, mixed signals | **Conservative build.** Aim for average board, don't lose streak, hit econ thresholds, don't break streak on stage 2. |
| **4th Forbidden Option:** open fort / commit stage 1 | Rare. Only when the line is so strong it's worth giving up every other option (unbalanced patches; Set 17 [VERIFY]). |

#### Stage 2 — "Did I keep my streak?"

Split based on what happened:

- **Kept streak →** hold until stage 3. Don't break streak unless the econ swing is bigger than 2 rounds of streak gold. Might luck into a win-streak/lose-streak conversion.
- **Lost streak →**
  - If board is average → **Conservative**: build a board that kills units, not chasing streak. Roll minimal, hit econ thresholds.
  - If board is really weak → **Open Fort**: deliberately lose, keep loss-streak going for income + low-HP gods, even at HP cost. Commit fully — partial open-fort is the worst outcome.

#### Stage 3 — "Evaluate your spot"

Checklist before deciding:
- Streak state (W / L / broken / building)
- Econ (gold vs interest thresholds)
- HP vs lobby
- Board strength vs stage baseline (§4.1)
- Components on bench + carousel drops
- Augments taken + augment still-to-come
- Uncontested strong units on board

Decide on 3-2 whether you are **sacking stage 3** (eat HP damage for econ+position) or **fighting** (convert gold into board). If you lost stage 2 already, you usually CANNOT sack stage 3 too — you must stabilize. This is why keeping units on stage 2 matters: it keeps stage 3 stabilization cheap.

Branches from here:

| Signal | Action |
|---|---|
| Committed 1-cost reroll line | Roll down 3-1, target 3★ main carry. Do NOT level past 5 until 3★. |
| Hit early 2/3-cost pairs, strong direction | Play Aggressive; slam items, push level 6. Win-streak → Conservative (preserve streak). Lose-streak → Play Conservative (don't bleed). |
| Given 2/3-cost reroll direction (aug, strong pair signal, god pick favouring the line) | Commit: slow-roll at level 6 for 2-cost, level 7 for 3-cost. |
| No direction, pair-light | Level + save, use stage 3 for econ, let stage 4 decide the comp. |
| Too broke to roll on 4-2 + bleeding out | **Stabilize 3-5 on level 7** to prepare for a 4-5 rolldown instead. Trade the 4-2 spike for survival. |

#### Stage 4 — "Am I too rigid, or too flex?"

Checklist first:
- What items have I slammed by now? AD or AP?
- What units are on my board + what augments do I have?
- Gold / HP situation?

Then decide on the **strongest option** from the comps actually available (given items + units + augments). Strong reminder: **only 9 bench slots**. Being unreasonably flexible (holding every possible support unit just in case) is itself a mistake — it slows your rolldown and caps your board strength.

Deciding your flex options (the crucial fork):

| What you have | What to play | Non-negotiable |
|---|---|---|
| Slammed AD items | Pick the best AD comp your board supports | **Shred** (e.g. Last Whisper) |
| Slammed AP items | Pick the best AP comp your board supports | **Sunder** (e.g. Ionic Spark / MR shred equivalent) |
| Mixed items | Play the comp that uses more of them; have a back-up carry for the rest | Both shred+sunder if bicarry |

**"BiS is a fake concept, but."** Certain items are genuinely make-or-break for certain carries:
- Most melee AD carries need a form of sustain (Bloodthirster / Hand of Justice)
- Ability-cast carries (Ahri-archetype) need Blue Buff or an equivalent mana engine
- Crit-ult carries (Karthus-archetype) are useless without ability crit (IE or JG)

If the make-or-break item is unhittable, the carry isn't an option — don't commit. Dual-carry outliers (Zed-type) have one rigid carry + one flex carry using leftover items.

#### Stage 4 Rolldown — "Where did I land?"

After the 4-2 rolldown (or 4-5 if you stabilized on 7):

| Outcome | Response |
|---|---|
| Hit best option | Play the best comp, stabilize board, eval level 9 timing |
| Hit 2nd-best option | Play given option, look to pivot or flex later if lobby breaks your way |
| Missed everything | Stop. Figure out realistic placement (3rd? 4th?). If you can't realistically outcap the top 2, stay at 8 and roll to guarantee 3rd+. |

#### Stage 5 — "Am I stable? Go 9."

Stability checklist:
- Do I have 3-item carries? How good? What unit are they on?
- Is my board fully upgraded (no 1★s outside of trait bots)?
- Do I have Shred / Sunder / Anti-Heal?
- What are my augments doing?
- How strong is the lobby (# of strong boards left)?
- How long will it take to hit level 9 + enough gold to roll at 9?
- What placement am I realistically playing for?

If stable → **Go 9.** If not stable → **roll at 8 until stable**, then go 9.

Special case: if your realistic placement is 3rd–4th (you can't out-cap 1st/2nd), don't gamble for 1st at 9. Stay at 8, hit the 3rd/4th consolation carry upgrades, guarantee the placement.

### 5.7 Scouting Cadence

Scout frequency by stage:

| Stage | Minimum scouts |
|---|---|
| 2 | 1× (who has pair boards already?) |
| 3 | 2× (before each rolldown) |
| 4 | 3× (every round — contest math changes) |
| 5+ | Every round — item check, position check |

Scout data the coach uses:
- Contested units (who else is on my line?)
- Item types in lobby (AD-heavy? AP-heavy? Tank-heavy?)
- Level leaders (who's at 8 already?)
- HP leaders (who's the healthiest greed player?)

This data isn't available from a single screenshot today. Pipeline gap noted.

---

## Part 6 — Set 17 Specific Data

### 6.1 Full Roster by Cost (from `data/set_data.json`, auto-generated)

**1-cost (18 units):**
Aatrox (N.O.V.A./Bastion), Briar (Anima/Primordian/Rogue), Caitlyn (N.O.V.A./Fateweaver), Cho'Gath (Dark Star/Brawler), Ezreal (Timebreaker/Sniper), Leona (Arbiter/Vanguard), Lissandra (Dark Star/Shepherd/Replicator), Nasus (Space Groove/Vanguard), Poppy (Meeple/Bastion), Rek'Sai (Primordian/Brawler), Talon (Stargazer/Rogue), Teemo (Space Groove/Shepherd), Twisted Fate (Stargazer/Fateweaver), Veigar (Meeple/Replicator). *(plus Golem, Scuttler, Dummy, Mini Black Hole — non-playable)*

**2-cost (13):**
Akali (N.O.V.A./Marauder), Bel'Veth (Primordian/Challenger/Marauder), Gnar (Meeple/Sniper), Gragas (Psionic/Brawler), Gwen (Space Groove/Rogue), Jax (Stargazer/Bastion), Jinx (Anima/Challenger), Meepsie (Meeple/Shepherd/Voyager), Milio (Timebreaker/Fateweaver), Mordekaiser (Dark Star/Conduit/Vanguard), Pantheon (Timebreaker/Brawler/Replicator), Pyke (Psionic/Voyager), Zoe (Arbiter/Conduit).

**3-cost (13):**
Aurora (Anima/Voyager), Diana (Arbiter/Challenger), Fizz (Meeple/Rogue), Illaoi (Anima/Vanguard/Shepherd), Kai'Sa (Dark Star/Rogue), Lulu (Stargazer/Replicator), Maokai (N.O.V.A./Brawler), Miss Fortune (Gun Goddess/Choose Trait), Ornn (Space Groove/Bastion), Rhaast (Redeemer), Samira (Space Groove/Sniper), Urgot (Mecha/Brawler/Marauder), Viktor (Psionic/Conduit).

**4-cost (13):**
Aurelion Sol (Mecha/Conduit), Corki (Meeple/Fateweaver), Karma (Dark Star/Voyager), Kindred (N.O.V.A./Challenger), LeBlanc (Arbiter/Shepherd), Master Yi (Psionic/Marauder), Nami (Space Groove/Replicator), Nunu & Willump (Stargazer/Vanguard), Rammus (Meeple/Bastion), Riven (Timebreaker/Rogue), Tahm Kench (Oracle/Brawler), The Mighty Mech (Mecha/Voyager), Xayah (Stargazer/Sniper).

**5-cost (10):**
Bard (Meeple/Conduit), Blitzcrank (Party Animal/Space Groove/Vanguard), Fiora (Divine Duelist/Anima/Marauder), Graves (Factory New), Jhin (Dark Star/Eradicator/Sniper), Morgana (Dark Lady), Shen (Bulwark/Bastion), Sona (Commander/Psionic/Shepherd), Vex (Doomer), Zed (Galaxy Hunter).

### 6.2 Unit Role Classification (condensed) [VERIFY per champion]

| Role | Units |
|---|---|
| **Main-carry AD** | Kai'Sa, Xayah, Jinx, Samira, Jhin, Caitlyn (reroll), Rhaast (bruiser), Graves |
| **Main-carry AP** | Viktor, Fizz, Karma, Aurelion Sol, Bard, Sona, Vex, Morgana, Veigar (reroll) |
| **Secondary / flex carry** | Kindred, LeBlanc, Akali, Gwen, Riven, Miss Fortune, Lulu (reroll), Talon (reroll) |
| **Main tank (bruiser)** | Rhaast, Rammus, Tahm Kench, Mordekaiser, Shen, Nunu, Leona (reroll), Urgot |
| **Secondary tank / bastion** | Ornn, Jax, Poppy (reroll), Diana, Illaoi, Maokai |
| **CC / utility** | Blitzcrank, Zoe, Twisted Fate, Milio, Nami, Pyke, Lulu |
| **Trait bot** | Golem, Scuttler, Dummy, Meepsie (if not running Meeple main) |

### 6.3 Meta Comps (cross-sourced snapshot, Patch 17.1b, 2026-04-20)

Different sources rank slightly differently. The comps below appear S-tier in ≥2 of (BunnyMuffins, Mobalytics, tftacademy, TFTFlow):

**S-tier (consensus):**
- **Stay Groovy** — Space Groove vertical, **Nami** primary carry (NOT Riven as in prior sets), Fast 8/9, AP-focused
- **Turbo Doomer** — Vex carry, Bard + Rammus support, Fast 9, AP
- **Snipin & Vibin** — Xayah + Jhin, Sniper vertical, Fast 8, AD
- **Slap & Zap** — Viktor primary (+ Nami, Illaoi support), Level 7 slow-roll, AP

**S-tier (single-source, watch for stabilization):**
- Vex 9-5 Fast 9 (tftacademy) — may overlap with Turbo Doomer framing
- Shepherd Viktor (BunnyMuffins) — Viktor + Shepherd vertical, Fast 8/9

**A-tier (reliable picks):**
- Rogue Diff (Kai'Sa/Fizz/Ornn/Rhaast, Lv7 slow-roll, AD) — *was S-tier in earlier read; has settled A*
- Xayah Fast 9 / Jhin variant (AD)
- Bel'Veth Primordian Reroll (AD)
- Samira Knock-up (Space Groove/Sniper, AD)
- Vanguard Karma & LeBlanc (AP bicarry)
- Space Groove Riven (if Space Groove +1 emblem, AD/hybrid)
- Stargazer Xayah (Lv8, Constellation-dependent)
- Twisted Fate Reroll
- Mecha, Corki Riven, MF Reroll (variable)

**Meta shape.** The release patch leans **AP-heavy** (Vex, Viktor, Nami, Karma, LeBlanc top carries). AD lines (Xayah, Jhin, Kai'Sa, Bel'Veth) are present but below the AP ceiling. Expect patch 17.2 to rebalance this.

### 6.4 Three Canonical Comps (detail for coach)

#### Rogue Diff (3-cost reroll)

- **Core:** Kai'Sa, Fizz, Rhaast, Ornn
- **Secondary:** Riven (4-cost), Talon (1-cost pair early)
- **Level path:** Stay 7, roll 3-5 or 4-1 for 3★s
- **Item build:**
  - Kai'Sa: IE + Runaan's + Last Whisper (BiS), slammable to Giant Slayer / Statikk
  - Fizz: Blue Buff + Jeweled Gauntlet + Rabadon's (BiS), slammable to Hand of Justice
  - Ornn: Warmog's + Bramble Vest + Gargoyle (BiS), slammable any tank
  - Rhaast: Bloodthirster + Titan's Resolve + Quicksilver (BiS)
- **Spike rounds:** 3-5, 4-1, 4-5
- **Position:** Tanks front line, Kai'Sa and Fizz in opposite far corners behind Bastion tanks
- **HP target:** Above 50 at 3-5 for the rolldown; can drop to 30 during the slow-roll

#### Stay Groovy (Space Groove vertical, Fast 8/9)

- **Core:** Nami (primary carry), Ornn, Blitzcrank, Tahm Kench
- **Supporting:** Gwen or Samira (secondary damage), Teemo/Nasus (for trait count)
- **Level path:** Fast 8 at 4-2, 9 at 5-2 if HP allows
- **Item build:**
  - Nami (primary AP carry): Jeweled Gauntlet + Archangel's + Rabadon's (BiS); slammable to Blue Buff / Hand of Justice
  - Ornn: Warmog's + Bramble Vest + Gargoyle (standard tank)
  - Blitzcrank: tank items + Zz'Rot / Redemption for peel
  - Tahm Kench: Dragon's Claw + Gargoyle (anti-magic frontline)
- **Spike rounds:** 4-2 (cap 8), 5-2 (cap 9)
- **Position:** Blitz + Tahm front-left, Ornn front-right; Nami in protected corner behind Ornn
- **HP target:** 55+ at 4-1; can drop to 30 on 5-1 if committing to Lv9
- **Note:** Riven was the Stay Groovy carry in pre-release / early PBE reads. Live meta has Nami as the dominant AP carry in this line. Update if a patch rebalances Nami.

#### Swarm-Storm (Primordian/N.O.V.A. reroll)

- **Core:** Bel'Veth (3★), Rek'Sai (3★), Briar (3★), Caitlyn (3★), Maokai/Kindred flank
- **Level path:** Slow-roll at 6 through 3-5; level 7 after 3★ secured; level 8 at 4-5
- **Item build:**
  - Bel'Veth: Deathblade + IE + Quicksilver
  - Caitlyn: Runaan's + Zephyr + Red Buff
  - Kindred (or Maokai): standard tank / AP flex
- **Spike rounds:** 3-5 (if 3★ Bel'Veth), 4-5, 5-1
- **Position:** 2 rows, tanks front, carries centered back, spread against AOE
- **HP target:** Can run deep loss streak — 30 HP at 4-1 acceptable if 3★ Bel'Veth locked

### 6.5 Realm of the Gods (Set 17 carousel replacement)

**Mechanic.** Each game selects 2 Gods (out of 9). You encounter them 3 times: **2-4, 3-4, 4-4**. Each offering comes with a guaranteed component. At **4-7** you unlock a tailored Boon armory from the god you picked most often, which then continues to drop loot for the rest of the game. Each 4-7 boon can be rerolled for 1 gold.

**The nine gods (cross-source tier, 2026-04-20):**

| God | Domain | Offerings | 4-7 Boon | Tier | Best when |
|---|---|---|---|---|---|
| **Ahri** | Opulence | Gold, XP, rerolls | +2% AD/AP per level | S | Fast 9 / econ lines |
| **Yasuo** | The Abyss | Power hexes on champions (Cosmic, Solar, Cryogenic, Starlight, Acceleration, Storm) | +50% hex power; 12G if only 2 hexes taken | S | Hyper-carry lines that want stat amp |
| **Kayle** | Order | Components & item completion | Upgrade a random completed item to Radiant | A | BiS / duo-carry lines with items already complete |
| **Evelynn** | Temptation | 2★ upgrades, gold (Blood Pact), Steamroll engine — at HP cost | +10% durability; -1 extra HP on loss | A | Spare HP + need immediate spike |
| **Ekko** | Time | Scuttle Party, cost units, Spatulas, Artifacts (delayed payoff) | Anomaly item for role-based evolution | A | Loss-streak / scaling comps |
| **Varus** | Love | Duplicators, tailored shops | +18 HP per total star-level on team | A | Reroll comps (double up copies) |
| **Aurelion Sol** | Wonders | Quests: Wealth / Starry / Trait / Level / Low Health / Reroll | Choose from 3 quests (AP/AD, item anvil + gold, trait bonus) | A | You reliably complete quests |
| **Soraka** | Stars | Player HP + tactician health | +2 HP per missing player HP | B | Deep lose-streak survival |
| **Thresh** | Pacts | Random boons from other gods + gold | Roll dice each round for random bonus | C | Fallback / no clear line |

**Pengu** is a **separate** low-HP catch-up mechanism, not a god. If your HP is lowest in the lobby, Pengu offers higher-cost units and component anvils during PvE rounds.

**Coach heuristic.** Both chosen gods should be known before round 2-4. The coach treats god-picks as *multipliers* on the playstyle read:
- Ahri + Yasuo in game → Fast-9 bias reinforced
- Evelynn + Ekko in game → tempo-or-delay fork; the coach should ask "are you committing to Eve HP-sacks or Ekko scaling?"
- Soraka + Thresh in game → signals low lobby strength / survival orientation; the coach biases conservative advice

The 4-7 boon choice is a major pivot point — the coach should flag "which god did you pick more?" around 4-5 so the user is positioned for the right armory.

---

## Part 7 — What the Coach Needs (Prompt Inputs)

To use this playbook in the assistant, the advisor prompt should receive:

1. **Per-unit structured data**: champion name, cost, traits, star, items, position — we already have this.
2. **Trait activation state**: which traits are at which tier (1/2/3 breakpoint). Available.
3. **Stage + round**: X-Y format. Available.
4. **HP, gold, level, XP, streak**: available.
5. **[GAP] Components on bench**: the vision currently extracts "items" but not loose components on the bench. This is the single biggest data-gap for meaningful coaching. **Add to vision prompt.**
6. **[GAP] Shop**: available but not rated against the current board's needs. The coach should compute "relevance score" per shop slot (does this unit pair with my board? fill a trait? replace a weak unit?) before giving "buy X" advice.
7. **[GAP] Augments + God picks**: we extract augments but not Realm of the Gods picks. Add to vision prompt.
8. **[GAP] Opponent scout data**: not captured today. Scout-round capture is a separate feature.

---

## Part 8 — What the Coach Says (Output Schema)

The advisor's recommendation object should express the framework above. Proposed extended schema (superset of current):

```yaml
one_liner: "Roll everything now — 28 HP, one loss from elimination."
confidence: HIGH            # based on how clearly the benchmarks fire
tempo_read: BEHIND          # ahead / on-pace / behind / critical
playstyle_detected: tempo   # tempo / greed / undecided
primary_action: ROLL_DOWN   # existing set
reasoning: "..."            # free text

# NEW — specific deltas from benchmarks
benchmark_deltas:
  hp_delta: -32             # how far from curve at this stage (negative = behind)
  gold_delta: +8
  level_delta: 0
  board_strength_delta: -20

# NEW — specific actionable micro-moves
micro_actions:
  - type: pair_up
    target: "Rek'Sai"       # pair from shop slot 2 with board Rek'Sai for 2★
    priority: HIGH
  - type: slam_item
    target: "Warmog's Armor"
    components: ["Giant's Belt", "Giant's Belt"]
    on_unit: "Ornn"
    priority: HIGH
    reasoning: "on-curve tank HP for stage 3"
  - type: reposition
    unit: "Kai'Sa"
    from_hex: [3, 3]
    to_hex: [0, 3]
    reasoning: "vs opponent sniper comp, far corner reduces focus"

# NEW — explicit tradeoff when relevant
trade_off:
  option_a: "Roll 20G now — likely lock 2★ Viktor; save 4-2 spike."
  option_b: "Save; push level 8 at 4-2 — risky given 42 HP."
  recommendation: A

considerations: [...]       # existing
warnings: [...]             # existing
data_quality_note: ...      # existing
```

The main shift: from "fire rules, write one-liner" to "measure deltas from benchmarks, name the tradeoff, suggest micro-actions."

---

## Part 9 — Open Questions for You

Before I turn this into `playbook.yaml` and wire the advisor to it, I need your calls on:

1. **Playstyle default.** When tempo/greed is genuinely mixed, do you want the coach to default to the tempo recommendation (safer, top-6 floor) or the greed recommendation (higher ceiling, higher bust risk)? `It really depends. If my opener is bad, like I don't have a two-star unit in stage two like overall, just look up what a well opener would look like, or like I would usually pick an augment that gives me econ and I will probably sack my HP for econ if I have econ traits in the game, if I find these guys, these units, then I will stack on the way to, let's say, 4/1 and make a comeback from there. But if I have a good opener I have slamable items for tempo, optimal or sub-optimal. I was just gonna slam it and try. If I get a three-winch rig and the gold for the carousel, I will get the component that will help me keep making items. To make my tempo higher and higher and try to greet a five trick before neutral to compensate for the gold that I spent leveling and investing in my board, get the three gold from streaking. Like that is the best scenario, like five Win streak into neutral I'll just push my temple as hard as possible and the average would be like a 3.5. From that spot you cannot four from that spot unless you mess up really bad and your roles are really bad usually in that spot after neutral then I'll just tempo into four one. When every other player they are committing to roll on level eight, I will sack the stage4 and level up to nine after and play off of two-star five cost if and if with subtle more items from slamming for tempo before that is the general guide in my head for a TFT game and with reroll comps there are a lot of signals that you should commit to a reroll comp let's say there's an encounter with a space god that gives me a strong three-cost unit that is also meta for level 7 reroll strat then I will commit to a reroll and try to beat people in stage three because I have a two-star three cost and most of them don't hold the pairs so they don't have two stars, three cards, and they will lose to me on stage three I would say that reruns are very coin flippy in my opinion. I love to play with e-cons. Tempos like these two that I mentioned before are just my go-to play style and there is also the AP and the AD COMp but I don't wanna get into that because it's pretty complicated. If you ask me for a playstyle default then I would prefer either of the two: if I have a good opener or play tempo into level 9 or if my tempo is is bad meaning that I invested in my board but I somehow lost my win streak then I will still just have to play for a level 8 roll down and if I have a weak opener then I will likely sac and look for units that have econ traits or if I don't find them then I will just play my strongest board and lead out as little as possible while holding as much gold as possible and roll down on four one with at least thirty gold to make a solid board of at least one two-star four-cost and at least a pair other fourcost units that are on the comp.`
2. **HP floor tolerance.** Some players run deep lose-streak lines and stay alive at 20 HP; others refuse to drop below 50. What's your floor? `I would say I am pretty comfortable when I have three lives left. A definition of a life in TFT is when you lose a round. Like if I'm on, let's say, I'll stack all the way. I'm playing an icon trait like Anima. And it's like on the way to 30 HP. And I'd roll down. Then I would consider that my current HP is 3 lives even though the average damage of a stage 4-5 damage is 10+Because I have a really strong board, there is no way that I'm losing to six or seven units if I somehow lose a fight when I have invested all my gold in it, it would be just a two- to three-unit loss which converts to like 7 or 9 HP so basically 30 HP is three lives so I'm pretty comfortable as long as I have three lives because when I lose I still have the choice to  all-in and play for a top5, 4 ,3 but if my evaluation sees it like that, I can possibly create and take the top one from gambling then I will just greet because I still have the choice. I still have two lives, right so yeah that's my life philosophy in tft.`
3. **Comp pool restriction.** Should the coach only recommend the top-10 meta comps, or reason about any comp it sees on your board? The former is safer; the latter teaches more. `[I would love for you to recommend comps based on the current stage. If I want stage two then any unit that is two-star is better than any comps that you would recommend but when it gets to stage three, then it's a bit tricky because you gotta utilize your shop to make the best mid-game board and somewhat solidify your foundation for stage four, I would love you to just analyze my board before giving an in-depth comp guide and I'm pretty flexible so I can play like 5 to 6 comps comfortably and I still have you, right? You're my assistant so you basically play ing the game with me so let's have fun bro. Let's learn together.]`
4. **Prompt depth vs latency.** A richer advisor prompt (full playbook + scout + bench components) raises latency from 14s → likely 20s. Trade-off: smarter advice, slower delivery. `[Yes in-depth is the way to go here but make sharp points.]`
5. **Carry archetype bias.** You seem to favor AOE over single-target in your example — is that a general preference, or situational? If general, the coach biases comp suggestions toward AOE-heavy lines. `[I think you should be the one giving me on that because you're better at math, right? You should look at the core character design. There are tanks that are not designed for tanking at all; they are designed to use their effective HP, cast, and die. And there are tanks that are just completely unkillable when building best items for them. And also the same thing, the same design philosophy goes for carries there are some carries that are designed to just completely blast the enemy camp withaoe dmg with  damage amplifying items, stats and there are some AOE units that are just designed to do best with effect Causing items like Morello shreds you should be doing a really deep dive into the character design of this game it's very interesting so this is more of a command that you put in a wholesession you know what I will tell you: to make an agent or a skill that will do a deep dive into the character design, not their graphics, not their appearance, but their design philosophy behind their stats, their damage, their unique interaction with certain items, and their BIS and why they are good on a certain comp but do nothing in another comp.]`

---

## Part 10 — How This Doc Becomes Code

Once you've reviewed and edited:

1. I extract §2–6 into `data/playbook.yaml` — tables become dicts/lists, rules become weighted booleans.
2. `rules.py` grows: new rule families fire on benchmark deltas, pair-up detection, item-slam opportunity, playstyle classification.
3. `advisor.py` system prompt grows: embeds the "contribution math" mental model and references the playbook tables directly.
4. Vision prompt grows: captures loose components on bench + augments + God picks (the §7 gaps).
5. Output schema grows to match §8.

Estimated implementation once this doc is locked: 3–4 hours for rules + advisor prompt + schema; +1 hour for vision prompt bench-component extraction; +1 hour for a test screenshot suite covering all §6.4 comps.

---

---

## Appendix — Audit Log

**2026-04-20 (v0.2):** First audit vs live Patch 17.1b sources.

Corrected:
- §3.3 XP table — removed speculative "56G for 8→9"; marked [VERIFY] pending live client.
- §5.6 removed "headliner-equivalent" (Set 10 term).
- §6.3 meta list — replaced early-read S-tier (Slap&Zap listed as Primordian/Rogue) with consensus cross-source S: Stay Groovy / Turbo Doomer / Snipin & Vibin / Slap & Zap (Viktor Lv7).
- §6.4 Stay Groovy — carry swapped from Riven/Gwen to **Nami** (current meta).
- §6.5 Realm of the Gods — fully rewritten. Fixed: Pengu is NOT a god; added missing Yasuo, Aurelion Sol, Thresh; added encounter timing (2-4, 3-4, 4-4) + 4-7 tailored boon mechanic; added per-god tier and 4-7 boon effects.
- §5.2 — added Psionic items table (new Set 17 category, drop from gods/armory, no components).

Confirmed current:
- §3.4 shop odds (Level 7 is post-17.1 value 19/30/40/10/1).
- §3.1 interest curve + §3.2 streak bonuses unchanged in 17.1.
- Champion roster (§6.1) matches `data/set_data.json`.
- Trait breakpoints (§2.4) match `data/set_data.json`.

Known gaps (not fixable from web research):
- Exact 8→9 and 9→10 XP costs in Set 17 patch 17.1 — not in public patch notes; must verify from live client.
- Lower-level shop odds (Lv 3/4/5/6/8/9/10) — only Level 7 confirmed post-patch; others are carry-over best-guess.
- Item tier list — metabot.gg scrape failed; re-pull later.

## Sources

- [TFT Set 17 Space Gods Guide — eloboost24](https://eloboost24.eu/blog/tft-set-17-space-gods-guide)
- [Best TFT Meta Comps Tier List (Set 17) — TFT Flow](https://tftflow.com/tier-list)
- [TFT Meta Team Comps — tftactics.gg](https://tftactics.gg/tierlist/team-comps/)
- [Best PBE TFT Team Comps (Patch 17.1) — Mobalytics](https://mobalytics.gg/tft/guides/best-tft-pbe-comps)
- [Meta Team Comps Challenger Set 17 — Tacter](https://www.tacter.com/tft/guides/meta-team-comps-challenger-set-17-space-gods-tier-list-b78bbf34)
- [TFT Leveling Guide Set 17 — BunnyMuffins](https://bunnymuffins.lol/tft-leveling-guide/)
- [TFT Economy Mastery — Boosteria](https://boosteria.org/guides/tft-economy-mastery)
- [Fundamentals of TFT — BunnyMuffins](https://bunnymuffins.lol/fundamentals-of-tft/)
- [TFT Itemization Guide — Boosteria](https://boosteria.org/guides/tft-itemization-guide-bis-vs-flexible-items-work)
- [Understanding Tempo in TFT — Dignitas](https://dignitas.gg/articles/understanding-how-tempo-changes-the-game)
- [Guide: How to Play Tempo in TFT — Tacter](https://www.tacter.com/tft/guides/guide-how-to-play-tempo-in-tft-ddb8b3f3)
- [BunnyMuffins — Set 17 Gods Mechanic Explained](https://bunnymuffins.lol/gods/)
- [BunnyMuffins — Set 17 Meta Snapshot (Patch 17.1)](https://bunnymuffins.lol/meta/)
- [tftacademy — Set 17 Comp Tierlist (Patch 17.1b)](https://tftacademy.com/tierlist/comps)
- [Mobalytics — Set 17 Space Gods release](https://mobalytics.gg/tft/new-set-release)
- [Riot — TFT Patch 17.1 Notes](https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/teamfight-tactics-patch-17-1/)
- [tactics.tools — Patch 17.1 Notes Summary](https://tactics.tools/info/patch-notes/17.1)
- Water Park Tactics flowchart, u/mokabynone (reddit, image provided by user)
- Internal: `data/tft_set17_rules.md` (user-provided 50-rule research doc, 2026-04-20)
- Internal: `data/set_data.json` (Community Dragon Set 17 champion/trait dump)
