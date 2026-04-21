"""Thin translation layer: pipeline dicts → AuroraPanel apply_* calls.

Usage (in assistant_overlay.py AppController):
    from ui.bindings import Bindings
    self.bindings = Bindings(aurora_panel)
    worker.stateExtracted.connect(self.bindings.on_state_extracted)
    worker.compPlanReady.connect(self.bindings.on_comp_plan)
    worker.verdictReady.connect(self.bindings.on_verdict_ready)
    worker.finalReady.connect(self.bindings.on_final)
    worker.errorOccurred.connect(self.bindings.on_error)
    worker.extractingStarted.connect(self.bindings.on_extracting)
"""
from __future__ import annotations
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.panel import AuroraPanel

# ActionType → (glyph, aurora-priority, ui.tokens accent color)
_ACTION_META: dict[str, tuple[str, str, str]] = {
    "BUY":        ("◎", "high",   "#FF89C8"),
    "SELL":       ("✕", "medium", "#FF8BA3"),
    "ROLL_TO":    ("↓", "high",   "#FF89C8"),
    "LEVEL_UP":   ("↑", "medium", "#7AB4FF"),
    "HOLD_ECON":  ("◈", "low",    "#FFC889"),
    "SLAM_ITEM":  ("⚙", "medium", "#B48CFF"),
    "PIVOT_COMP": ("⇄", "high",   "#7AFFB4"),
}

# AdvisorVerdict.tempo_read → AuroraPanel verdict key (HeroSection._VERDICT_STYLES keys)
_TEMPO_TO_VERDICT: dict[str, str] = {
    "AHEAD":    "strong_buy",
    "ON_PACE":  "hold",
    "BEHIND":   "buy",
    "CRITICAL": "sell",
}


class Bindings:
    """Wires PipelineWorker signals to AuroraPanel.apply_* calls."""

    def __init__(self, panel: "AuroraPanel") -> None:
        self._panel = panel
        self._t0: float = 0.0

    def on_extracting(self) -> None:
        self._t0 = time.time()
        self._panel.apply_warning("Extracting…", visible=True)

    def on_state_extracted(self, state_dict: dict) -> None:
        self._panel.apply_warning("", visible=False)
        stage  = state_dict.get("stage") or "—"
        gold   = int(state_dict.get("gold") or 0)
        hp     = int(state_dict.get("hp") or 100)
        level  = int(state_dict.get("level") or 1)
        streak = int(state_dict.get("streak") or 0)
        interest = min(5, gold // 10)
        self._panel.apply_stage(stage)
        self._panel.apply_econ(gold, level, streak, interest)
        self._panel.title_bar.set_hp(hp)

        # FIX 2.A — carries from live board units that are holding items
        board = state_dict.get("board") or []
        carries = []
        for unit in board:
            items = unit.get("items") or []
            if not items:
                continue
            champ = unit.get("champion") or unit.get("name") or ""
            carries.append({
                "name": champ.split("_")[-1] if "_" in champ else champ,
                "api_name": champ,
                "cost": _cost_for(champ),
                "items": [{"api_name": it, "category": _item_category(it)} for it in items],
            })
        self._panel.apply_carries(carries)

        # FIX 2.B — active augments from state
        augments = state_dict.get("augments") or []
        self._panel.apply_augments([
            {
                "name": _aug_display_name(a),
                "api_name": a,
                "tier": "silver",  # tier not extracted by vision yet; see DATA_GAPS.md
            }
            for a in augments
        ])

    def on_comp_plan(self, comps: list[dict]) -> None:
        if not comps:
            return
        best = comps[0]
        arch = best.get("archetype") or {}

        # FIX 2.D — tier differentiation: map comp tier to chip tier
        # Trait breakpoint tier data not available here; use comp power tier as proxy.
        # TODO: wire actual trait breakpoint tiers when knowledge/set_17.yaml exposes them.
        arch_tier = arch.get("tier", "B")
        chip_tier = "gold" if arch_tier in ("S", "A") else ("silver" if arch_tier == "B" else "bronze")

        traits = [
            {
                "name": t[0] if isinstance(t, (list, tuple)) else str(t),
                "tier": chip_tier,
                "active": True,
            }
            for t in (arch.get("required_traits") or [])[:6]
        ]
        champions = [
            {"api_name": c, "cost": _cost_for(c), "name": c.split("_")[-1]}
            for c in (arch.get("core_units") or [])[:9]
        ]
        self._panel.apply_comp(traits, champions)

        # FIX 2.C — probability: show comp reach probability on the ProbCard
        p_reach = best.get("p_reach") or 0.0
        missing = best.get("missing_units") or []
        display_name = arch.get("display_name") or arch.get("archetype_id") or "Target comp"
        self._panel.apply_probability(
            p_reach,
            label=f"Reach: {display_name}",
            sublabel=f"{len(missing)} unit(s) still needed" if missing else "All core units on board",
        )

    def on_verdict_ready(self, one_liner: str) -> None:
        """Streaming one-liner arrives before final — show as warning hint."""
        self._panel.apply_warning(one_liner, visible=True)

    def on_final(
        self,
        rec: dict,
        meta: dict,
        wall_s: float,
        vision_cost: float,
        game_id,
    ) -> None:
        self._panel.apply_warning("", visible=False)

        tempo   = rec.get("tempo_read", "ON_PACE")
        verdict = _TEMPO_TO_VERDICT.get(tempo, "hold")
        chosen  = rec.get("chosen_candidate") or {}
        action_type = (chosen.get("action_type") or "HOLD_ECON")
        params  = chosen.get("params") or {}

        champ_api  = params.get("champion") or ""
        champ_name = champ_api.split("_")[-1] if champ_api else "Board"
        cost       = _cost_for(champ_api)

        self._panel.apply_verdict(verdict, champ_name, champ_api, cost, carries=[])

        # Actions from considerations list + chosen candidate
        actions = [_action_to_row(rec, chosen)]
        for note in (rec.get("considerations") or [])[:2]:
            actions.append({
                "headline": note[:80],
                "subline": "",
                "score": 0,
                "priority": "low",
                "glyph": "→",
                "color": "#7AB4FF",
            })
        self._panel.apply_actions(actions)

        warns = rec.get("warnings") or []
        if warns:
            self._panel.apply_warning(warns[0], visible=True)

        ms = int(wall_s * 1000)
        self._panel.apply_latency(ms)

    def on_error(self, msg: str) -> None:
        self._panel.apply_warning(f"Error: {msg}", visible=True)
        self._panel.apply_latency(None)


def _action_to_row(verdict: dict, candidate: dict) -> dict:
    action_type = (candidate.get("action_type") or "HOLD_ECON")
    glyph, priority, color = _ACTION_META.get(action_type, ("→", "medium", "#7AB4FF"))
    summary = candidate.get("human_summary") or verdict.get("one_liner") or action_type
    scores  = candidate.get("scores") or {}
    total   = candidate.get("total_score") or 0.0
    return {
        "headline": summary[:80],
        "subline": ", ".join(
            f"{k}={v:+.1f}"
            for k, v in scores.items()
            if isinstance(v, (int, float)) and v != 0
        )[:60],
        "score": round(abs(total) * 10),
        "priority": priority,
        "glyph": glyph,
        "color": color,
    }


def _item_category(api_name: str) -> str:
    """Best-effort item category from API name — used for fallback gradient color."""
    n = api_name.lower()
    if any(x in n for x in ["bfsword", "infinity", "bloodthirster", "deathblade", "rapidfire", "lastwhisper", "giantslayer", "steraks", "dclaw"]):
        return "ad"
    if any(x in n for x in ["needlesslylargerod", "rabadon", "archangel", "shojin", "jeweled", "spear", "morello", "shadowflame"]):
        return "ap"
    if any(x in n for x in ["recurvebow", "guinsoo", "nashor", "runaan", "statikk", "kraken"]):
        return "as"
    if any(x in n for x in ["chainvest", "bramble", "gargoyle", "sunfire", "redemption", "locketiron"]):
        return "armor"
    if any(x in n for x in ["giantsbelt", "warmog", "zeke", "titans", "ionic"]):
        return "hp"
    if any(x in n for x in ["tear", "manamune", "bluebuff", "spellbinder"]):
        return "mana"
    return "ap"  # fallback


def _aug_display_name(api_name: str) -> str:
    """Convert augment API name to a readable display name (best-effort)."""
    # Strip prefixes: TFT_Augment_AnimaSquadHeart → AnimaSquadHeart
    name = api_name
    for prefix in ("TFT_Augment_", "TFT17_Augment_", "Set17_Augment_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    # CamelCase → "Camel Case"
    import re
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def _cost_for(champ_name: str) -> int:
    """Best-effort cost lookup from knowledge set; falls back to 1.

    Accepts display names ("Jinx") — that's what BoardUnit.champion stores.
    """
    try:
        import sys
        from pathlib import Path
        _engine = Path(__file__).resolve().parents[1] / "engine"
        if str(_engine) not in sys.path:
            sys.path.insert(0, str(_engine))
        from knowledge import load_set
        set_ = load_set("17")
        for c in set_.champions:
            if c.get("name") == champ_name:
                return int(c.get("cost") or 1)
    except Exception:
        pass
    return 1
