"""Calibrate OCR coords against a real Set 17 1920x1080 screenshot.

Crops the two regions we actually need (gold, round), saves them to disk
for eyeball-verification, and runs Tesseract on each one.

No API cost.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

import ocr
from screen_coords import GOLD_POS, ROUND_POS


def crop(img: Image.Image, bbox) -> Image.Image:
    x1, y1, x2, y2 = bbox.get_coords()
    return img.crop((x1, y1, x2, y2))


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "test_screenshot_en.png")
    if not path.exists():
        print(f"ERROR: {path} not found")
        return 1

    img = Image.open(path)
    print(f"Image: {path} ({img.size})")
    if img.size != (1920, 1080):
        print("WARN: not 1920x1080 — coords won't match")

    out_dir = Path("calibration_crops")
    out_dir.mkdir(exist_ok=True)

    # Current (reference-repo) coords
    gold_crop = crop(img, GOLD_POS)
    gold_crop.save(out_dir / "gold.png")
    gold_text = ocr.get_text_from_image(gold_crop, psm=7, whitelist="0123456789")
    print(f"  GOLD  {GOLD_POS.get_coords()} -> '{gold_text}'")

    round_crop = crop(img, ROUND_POS)
    round_crop.save(out_dir / "round.png")
    round_text = ocr.get_text_from_image(round_crop, psm=7, whitelist="0123456789-")
    print(f"  ROUND {ROUND_POS.get_coords()} -> '{round_text}'")

    # Candidate Set-17 coords — based on visual inspection of test screenshot
    candidates = {
        "gold_wide":   (900, 905, 1020, 950),   # center-bottom, "40"
        "round_wide":  (850, 5,   950, 45),     # top-center, "2-8"
        "level_wide":  (280, 880, 380, 925),    # bottom-left, "Lvl. 8"
        "xp_wide":     (370, 880, 460, 925),    # bottom-left, "4/68"
        "gold_v3":     (950, 910, 1000, 945),
        "round_v3":    (870, 10, 920, 40),
    }

    print("\n-- Candidate Set-17 coords --")
    for name, (x1, y1, x2, y2) in candidates.items():
        c = img.crop((x1, y1, x2, y2))
        c.save(out_dir / f"{name}.png")
        whitelist = "0123456789-/"
        txt = ocr.get_text_from_image(c, psm=7, whitelist=whitelist)
        print(f"  {name:10s} ({x1},{y1})-({x2},{y2}) -> '{txt}'")

    print(f"\nCrops saved to {out_dir}/ — open them to verify tight bounding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
