-- Telegram-Store (SQLite). Versionierung uebernimmt SqliteTelegramStore._migrate.

CREATE TABLE IF NOT EXISTS messages (
    peer INTEGER NOT NULL,
    msg_id INTEGER NOT NULL,
    sender TEXT NOT NULL,
    text TEXT NOT NULL,
    ts TEXT NOT NULL,
    outgoing BOOLEAN NOT NULL,
    is_bot BOOLEAN NOT NULL,
    PRIMARY KEY (peer, msg_id)
);

CREATE TABLE IF NOT EXISTS cursors (
    peer INTEGER PRIMARY KEY,
    last_msg_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS monitored (
    peer INTEGER PRIMARY KEY,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pairings (
    source_peer INTEGER PRIMARY KEY,
    target_peer INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS allowlist (
    peer TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestions (
    id TEXT PRIMARY KEY,
    source_peer INTEGER NOT NULL,
    target_peer INTEGER NOT NULL,
    text TEXT NOT NULL,
    based_on_msg_id INTEGER,
    origin TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    request_id TEXT,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    callback_url TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength INTEGER NOT NULL,
    peer INTEGER NOT NULL,
    msg_id INTEGER NOT NULL,
    evidence TEXT NOT NULL,
    created_at TEXT NOT NULL,
    kanban_task_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_direction_created_at
    ON signals (symbol, direction, created_at);

CREATE TABLE IF NOT EXISTS sends (
    id TEXT PRIMARY KEY,
    peer INTEGER NOT NULL,
    ts TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sends_peer_ts
    ON sends (peer, ts);
