# Third-Party Notices

This project adapts code and techniques from the following open-source projects.

## TFT-OCR-BOT

- **Source:** https://github.com/jfd02/TFT-OCR-BOT
- **License:** GNU General Public License v3.0
- **Local copy:** `_unused_reference/TFT-OCR-BOT/` (unmodified)

Files in this project that are direct copies or derivatives:
- `vec2.py` — direct copy (geometry primitive)
- `vec4.py` — direct copy (geometry primitive)
- `screen_coords.py` — direct copy (1920x1080 UI coordinate schema)
- `ocr.py` — rewritten using pytesseract instead of tesserocr; pipeline approach adapted
- `ocr_helpers.py` — reimplementation of LCU API calls, fuzzy-match helpers, and threaded shop reader patterns
- `round_reader.py` — reimplementation of `game_functions.get_round` pattern

As this project incorporates GPLv3-licensed code, the combined work is also
licensed under GPLv3. See `LICENSE`.

## Tesseract OCR

- **Source:** https://github.com/tesseract-ocr/tesseract
- **License:** Apache 2.0
- The binary must be installed separately on Windows from
  https://github.com/UB-Mannheim/tesseract/wiki before OCR will function.

## Community Dragon

- **Source:** https://www.communitydragon.org/
- Public mirror of Riot's game data. Not a code dependency — used at runtime
  by `data/fetch_community_dragon.py` for current-set champion/item/trait data.
