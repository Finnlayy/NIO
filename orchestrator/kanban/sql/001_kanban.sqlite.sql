-- Hermes-Kanban, Schema 001 (SQLite >= 3.38, JSON-Funktionen eingebaut).
-- Spiegel von 001_kanban.sql; Zeitstempel als ISO-8601-Text (UTC, 'Z').

CREATE TABLE kanban_boards (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE kanban_workers (
    uid                 TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    skills              TEXT NOT NULL DEFAULT '[]' CHECK (json_type(skills) = 'array'),
    soul_md             TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'idle' CHECK (status IN ('idle', 'busy', 'disabled')),
    fail_count          INTEGER NOT NULL DEFAULT 0,
    breaker_open_until  TEXT,
    updated_at          TEXT NOT NULL
);

CREATE TABLE kanban_tasks (
    id                   TEXT PRIMARY KEY,
    board_id             TEXT NOT NULL REFERENCES kanban_boards(id),
    title                TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    status               TEXT NOT NULL DEFAULT 'triage'
                         CHECK (status IN ('triage', 'backlog', 'ready', 'in_progress', 'blocked', 'completed')),
    priority             INTEGER NOT NULL DEFAULT 0,
    assigned_worker_uid  TEXT REFERENCES kanban_workers(uid),
    parent_id            TEXT REFERENCES kanban_tasks(id),
    dependencies         TEXT NOT NULL DEFAULT '[]' CHECK (json_type(dependencies) = 'array'),
    required_skills      TEXT NOT NULL DEFAULT '[]' CHECK (json_type(required_skills) = 'array'),
    is_rollup            INTEGER NOT NULL DEFAULT 0,
    attempts             INTEGER NOT NULL DEFAULT 0,
    result_payload       TEXT,
    block_reason         TEXT NOT NULL DEFAULT '',
    workspace_repo       TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    started_at           TEXT
);
CREATE INDEX kanban_tasks_board_status ON kanban_tasks (board_id, status);
CREATE INDEX kanban_tasks_status_prio ON kanban_tasks (status, priority DESC, created_at);
CREATE INDEX kanban_tasks_parent ON kanban_tasks (parent_id);

CREATE TABLE experiences (
    id            TEXT PRIMARY KEY,
    worker_uid    TEXT NOT NULL REFERENCES kanban_workers(uid),
    task_id       TEXT NOT NULL REFERENCES kanban_tasks(id),
    summary       TEXT NOT NULL,
    lessons       TEXT NOT NULL DEFAULT '[]',
    skills_delta  TEXT NOT NULL DEFAULT '[]',
    outcome       TEXT NOT NULL DEFAULT 'success',
    vault_synced  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE INDEX experiences_worker ON experiences (worker_uid, created_at);

CREATE TABLE audit_ledger (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    category    TEXT NOT NULL CHECK (category IN ('system', 'code', 'trading', 'task', 'worker')),
    subject     TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT '{}',
    prev_hash   TEXT NOT NULL,
    entry_hash  TEXT NOT NULL UNIQUE
);

CREATE TRIGGER audit_ledger_no_update BEFORE UPDATE ON audit_ledger
BEGIN
    SELECT RAISE(ABORT, 'audit_ledger ist append-only (UPDATE verweigert)');
END;
CREATE TRIGGER audit_ledger_no_delete BEFORE DELETE ON audit_ledger
BEGIN
    SELECT RAISE(ABORT, 'audit_ledger ist append-only (DELETE verweigert)');
END;
