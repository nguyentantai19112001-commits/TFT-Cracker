# SCHEMA_REPORT.md — Set 17 CDragon Schema Verification

## Fetched

- URL: `https://raw.communitydragon.org/latest/cdragon/tft/en_us.json`
- Sets present: `1, 3, 4, 5, 7, 13, 14, 15, 16, 17`
- Fetched: 2026-04-21
- **Note**: The spec pinned `/17.1/` — that URL 404s. CDragon uses LoL patch version numbers,
  not TFT set numbers. `/latest/` contains Set 17 data; the spec's claim that it returns
  Set 13 was incorrect.

## Set number confirmation

- `data["sets"]` keys: `['1', '3', '4', '5', '7', '13', '14', '15', '16', '17']`
- Active set: **"17" present** — 82 champions

## Champion schema (sample: `TFT17_Jinx`)

```
apiName        str   = 'TFT17_Jinx'
characterName  str   = 'TFT17_Jinx'
name           str   = 'Jinx'
cost           int   = 2
role           str   = 'ADCarry'
traits         list  = ['Anima', 'Challenger']
icon           str   = 'ASSETS/Characters/TFT17_Jinx/Skins/Base/Images/TFT17_Jinx_splash_centered_38.TFT_Set17.tex'
squareIcon     str   = 'ASSETS/Characters/TFT17_Jinx/Skins/Base/Images/TFT17_Jinx_splash_tile_38.TFT_Set17.tex'
tileIcon       str   = 'ASSETS/Characters/TFT17_Jinx/HUD/TFT17_Jinx_Square.TFT_Set17.tex'
ability        dict  = { desc, icon, name, variables }
stats          dict  = { armor, attackSpeed, critChance, hp, mana, ... }
```

### Icon field for champions

- Best field for UI grid: **`tileIcon`** (compact HUD square, consistent across all champs)
- Fallback: `squareIcon` (splash tile, larger)
- Avoid: `icon` (full splash art, large and inconsistently cropped)
- Example value: `ASSETS/Characters/TFT17_Jinx/HUD/TFT17_Jinx_Square.TFT_Set17.tex`
- Transform → URL: `https://raw.communitydragon.org/latest/game/assets/characters/tft17_jinx/hud/tft17_jinx_square.tft_set17.png`
- Test fetch: **HTTP 200**

### Traits on champions

`traits` is a list of display-name strings (e.g. `["Anima", "Challenger"]`), directly
matching the names used in `engine/knowledge/set_17.yaml`. No further mapping needed.

## Item schema

- Total items in `data["items"]`: **3565** (includes all sets, all types)
- Components: **14** (filter: `'component' in item["tags"]`)
- Completed: filtered by `len(item["composition"]) == 2` (composition holds two component apiNames)
- Augments: **1627** (filter: `'_Augment_' in item["apiName"]`)

### Critical schema difference from spec

The spec expected a `from` array with component IDs. **`from` is always `null`.**
The correct field is **`composition`** — it holds a list of component `apiName` strings.
Example for Infinity Edge: `composition: ["TFT_Item_BFSword", "TFT_Item_SparringGloves"]`.
Items with `len(composition) == 2` are completed items. Items with `len(composition) == 0`
and `'component' in tags` are base components.

### Component icon (sample: `TFTTutorial_Item_RecurveBow`)

```
apiName  = 'TFTTutorial_Item_RecurveBow'
name     = 'Recurve Bow'
icon     = 'ASSETS/Maps/Particles/TFT/Item_Icons/Standard/Recurve_Bow.tex'
tags     = ['component']
```

- Transform → URL: `https://raw.communitydragon.org/latest/game/assets/maps/particles/tft/item_icons/standard/recurve_bow.png`
- Test fetch: **HTTP 200**

### Completed item icon (sample: `TFT_Item_InfinityEdge`)

```
apiName      = 'TFT_Item_InfinityEdge'
name         = "Infinity Edge"
icon         = 'ASSETS/Maps/TFT/Icons/Items/Hexcore/TFT_Item_InfinityEdge.TFT_Set13.tex'
composition  = ['TFT_Item_BFSword', 'TFT_Item_SparringGloves']
```

- Transform → URL: `https://raw.communitydragon.org/latest/game/assets/maps/tft/icons/items/hexcore/tft_item_infinityedge.tft_set13.png`
- Test fetch: **HTTP 200**

### Augment icon (sample: `TFT17_Augment_EkkoGodAugment`)

```
apiName = 'TFT17_Augment_EkkoGodAugment'
name    = "Ekko's Boon"
icon    = 'ASSETS/Maps/TFT/Icons/Augments/Hexcore/GodAugmentEkko_II.TFT_Set17.tex'
```

- Transform → URL: `https://raw.communitydragon.org/latest/game/assets/maps/tft/icons/augments/hexcore/godaugmentekko_ii.tft_set17.png`
- Test fetch: **HTTP 200**

## URL transform rule (confirmed)

```
step 1: lowercase the entire path
step 2: replace .tex extension with .png
step 3: prepend https://raw.communitydragon.org/latest/game/
```

Applies identically to champions, components, completed items, and augments.

## Jinx verification

- Jinx in Set 17: **YES**
- `apiName = "TFT17_Jinx"`, `cost = 2`, `traits = ["Anima", "Challenger"]`
- **Gotcha**: Jinx is cost **2**, not a premium flagship carry. The mockup's implied
  "flagship unit" framing is misleading. She's a mid-tier carry. If the UI needs a
  showcase unit, a cost-4 or cost-5 is more representative.

## Known gotchas

1. **Spec's `/17.1/` URL 404s.** CDragon versions are LoL patch numbers (e.g. `14.24`,
   `15.1`, `16.1`), not TFT set numbers. Use `/latest/` — it serves Set 17 data.
2. **`from` field is always `null`.** The spec's item-filter code using `item.get("from")`
   is broken. Use `item["composition"]` to identify completed items.
3. **No `tags: ["completed"]` exists.** The only tag-based filter that works is
   `"component" in tags` for base components. Everything else requires checking `composition`.
4. **3565 items span all historical sets** — augments from Set 13, 14, 15, 16, 17 all coexist.
   Filter by `TFT17` in `apiName` if you only want Set 17 augments.
5. **`tileIcon` is the right field for UI**, not `icon` (splash) or `squareIcon` (tile splash).

## Ready for Phase 1?

**YES**

- All 4 test fetches returned HTTP 200
- Champion icon field identified: `tileIcon` → `.tex→.png` transform → 200 OK
- Item icon field identified: `icon` → `.tex→.png` transform → 200 OK
- Augment icon field identified: `icon` → `.tex→.png` transform → 200 OK
- Completed item recipe field: `composition` (not `from`)
- Transform rule confirmed working for all 4 asset classes
