"""Quick visual smoke-test: launch the Aurora panel with fake data."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from ui.chrome.frameless_window import AugieFrameless
from ui.panel import AuroraPanel

FAKE_STATE = {
    "verdict": "buy",
    "champ_name": "Jinx",
    "champ_api": "TFT17_Jinx",
    "cost": 3,
    "gold": 47,
    "level": 7,
    "streak": 2,
    "interest": 4,
    "prob": 0.38,
    "prob_label": "Jinx 3★ this round",
    "prob_sublabel": "11 copies seen · 9 in pool",
    "traits": [
        {"name": "Anima Squad", "tier": "gold", "active": True},
        {"name": "Challenger", "tier": "silver", "active": True},
        {"name": "Sniper", "tier": "bronze", "active": False},
    ],
    "champions": [
        {"api_name": "TFT17_Jinx", "cost": 3},
        {"api_name": "TFT17_Vi", "cost": 2},
        {"api_name": "TFT17_MissFortune", "cost": 4},
    ],
    "actions": [
        {"headline": "Roll down — hit Jinx 3★", "subline": "38% chance per shop",
         "score": 92, "priority": "high", "glyph": "↓", "color": "#FF89C8"},
        {"headline": "Hold gold for level 8", "subline": "4 interest next round",
         "score": 71, "priority": "medium", "glyph": "◈", "color": "#FFC889"},
        {"headline": "Swap Recurve → Guinsoo", "subline": "+18 DPS on Jinx",
         "score": 58, "priority": "low", "glyph": "⚙", "color": "#7AB4FF"},
    ],
    "carries": [
        {"name": "Jinx", "api_name": "TFT17_Jinx", "cost": 3,
         "items": [{"api_name": "TFT_Item_GuinsoosRageblade", "category": "as"},
                   {"api_name": "TFT_Item_InfinityEdge", "category": "ad"}]},
    ],
    "augments": [
        {"name": "Anima Squad Heart", "api_name": "TFT_Augment_AnimaSquad1", "tier": "silver"},
        {"name": "Recon Mission II",   "api_name": "TFT_Augment_ReconMission2", "tier": "gold"},
    ],
    "stage": "4-2",
    "latency_ms": 320,
}


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Augie Demo")

    window = AugieFrameless()
    panel = AuroraPanel(window)

    # Wire title bar buttons
    panel.title_bar.minimize_clicked.connect(window.showMinimized)
    panel.title_bar.close_clicked.connect(app.quit)
    panel.title_bar.pin_toggled.connect(window.set_pinned)

    window.setLayout(__import__("PyQt6.QtWidgets", fromlist=["QVBoxLayout"]).QVBoxLayout())
    window.layout().setContentsMargins(0, 0, 0, 0)
    window.layout().addWidget(panel)

    s = FAKE_STATE
    panel.apply_stage(s["stage"])
    panel.apply_verdict(s["verdict"], s["champ_name"], s["champ_api"], s["cost"], s["carries"])
    panel.apply_econ(s["gold"], s["level"], s["streak"], s["interest"])
    panel.apply_probability(s["prob"], label=s["prob_label"], sublabel=s["prob_sublabel"])
    panel.apply_comp(s["traits"], s["champions"])
    panel.apply_actions(s["actions"])
    panel.apply_carries(s["carries"])
    panel.apply_augments(s["augments"])
    panel.apply_latency(s["latency_ms"])

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
