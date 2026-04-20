-- TFT Companion logging database schema.
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

CREATE TABLE IF NOT EXISTS game_states (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
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
