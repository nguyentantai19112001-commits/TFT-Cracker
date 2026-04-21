# EXPLICITLY_DEFERRED.md — Things NOT in this package

> The user's architecture reviewer identified additional optimizations
> that were considered and explicitly deferred. If you find yourself about
> to work on one of these, STOP. They are out of scope for this session.
>
> Do not suggest adding them back as "small improvements." Each has a
> specific reason for being deferred.

---

## 1. Switching narrator from Claude Haiku 4.5 to Groq + Llama 3.3 70B

**Why deferred:** The architectural reviewer recommended this as a major
latency improvement (~2.5s → ~0.9s). However:
- The Phase 6 advisor is just-completed and working at 96 tests green.
- Swapping the LLM provider mid-polish risks destabilizing the pipeline
  we just wired.
- The right time to do this is a dedicated v2.1 milestone after playtesting
  reveals whether the current latency actually hurts in practice.
- If Haiku's 2.5s latency is tolerable during real play, this swap is
  unnecessary churn.

**When to revisit:** After 10-20 logged games if user reports "feels slow."

---

## 2. Expanding archetypes from 12 to 18-22

**Why deferred:** This is authorship work, not engineering work. Adding
archetypes before playtesting is guessing at meta gaps that may or may
not exist in the user's actual games. A user who plays tempo-heavy
fast-8 comps has different gaps than one who plays reroll comps.

**When to revisit:** After playing with the 12 current archetypes for a
patch cycle. Log which actions the user takes that the tool didn't
predict — that reveals which archetypes are missing.

---

## 3. Training a custom 10-class digit classifier

**Why deferred:** Requires labeled training data that doesn't exist yet.
The user would need to collect 200+ hand-labeled digit crops from real
screenshots to train a classifier that might outperform PaddleOCR —
and PaddleOCR (Task 6) likely hits the accuracy target without custom
training.

**When to revisit:** Only if PaddleOCR accuracy stays below 98% even
after Task 6 ships.

---

## 4. Confidence-escalation staircase with Lowe's ratio test

**Why deferred:** This requires calibration against a corpus of real
mismatches. Thresholds pulled from research (Lowe's ratio 1.3, z-score
> 5) are guesses for this specific UI. Shipping with default thresholds
would either over-trigger (lots of false "low confidence" warnings) or
under-trigger (silent failures continue).

**When to revisit:** After Task 8 (Sentry) has logged 50+ real perception
failures. Then tune thresholds against actual data.

---

## 5. phash + colorhash replacing matchTemplate

**Why deferred:** The current matchTemplate pipeline works (Phase 3.5b/c
shipped and green). phash would be faster but is an optimization, not a
fix. Doing optimizations on working code introduces regression risk with
no user-visible benefit until the tool is actually running in live games.

**When to revisit:** If template-match latency is a measurable bottleneck
during live play. Benchmark before switching.

---

## 6. DPI/resolution calibration flow

**Why deferred:** Requires PyQt UX design (one-time user-click-corners
flow at game start). This is UX work that benefits from playtesting the
current resolution assumption first. If the user runs at 1440p @ 125%
DPI and the tool breaks, that's when calibration becomes obvious.

**When to revisit:** If the user (or anyone else) reports "tool doesn't
work on my resolution."

---

## 7. Overwolf migration

**Why deferred:** Full TypeScript rewrite. Only relevant if distributing
publicly, which the user has explicitly said they won't do. This is a
~1-2 week project for essentially zero quality improvement on a personal
tool.

**When to revisit:** Never, unless the user changes the "personal use
only" constraint.

---

## 8. DINOv2 + FAISS tertiary perception fallback

**Why deferred:** Adding a third-tier fallback before measuring whether
the primary and secondary tiers actually fail at meaningful rates is
textbook over-engineering.

**When to revisit:** After Task 8's Sentry logs 100+ primary perception
failures AND Task 6's PaddleOCR fallback also fails on a non-trivial
fraction of those.

---

## 9. Closed-loop weight learning from logged outcomes

**Why deferred:** Requires SQLite schema for logging every decision +
placement outcome, plus enough games (100+) to fit a meaningful model.
The logging schema can be added later without breaking anything; the
model fitting is pure offline analysis.

**When to revisit:** After 100-200 logged games, as a v2.2 project.

---

## If the user asks to add any of these now

Push back. Reference this file. Suggest the gate condition that would
justify revisiting (playtesting data, a specific measured failure, etc.).
The whole point of deferred-list discipline is that "we could do this"
is never the same as "we should do this now."

If the user insists, document the revisit in DATA_GAPS.md with 🛑 and
let them confirm before proceeding. The scope of this package is the
9 tasks in TASK_ORDER.md — deferred items are separate work with
separate packages.
