"""Claude Opus 4.7 vision wrapper — screenshot bytes in, structured TFT game state out."""

import base64
import json
import re
from io import BytesIO

from anthropic import Anthropic
from PIL import Image

MODEL = "claude-sonnet-4-6"
PROMPT_VERSION = "v1"

# Rough pricing ($/M tokens) for Sonnet 4.6 — update if Anthropic changes rates.
# Opus 4.7 ($15 in / $75 out) costs ~5x more; we've measured $0.086/call on
# a 1280px TFT screenshot. Sonnet gives comparable structured extraction for
# ~$0.015/call, which is the economics we need for iteration.
COST_INPUT_PER_MTOK = 3.0
COST_OUTPUT_PER_MTOK = 15.0

VISION_SYSTEM_PROMPT = """You are a Teamfight Tactics (TFT) screen reader.

You will receive a screenshot of an active TFT game and must extract the game state as structured JSON.
The screenshot may be from ANY TFT set, including sets released after your training cutoff. Do not assume champion names, trait names, or item names from prior sets — read them directly from the image (portraits, tooltips, sidebar text, shop row labels).

Return ONLY valid JSON (no prose, no markdown fences) with this exact shape:

{
  "set": "<set number or name as shown in UI, or null>",
  "stage": "<X-Y>",
  "gold": <int>,
  "hp": <int>,
  "level": <int>,
  "xp": "<current>/<needed> or null",
  "streak": <int, positive for win streak, negative for loss streak, 0 for none>,
  "board": [
    {"champion": "<name as shown>", "star": <1|2|3>, "items": ["<full item name>", ...]}
  ],
  "bench": [
    {"champion": "<name as shown>", "star": <1|2|3>, "items": ["<full item name>", ...]}
  ],
  "shop": ["<champion name>", "<champion name>", ...],
  "active_traits": [
    {"trait": "<trait name as shown>", "count": <int>, "tier": "<bronze|silver|gold|prismatic|chromatic>"}
  ],
  "augments": ["<augment name>", ...],
  "visible_opponents": []
}

Rules:
- If a field is genuinely not visible or readable, use null or an empty array — never guess.
- Stage format is always "X-Y" (e.g., "3-2").
- `star` is determined by the colored border on the champion portrait (bronze=1, silver=2, gold=3).
- Item names must be the full in-game English name as it would appear in the item tooltip, not abbreviations.
- Champion and trait names must be transcribed exactly as shown in the current set's UI, even if unfamiliar.
- Output MUST be parseable by json.loads. No trailing commas, no comments, no markdown fences."""


def capture_screen() -> bytes:
    """Capture the primary monitor and return PNG bytes."""
    import mss

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor (index 0 is "all monitors combined")
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def parse_game_state(png_bytes: bytes, client: Anthropic) -> dict:
    """Send the screenshot to Claude and parse the returned JSON."""
    b64 = base64.standard_b64encode(png_bytes).decode("utf-8")

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=VISION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64},
                    },
                    {"type": "text", "text": "Extract the game state from this TFT screenshot."},
                ],
            }
        ],
    )

    raw = resp.content[0].text.strip()

    # Claude sometimes wraps JSON in ```json fences despite instructions — strip them defensively.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)

    return json.loads(raw)


def parse_and_meter(png_bytes: bytes, client: Anthropic) -> dict:
    """Same as parse_game_state but returns metadata for logging.

    Returns dict with keys: parsed, raw_text, input_tokens, output_tokens,
    cost_usd, model, prompt_version, parse_ok, error.
    """
    b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
    out = {
        "parsed": None, "raw_text": None,
        "input_tokens": None, "output_tokens": None, "cost_usd": None,
        "model": MODEL, "prompt_version": PROMPT_VERSION,
        "parse_ok": False, "error": None,
    }
    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=2048, system=VISION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "Extract the game state from this TFT screenshot."},
            ]}],
        )
        out["input_tokens"] = getattr(resp.usage, "input_tokens", None)
        out["output_tokens"] = getattr(resp.usage, "output_tokens", None)
        if out["input_tokens"] is not None and out["output_tokens"] is not None:
            out["cost_usd"] = round(
                out["input_tokens"] / 1_000_000 * COST_INPUT_PER_MTOK
                + out["output_tokens"] / 1_000_000 * COST_OUTPUT_PER_MTOK,
                4,
            )
        raw = resp.content[0].text.strip()
        out["raw_text"] = raw
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
        if fence:
            raw = fence.group(1)
        out["parsed"] = json.loads(raw)
        out["parse_ok"] = True
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out
