"""Standalone demo launcher — feeds fixtures through the v3 orchestrator."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ENGINE = ROOT / "engine"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE))

from PyQt6.QtWidgets import QApplication, QVBoxLayout
from ui.chrome.frameless_window import AugieFrameless
from ui.panel import AuroraPanel
from ui.bindings import Bindings
from engine.agents.orchestrator import CoachOrchestrator, AgentContext

_ORCHESTRATOR = CoachOrchestrator()

# board entries: (api_name, star, items_held)
FIXTURES = {
    "early": dict(
        stage=(2, 3), hp=95, gold=22, level=4, streak=0,
        board=[("TFT17_Annie", 1, [])],
        bench_components=[],
    ),
    "mid": dict(
        stage=(3, 5), hp=68, gold=50, level=6, streak=2,
        board=[
            ("TFT17_Vi", 2, ["JG"]),
            ("TFT17_Jinx", 1, ["AS"]),
            ("TFT17_Ziggs", 1, []),
            ("TFT17_Seraphine", 1, []),
            ("TFT17_Rumble", 1, ["BF"]),
            ("TFT17_Sona", 1, []),
        ],
        bench_components=["Rod", "Glove"],
    ),
    "late": dict(
        stage=(4, 2), hp=62, gold=56, level=8, streak=3,
        board=[
            ("TFT17_Vex", 2, ["JG", "AS"]),
            ("TFT17_Blitzcrank", 2, []),
            ("TFT17_Rammus", 1, []),
            ("TFT17_Karma", 1, []),
            ("TFT17_Mordekaiser", 2, ["Redemption"]),
        ],
        bench_components=["Rod", "Rod", "BF", "Glove"],
    ),
    "dying": dict(
        stage=(4, 7), hp=14, gold=8, level=7, streak=-4,
        board=[
            ("TFT17_Jinx", 1, []),
            ("TFT17_Vi", 1, []),
            ("TFT17_MissFortune", 1, []),
        ],
        bench_components=[],
    ),
}

_COST_HINTS: dict[str, int] = {
    "TFT17_Annie": 1, "TFT17_Jinx": 3, "TFT17_Vi": 2,
    "TFT17_Ziggs": 2, "TFT17_Seraphine": 3, "TFT17_Rumble": 2, "TFT17_Sona": 4,
    "TFT17_Vex": 4, "TFT17_Blitzcrank": 3, "TFT17_Rammus": 2,
    "TFT17_Karma": 4, "TFT17_Mordekaiser": 5, "TFT17_MissFortune": 5,
}


def build_demo_state(
    stage: tuple[int, int],
    hp: int,
    gold: int,
    level: int,
    streak: int,
    board: list,
    bench_components: list,
) -> AgentContext:
    board_slots = [
        {
            "api_name": api,
            "display_name": api.split("_")[-1] if "_" in api else api,
            "cost": _COST_HINTS.get(api, 1),
            "star": star,
            "items_held": list(items),
            "bis_trios": [],
            "value_class": "B",
        }
        for api, star, items in board
    ]
    return AgentContext(
        hp=hp,
        gold=gold,
        level=level,
        stage=stage,
        streak=streak,
        interest_tier=min(5, gold // 10),
        board_strength=0.5,
        board_slots=board_slots,
        bench_components=list(bench_components),
        augments_picked=[],
        augment_tiers=[],
        target_comp_apis=[],
        active_items={},
    )


def main(fixture_name: str = "late") -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Augie Demo")

    fixture = FIXTURES[fixture_name]
    ctx = build_demo_state(**fixture)

    print(f"[demo] Running orchestrator for fixture '{fixture_name}'...")
    result = _ORCHESTRATOR.run_sync(ctx)
    tempo_safe = result.tempo.verdict_display.encode("ascii", "replace").decode("ascii")
    print(f"[demo] frame={result.frame.game_tag}  tempo={tempo_safe!r}")

    window = AugieFrameless()
    panel = AuroraPanel(window)
    bindings = Bindings(panel)

    panel.title_bar.minimize_clicked.connect(window.showMinimized)
    panel.title_bar.close_clicked.connect(app.quit)
    panel.title_bar.pin_toggled.connect(window.set_pinned)

    lay = QVBoxLayout()
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(panel)
    window.setLayout(lay)

    # Stage + HP not included in CoachResult — set from fixture directly
    stage = fixture["stage"]
    panel.apply_stage(f"{stage[0]}-{stage[1]}")
    panel.title_bar.set_hp(fixture["hp"])

    # All 9 panel sections populated via bindings
    bindings.on_coach_result(result)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    fixture = sys.argv[1] if len(sys.argv) > 1 else "late"
    main(fixture)
