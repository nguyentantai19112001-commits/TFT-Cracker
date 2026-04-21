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
        stage = state_dict.get("stage") or "—"
        gold  = int(state_dict.get("gold") or 0)
        hp    = int(state_dict.get("hp") or 100)
        level = int(state_dict.get("level") or 1)
        streak = int(state_dict.get("streak") or 0)
        interest = min(5, gold // 10)
        self._panel.apply_stage(stage)
        self._panel.apply_econ(gold, level, streak, interest)
        # Show hp on title bar pill
        self._panel.title_bar.set_hp(hp)

    def on_comp_plan(self, comps: list[dict]) -> None:
        if not comps:
            return
        best = comps[0]
        traits = [
            {"name": t, "tier": "gold", "active": True}
            for t in (best.get("traits") or [])[:6]
        ]
        champions = [
            {"api_name": c, "cost": _cost_for(c), "name": c}
            for c in (best.get("champions") or [])[:9]
        ]
        self._panel.apply_comp(traits, champions)

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


def _cost_for(api_name: str) -> int:
    """Best-effort cost lookup from sprites manifest; falls back to 1."""
    try:
        import json
        from engine.sprites import manifest_path
        data = json.loads(manifest_path.read_text())
        entry = data.get(api_name) or {}
        return entry.get("cost") or 1
    except Exception:
        return 1
