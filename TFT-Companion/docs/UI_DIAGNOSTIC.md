# UI Diagnostic Report — Aurora Panel

**Date:** 2026-04-21  
**Method:** READ-ONLY — no code edited during this pass  
**Screenshot:** `docs/diagnostic_screenshots/01_demo_panel.png`

---

## 1. Screenshot: What the panel actually looks like

Window opened (exit 124 = timeout, no crash), Mica backdrop confirmed. Panel is **visible and draggable** at correct dimensions (500 × 680px).

### What renders correctly
| Section | Status | Notes |
|---|---|---|
| Title bar chrome | ✅ | Logo tile, stage label ("Stage 4-2"), pin/min/close buttons all visible |
| HP pill | ⚠️ renders | Shows "HP 47" — value is gold, not HP (see Bug 1) |
| Verdict badge | ✅ | "↑ Buy" renders with gradient border and correct color |
| Hero ChampIcon (52px) | ✅ | Jinx sprite loads — `set_champion()` is called, which triggers `_try_load_pixmap()` |
| Status pills | ✅ | Gold / Level / Streak / Interest all visible with correct pill style |
| Action rows | ✅ | Two rows with icon glyphs, headline text, subline, score badges |
| Footer | ✅ | "● 320ms" and "Educational use only" visible |

### What does NOT render
| Section | Status | Root cause (see below) |
|---|---|---|
| Roll Probability card | ❌ invisible | `ProbCard` has no `sizeHint()` — collapses to 0 height in layout (Bug 2) |
| Trait chips (Target Comp) | ❌ invisible | `TraitChip` has `WA_TranslucentBackground` but is never given a visible background against the panel; chips ARE created but not visually distinguishable |
| All TinyChampIcon sprites | ❌ fallback text | Constructor never calls `_try_load_pixmap()` — shows "Jin", "Vi", "Mis" abbreviations (Bug 3) |
| All ItemIcon sprites | ❌ fallback gradient | Same constructor bug — shows green/red gradient squares instead of item art (Bug 3) |
| Augment section | ⚠️ header only | Visible at scroll bottom; augment rows use `ItemIcon` fallback for augment icons (Bug 3) |

---

## 2. Root cause analysis — 5 confirmed bugs

### Bug 1 — HP pill shows gold, not HP (`panel.py:149`)
```python
def apply_econ(self, gold: int, level: int, streak: int, interest: int):
    self.status_pills.apply(gold, level, streak, interest)
    self.title_bar.set_hp(gold)   # ← passes gold as HP
```
`apply_econ` receives gold but feeds it to the HP pill. HP is a separate stat never passed through this method. In `bindings.py`, `on_state_extracted` correctly calls `self._panel.title_bar.set_hp(hp)` separately — but then `apply_econ` overwrites that with gold.

**Fix needed:** Remove line 149 from `apply_econ`. HP should only come from `bindings.on_state_extracted`.

---

### Bug 2 — ProbCard collapses to 0 height (`ui/widgets/prob_card.py`)
`ProbCard` is a bare `QWidget` with a custom `paintEvent` but no `sizeHint()` override, no `setFixedHeight()`, no layout. Qt's default `sizeHint()` returns `(-1, -1)`, which a `QVBoxLayout` treats as 0 preferred height. The card paints correctly when given space (all paint calls are valid), but the layout never allocates any.

**Fix needed:** Add `def sizeHint(self) -> QSize: return QSize(460, 88)` (or `setFixedHeight(88)`).

---

### Bug 3 — Icons never load sprites on construction (`champ_icon.py`, `item_icon.py`)
`ChampIcon.__init__` stores `api_name` but never calls `_try_load_pixmap()`. Sprite loading only happens when `set_champion()` is called. Every `TinyChampIcon` and every `ItemIcon` is constructed with `api_name` passed to `__init__` — `set_champion()` / `set_item()` are never called after that.

This affects:
- `TinyChampIcon` in carry strip, champion row, target comp
- `ItemIcon` in carries section, augment preview

`ChampIcon` (52px hero) works only because `HeroSection.apply()` calls `self.main_champ.set_champion(api_name, cost)` after construction.

**Fix needed:** Call `self._try_load_pixmap()` at the end of `ChampIcon.__init__` when `api_name` is non-empty. Same for `ItemIcon.__init__` → `self._try_load()`.

---

### Bug 4 — Trait chips visually absent (`ui/widgets/trait_chip.py`)
`TraitChip` has `sizeHint()` and is added to the `_trait_row` layout. Chips ARE created. However `TraitChip` has `WA_TranslucentBackground` set. Its background pill uses `QColor(COLOR.bg_raised)` at alpha 180 — `bg_raised = "#24213A"`. The panel itself paints `bg_panel_rgba = (24, 22, 42, 217)`. These are near-identical dark navy values. The chip pill is nearly invisible against the panel background. Additionally the white border is only 50 alpha, making it barely perceptible.

**Fix needed:** Increase chip bg alpha to 220+, or shift `bg_raised` to a distinctly lighter value for chips, or add a more visible accent border on chips.

---

### Bug 5 — `reasoningReady` signal disconnected (`assistant_overlay.py:AppController.on_advise`)
`PipelineWorker` emits `reasoningReady(str)` (line 96, 177). The comment at line 86 says it should connect to `overlay.set_reasoning(text)`. `AuroraPanel` has no `set_reasoning()` method and `on_advise` never connects `reasoningReady`. The signal fires silently.

**Fix needed:** Either connect to `apply_warning()` as a streaming hint, or remove the signal emission from the worker.

---

## 3. Data routing gaps in live mode

These don't break the demo (demo calls `apply_*` directly) but will leave sections empty in the real F9 pipeline:

| Section | Issue |
|---|---|
| Carries (`CarriesSection`) | `on_comp_plan` and `on_final` never call `apply_carries()` — always empty in live mode |
| Augments (`AugmentPreview`) | Same — `apply_augments()` never called from bindings |
| Roll probability | `apply_probability()` never called from any binding — card empty in live mode |
| Comp traits (live) | `on_comp_plan` calls `apply_comp()` but trait tier is hardcoded `"gold"` for all — no tier differentiation |

---

## 4. Sprite cache state

| Metric | Value |
|---|---|
| Files in `~/.augie/sprites/` | 3,685 PNGs |
| `manifest.json` present | ✅ |
| Manifest structure | Dict with sections: `champions`, `items`, `traits` — **not** indexed by API name |
| `SpriteCache.get()` uses manifest | ❌ — loads directly from disk (`sprite_dir / f"{api_name}.png"`) |
| TFT17_Jinx.png | ✅ present |
| TFT17_Vi.png | ❌ missing |
| TFT17_MissFortune.png | ✅ present (in manifest) |
| TFT_Item_GuinsoosRageblade.png | ✅ present |
| TFT_Item_InfinityEdge.png | ✅ present |
| TFT_Augment_AnimaSquad1.png | ❌ missing |

Once Bug 3 is fixed, Jinx, MissFortune, Guinsoo, and Infinity Edge icons will render. Vi will remain fallback (file missing).

---

## 5. `demo_panel.py` specific issues

1. **Duplicate `"carries"` key** — FAKE_STATE defines `"carries"` twice (lines 17–20 and 46–50). Python keeps the second definition. `apply_verdict` receives the 1-item detailed carries list (correct for carry section) but the 2-item short list (line 17) intended for carry strip icons is silently discarded.

2. **`window.setLayout(QVBoxLayout())`** — called on line 72 after `AuroraPanel(window)` already set `window` as its parent. This replaces the window's layout with a fresh empty one; `window.layout().addWidget(panel)` then re-adds the panel correctly. It works, but it's a fragile sequence. The production `assistant_overlay.py` uses `_layout = QVBoxLayout(window)` which is cleaner.

---

## 6. Summary — fix priority

| Priority | Bug | File | Impact |
|---|---|---|---|
| P0 | Bug 3: Icon constructor never loads sprite | `champ_icon.py`, `item_icon.py` | Every icon shows fallback |
| P0 | Bug 2: ProbCard has no height | `prob_card.py` | Entire probability section invisible |
| P1 | Bug 4: Trait chips invisible | `trait_chip.py` | Target comp shows champs only |
| P1 | Bug 1: Gold passed as HP | `panel.py` | HP pill shows wrong data |
| P2 | Bug 5: reasoningReady disconnected | `assistant_overlay.py` | Silent signal in live mode |
| P2 | Live data routing gaps | `bindings.py` | Carries/augments/prob empty in live |
