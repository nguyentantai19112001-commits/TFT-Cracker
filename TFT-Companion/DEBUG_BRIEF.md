# DEBUG_BRIEF.md — Augie overlay is broken, fix it

## What this project is

PyQt6 overlay for TFT (Teamfight Tactics). Frameless window, 780px wide, 10 sections
of coaching data. All widgets self-paint via QPainter paintEvent — no stylesheets.

Entry point: `assistant_overlay.py`
Fast test loop (no API key needed): `py demo_panel.py`

## What is broken

The overlay crashes on launch. Last known error:

```
File "ui/widgets/comp_option_card.py", line 127, in paintEvent
    f_name.setWeight(QFont.Weight.SemiBold)
AttributeError: type object 'Weight' has no attribute 'SemiBold'. Did you mean: 'DemiBold'?
```

That line was fixed but the user reports the whole thing is still broken.
There are likely more errors of the same class cascading.

## Your job

Fix every runtime error so `py demo_panel.py` launches clean and all 10 sections render.

**Do not touch `engine/` or `engine/agents/` — the backend is working fine.**

## How to work

1. Run `py demo_panel.py` — read the full traceback
2. Fix the error
3. Repeat until the window opens with no exceptions

## Where the bugs will be

All in `ui/widgets/` and `ui/sections/`. Look for:

- Wrong PyQt6 enum names — check every `QFont.Weight.*` call.
  Valid values: `Thin Light ExtraLight Normal Medium DemiBold Bold ExtraBold Black`
  `SemiBold` does NOT exist — it's `DemiBold`.
- Missing tokens — any `SIZE.x`, `COLOR.x`, `FONT.x` attribute that doesn't exist
  in `ui/tokens.py` will crash at paint time. Cross-reference every token access
  against what's actually defined in `ui/tokens.py`.
- Imports that fail at module load time (will crash before the window even opens).

## Key files

| File | Role |
|---|---|
| `demo_panel.py` | Standalone launcher with fake data — use this as your test loop |
| `ui/tokens.py` | All design tokens. Source of truth for what SIZE/COLOR/FONT values exist |
| `ui/panel.py` | AuroraPanel — wires all 10 sections |
| `ui/widgets/comp_option_card.py` | Known crash site |
| `ui/widgets/augment_rec_card.py` | Same SemiBold bug was here too |
| `ui/widgets/carry_row_v3.py` | Same SemiBold bug was here too |
| `ui/widgets/situational_frame_strip.py` | New widget — check tokens |
| `ui/sections/` | Section containers |

## Acceptance criteria

`py demo_panel.py` opens a window. All 10 sections visible. No exceptions in terminal.

The 10 sections in order:
1. Title bar (TitleBar)
2. Situational frame strip (SituationalFrameStrip)
3. Verdict hero (HeroSection)
4. Econ row (StatusPills)
5. Roll probability (ProbSection) — conditionally visible
6. Target comp cards (CompOptionRow)
7. Actions list (ActionsList)
8. Carries (CarriesSection)
9. Augments (AugmentPreviewV3)
10. Footer (Footer)
