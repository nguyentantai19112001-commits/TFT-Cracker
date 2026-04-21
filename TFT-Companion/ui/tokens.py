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
    text_tertiary="#A8A3C8",
    text_muted="#6D6893",
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
    # Panel
    panel_width=500,
    panel_min_height=320,
    panel_expanded_height=680,
    panel_max_height=820,

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
    hp_pill_padding_v=6,
    hp_pill_padding_h=12,
)


# ─── Fonts ──────────────────────────────────────────────────────────────

FONT = SimpleNamespace(
    family_ui="Inter, 'Segoe UI', system-ui, sans-serif",
    family_mono="'JetBrains Mono', 'Cascadia Code', Consolas, monospace",

    size_header_title=15,
    size_header_subtitle=11,
    size_hero_verdict=19,
    size_verdict_subtitle=13,
    size_section_label=10,
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


# ─── Shadows ────────────────────────────────────────────────────────────

SHADOW = SimpleNamespace(
    panel_blur=40,
    panel_dy=8,
    panel_alpha=140,

    row_blur=12,
    row_dy=2,
    row_alpha=90,

    hero_glow_blur=20,
    hero_glow_alpha=100,
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
