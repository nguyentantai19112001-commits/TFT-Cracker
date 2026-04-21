"""Design tokens for the Augie Aurora UI.

Every color, size, spacing value, radius, animation duration in the UI
must reference one of these namespaces. Never inline hex codes or pixel
values in widget code.
"""
from __future__ import annotations
from types import SimpleNamespace


# ─── Colors ─────────────────────────────────────────────────────────────

COLOR = SimpleNamespace(
    # Backgrounds
    bg_panel_rgba=(24, 22, 42, 217),       # 0.85 alpha — main panel
    bg_panel_solid="#181629",              # fallback on non-Mica systems
    bg_raised="#24213A",                   # raised rows, cards
    bg_input="#13111F",                    # deepest surfaces

    # Borders
    border_subtle_rgba=(255, 255, 255, 20),   # 0.08 alpha
    border_hover_rgba=(255, 255, 255, 38),    # 0.15 alpha
    border_accent="#FF89C8",                  # aurora pink

    # Text
    text_primary="#F0EEF8",
    text_secondary="#C5C0E0",
    text_tertiary="#b4adcd",
    text_muted="#8A86A8",      # bumped from #6D6893 for 4.5:1 contrast on dark bg
    text_disabled="#413E5C",

    # Semantic (priority/state)
    accent_pink="#FF89C8",
    accent_pink_soft_rgba=(255, 137, 200, 46),     # 0.18 alpha bg
    accent_blue="#7AB4FF",
    accent_blue_soft_rgba=(122, 180, 255, 36),     # 0.14 alpha bg
    accent_gold="#FFC889",
    accent_gold_soft_rgba=(255, 200, 137, 38),
    accent_green="#7AFFB4",
    accent_green_soft_rgba=(122, 255, 180, 26),
    accent_purple="#B48CFF",
    accent_red="#FF8BA3",
    accent_red_soft_rgba=(255, 137, 137, 36),

    # Cost colors for champion borders (match TFT in-game palette)
    cost_1="#9AA3B0",          # gray
    cost_2="#7AFFB4",          # green
    cost_3="#7AB4FF",          # blue
    cost_4="#C77AB0",          # purple
    cost_5="#FFD27A",          # gold
    cost_hero="#FFA058",       # unique hero / augment-exclusive

    # Item category gradients (used when sprite fails to load)
    item_ad_from="#E8533B",        # BF Sword family
    item_ad_to="#9C2A1A",
    item_ap_from="#6BADFF",        # Rod family
    item_ap_to="#2A4A9C",
    item_mana_from="#7ADCFF",      # Tear family
    item_mana_to="#2A6A9C",
    item_as_from="#8CD88A",        # Recurve Bow family
    item_as_to="#3A7A3A",
    item_armor_from="#C090F0",     # Cloak family
    item_armor_to="#5A3A9C",
    item_hp_from="#E8C95A",        # Giant's Belt family
    item_hp_to="#9C7A1A",

    # Econ chip icon tile gradients (Change 3)
    econ_gold_from="#FFD27A",
    econ_gold_to="#FF9454",
    econ_level_from="#7AB4FF",
    econ_level_to="#5A7AC7",
    econ_streak_from="#7AFFB4",
    econ_streak_to="#4ACE90",
    econ_interest_from="#C090F0",
    econ_interest_to="#8A60C8",
)


# ─── Spacing (4px grid) ─────────────────────────────────────────────────

SPACE = SimpleNamespace(
    xxs=2, xs=4, sm=8, md=12, lg=16, xl=20, xxl=28, xxxl=40,
)


# ─── Radii ──────────────────────────────────────────────────────────────

RADIUS = SimpleNamespace(
    pill=999,
    item_icon=5,
    champ_icon=6,
    chip=20,
    row=14,
    card=16,
    panel=22,
)


# ─── Sizes ──────────────────────────────────────────────────────────────

SIZE = SimpleNamespace(
    # Panel (Change 1)
    panel_width=640,
    panel_min_height=420,
    panel_expanded_height=880,
    panel_max_height=1040,

    # Title bar / chrome
    title_bar_height=56,
    chrome_btn=24,
    chrome_btn_radius=7,

    # Hero section
    hero_champ=52,
    hero_champ_radius=14,

    # Inline icons
    icon_champ_tiny=20,
    icon_item=20,
    icon_trait_sym=18,
    icon_mini_item=16,

    # Action rows
    action_icon=32,
    action_icon_radius=10,
    action_row_min_height=54,
    action_row_padding_v=11,
    action_row_padding_h=14,

    # Probability card
    prob_card_padding_v=14,
    prob_card_padding_h=16,
    prob_bar_height=6,

    # HP pill
    hp_pill_padding_v=7,
    hp_pill_padding_h=16,

    # Econ chips (Change 3)
    econ_chip_height=44,
    econ_icon_tile=28,
)


# ─── Fonts ──────────────────────────────────────────────────────────────

FONT = SimpleNamespace(
    family_ui="Inter, 'Segoe UI', system-ui, sans-serif",
    family_mono="'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
    family_display="Orbitron, 'Segoe UI', system-ui, sans-serif",

    size_header_title=18,
    size_header_subtitle=11,
    size_hero_verdict=19,
    size_verdict_subtitle=13,
    size_section_label=11,
    size_verdict_headline=22,
    size_body=12,
    size_body_small=11,
    size_row_title=13,
    size_row_subtitle=11,
    size_badge=11,
    size_footer=10,
    size_metric=24,
    size_hero_glyph=26,

    weight_regular=400,
    weight_medium=500,
    weight_semibold=600,
    weight_bold=700,
    weight_extra=800,

    letter_spacing_caps=1.8,
)


# ─── Motion ─────────────────────────────────────────────────────────────

MOTION = SimpleNamespace(
    fast=120,
    medium=220,
    slow=320,
    pulse=1400,
    spring=280,

    ease_out="OutCubic",
    ease_in_out="InOutCubic",
    ease_spring="OutBack",
    ease_elastic="OutElastic",
)


# ─── Shadows (Change 2) ─────────────────────────────────────────────────

SHADOW = SimpleNamespace(
    # Elevation tiers — passed to ui.fx.apply_shadow(widget, spec)
    elev_panel=dict(blur=60, dy=20, alpha=140, color="#000000"),
    elev_card =dict(blur=28, dy=10, alpha=90,  color="#000000"),
    elev_row  =dict(blur=14, dy=4,  alpha=60,  color="#000000"),
    elev_chip =dict(blur=6,  dy=2,  alpha=45,  color="#000000"),

    # Colored accent glows
    glow_hero =dict(blur=36, dy=0,  alpha=110, color="#FF9454"),
    glow_gold =dict(blur=20, dy=0,  alpha=80,  color="#FFD27A"),
    glow_pink =dict(blur=24, dy=0,  alpha=70,  color="#FF89C8"),
)


# ─── Z-order layers ─────────────────────────────────────────────────────

Z = SimpleNamespace(
    base=0,
    backdrop=10,
    content=20,
    overlay_tooltip=30,
    dropdown=40,
    modal=50,
)
