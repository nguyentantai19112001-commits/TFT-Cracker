# CLAUDE_MD_AMENDMENT.md — Add to CLAUDE.md before starting Phase 3.5

> Append this block to the existing `CLAUDE.md` at the repo root, under the
> "Hard rules" section. Number it as the next hard rule (likely rule 10).

---

## Rule to add

```markdown
10. **Perception hierarchy (added 2026-04-21, Phase 3.5).**
    When extracting game state, use the cheapest technique that works:
    
    - **OCR** for fixed-position text/numbers: gold, HP, level, XP, stage,
      round, streak, trait counts. Fast (<50ms), free, deterministic.
    - **Template matching** for sprites with stable visual identity:
      champion portraits, star crowns, item icons, augment icons.
      Fast (<200ms), free, high-confidence-scored.
    - **Claude Vision** ONLY for: (a) novel-set recognition before a template
      library exists, (b) low-confidence fallback when template match scored
      <0.85, (c) genuinely variable text that resists templating. Vision is
      slow (~2-4s) and costs money.
    
    Default to the cheaper tier. When in doubt, ask the user — do not default
    to Vision. If a sub-agent proposes using Vision for a field that OCR or
    template could handle, push back.
    
    This corrects the original architecture, which defaulted to Vision
    because Vision has lower setup cost. The latency penalty makes that
    wrong for a live coach. Template libraries are a one-time per-patch
    cost that pay for themselves within a handful of F9 presses.
```

---

## Also update "Scope ceiling" section

Under the existing `## Scope ceiling` section, modify the list to reflect
scouting removal:

```markdown
## Scope ceiling (say "out of scope" if asked to build these)

- Value net / any neural net training
- Combat simulator (tick-level or otherwise)
- Monte Carlo Tree Search / ISMCTS
- Riot Match-V1 data crawler
- Overwolf client-side collector
- Positioning recommendations (needs x/y data we don't have)
- Multi-user, networking, authentication, deployment-at-scale
- **Opponent scouting** (removed from v2 scope 2026-04-21; deferred to v2.5).
  Do not add scout-related types, methods, rules, or UI panels. If a feature
  request seems to need opponent data, confirm with user before building.

Everything above lives in a future v3 plan that has been explicitly deferred.
```

---

## And append a new clarification under "Anti-patterns to avoid"

Add (or create) an anti-patterns section if it doesn't exist, with:

```markdown
## Anti-patterns

- **Don't reach for Vision first.** See rule 10 above. When tempted to write
  a Vision prompt, first ask: can OCR do this? Can template matching do this?
  Vision is a fallback tier, not a default.
- **Don't add dormant scaffolding for deferred features.** Opponent scouting
  fields, for example, were added pre-emptively and caused silent bugs. If a
  feature is deferred, do NOT add empty types, empty fields, or empty test
  fixtures for it. Build when it's in scope; don't pre-build.
- **Don't parse augment descriptions.** Augment identification is icon-based
  (template match). Augment metadata (category, affinity, value curve) lives
  in YAML. Vision reading augment description text was never the plan and
  should not be re-introduced.
```

---

## Apply this before any 3.5 sub-phase starts

Claude Code: add these rules to CLAUDE.md as your FIRST action in the 3.5
work. Commit that edit alone. Then begin `SCOUTING_REMOVAL.md`. This
sequence means every subsequent commit is anchored against the corrected
rules.
