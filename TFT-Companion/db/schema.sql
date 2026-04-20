-- Augie logging database schema.
-- Feeds the feedback loop and future ML training dataset.

CREATE TABLE IF NOT EXISTS games (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time        TIMESTAMP,
    set_id          TEXT,
    patch_version   TEXT,
    queue_type      TEXT,
    final_placement INTEGER,
    notes           TEXT
);

-- One row per screenshot captured. The image itself is stored on disk (JPEG
-- q85, max 1280px wide) under captures/ — the DB holds only the path + hash.
CREATE TABLE IF NOT EXISTS captures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER REFERENCES games(id) ON DELETE CASCADE,
    captured_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    file_path       TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    width           INTEGER NOT NULL,
    height          INTEGER NOT NULL,
    bytes_on_disk   INTEGER NOT NULL,
    trigger         TEXT  -- e.g., "hotkey", "round_change", "test"
);

CREATE INDEX IF NOT EXISTS idx_captures_game_id ON captures(game_id);
CREATE INDEX IF NOT EXISTS idx_captures_sha     ON captures(sha256);

-- One row per parsed game state (merged from LCU + Vision + templates).
CREATE TABLE IF NOT EXISTS game_states (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    capture_id      INTEGER REFERENCES captures(id) ON DELETE SET NULL,
    captured_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stage           TEXT,
    gold            INTEGER,
    hp              INTEGER,
    level           INTEGER,
    xp_current      INTEGER,
    xp_needed       INTEGER,
    streak          INTEGER,
    state_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_game_states_game_id ON game_states(game_id);
CREATE INDEX IF NOT EXISTS idx_game_states_capture ON game_states(capture_id);

-- Per-field extraction log: which source produced the value, confidence, time.
-- Lets us debug fidelity issues and compare source accuracy over time.
CREATE TABLE IF NOT EXISTS extractions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    field           TEXT NOT NULL,        -- "gold", "board", "augments", ...
    source          TEXT NOT NULL,        -- "lcu", "vision", "template", "ocr"
    raw_value       TEXT,                 -- JSON-encoded
    parsed_value    TEXT,                 -- JSON-encoded
    confidence      REAL,                 -- 0.0–1.0 where applicable
    elapsed_ms      INTEGER NOT NULL,
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_extractions_capture ON extractions(capture_id);
CREATE INDEX IF NOT EXISTS idx_extractions_field   ON extractions(field);
CREATE INDEX IF NOT EXISTS idx_extractions_source  ON extractions(source);

-- Every template-match attempt. THIS IS THE YOLO TRAINING SET.
-- On ambiguous matches, dumped_crop_path points to the exact region image
-- so we can later review + relabel to build a fine-tuning dataset.
CREATE TABLE IF NOT EXISTS template_matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    category        TEXT NOT NULL,        -- "champion", "item", "augment"
    region_x        INTEGER NOT NULL,
    region_y        INTEGER NOT NULL,
    region_w        INTEGER NOT NULL,
    region_h        INTEGER NOT NULL,
    dumped_crop_path TEXT,                -- PNG of the exact region, for later labeling
    winner_name     TEXT,                 -- best match name or null if rejected
    winner_score    REAL,
    runner_up_name  TEXT,                 -- second-best match (for ambiguity analysis)
    runner_up_score REAL,
    is_ambiguous    INTEGER NOT NULL DEFAULT 0,  -- 1 when winner_score - runner_up_score < threshold
    is_rejected     INTEGER NOT NULL DEFAULT 0,  -- 1 when winner_score below confidence floor
    elapsed_ms      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tm_capture   ON template_matches(capture_id);
CREATE INDEX IF NOT EXISTS idx_tm_category  ON template_matches(category);
CREATE INDEX IF NOT EXISTS idx_tm_ambiguous ON template_matches(is_ambiguous);

-- Every Claude Vision API call. Tracks cost, response, and full payload
-- so we can replay past screenshots against an updated prompt offline.
CREATE TABLE IF NOT EXISTS vision_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,        -- bumped when VISION_SYSTEM_PROMPT changes
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cost_usd        REAL,
    response_json   TEXT,
    parse_ok        INTEGER NOT NULL,
    error           TEXT,
    elapsed_ms      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vision_capture ON vision_calls(capture_id);

CREATE TABLE IF NOT EXISTS rule_fires (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_state_id   INTEGER NOT NULL REFERENCES game_states(id) ON DELETE CASCADE,
    rule_id         TEXT NOT NULL,
    severity        REAL NOT NULL,
    action          TEXT,
    message         TEXT
);

CREATE INDEX IF NOT EXISTS idx_rule_fires_state_id ON rule_fires(game_state_id);
CREATE INDEX IF NOT EXISTS idx_rule_fires_rule_id  ON rule_fires(rule_id);

CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_fire_id    INTEGER NOT NULL REFERENCES rule_fires(id) ON DELETE CASCADE,
    rating          TEXT NOT NULL CHECK (rating IN ('agreed', 'disagreed', 'ignored')),
    note            TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_rule_fire ON feedback(rule_fire_id);
