-- Hermes-Kanban, Schema 001 (PostgreSQL >= 13).
-- Wird von orchestrator/kanban/store_pg.py einmalig ueber schema_version angewendet.

CREATE TABLE kanban_boards (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE kanban_workers (
    uid                 TEXT PRIMARY KEY CHECK (uid ~ '^[a-z0-9][a-z0-9._-]{1,47}$'),
    name                TEXT NOT NULL,
    skills              JSONB NOT NULL DEFAULT '[]'::jsonb,
    soul_md             TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'idle' CHECK (status IN ('idle', 'busy', 'disabled')),
    fail_count          INTEGER NOT NULL DEFAULT 0,
    breaker_open_until  TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
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
    dependencies         JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(dependencies) = 'array'),
    required_skills      JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(required_skills) = 'array'),
    is_rollup            BOOLEAN NOT NULL DEFAULT FALSE,
    attempts             INTEGER NOT NULL DEFAULT 0,
    result_payload       JSONB,
    block_reason         TEXT NOT NULL DEFAULT '',
    workspace_repo       TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at           TIMESTAMPTZ
);
CREATE INDEX kanban_tasks_board_status ON kanban_tasks (board_id, status);
CREATE INDEX kanban_tasks_status_prio ON kanban_tasks (status, priority DESC, created_at);
CREATE INDEX kanban_tasks_parent ON kanban_tasks (parent_id);

-- Academy-Lernschleife: eine Experience pro Worker-Lauf.
CREATE TABLE experiences (
    id            TEXT PRIMARY KEY,
    worker_uid    TEXT NOT NULL REFERENCES kanban_workers(uid),
    task_id       TEXT NOT NULL REFERENCES kanban_tasks(id),
    summary       TEXT NOT NULL,
    lessons       JSONB NOT NULL DEFAULT '[]'::jsonb,
    skills_delta  JSONB NOT NULL DEFAULT '[]'::jsonb,
    outcome       TEXT NOT NULL DEFAULT 'success',
    vault_synced  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX experiences_worker ON experiences (worker_uid, created_at);
CREATE INDEX experiences_vault_pending ON experiences (vault_synced) WHERE NOT vault_synced;

-- Unveraenderliches Audit-Ledger: Hash-Kette (prev_hash -> entry_hash), nur INSERT.
CREATE TABLE audit_ledger (
    seq         BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    category    TEXT NOT NULL CHECK (category IN ('system', 'code', 'trading', 'task', 'worker')),
    subject     TEXT NOT NULL DEFAULT '',
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_hash   CHAR(64) NOT NULL,
    entry_hash  CHAR(64) NOT NULL UNIQUE
);

CREATE FUNCTION audit_ledger_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_ledger ist append-only (% verweigert)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_ledger_no_mutation
    BEFORE UPDATE OR DELETE ON audit_ledger
    FOR EACH ROW EXECUTE FUNCTION audit_ledger_immutable();
CREATE TRIGGER audit_ledger_no_truncate
    BEFORE TRUNCATE ON audit_ledger
    FOR EACH STATEMENT EXECUTE FUNCTION audit_ledger_immutable();

-- Zweite Verteidigungslinie: die Anwendungsrolle (falls angelegt) darf das Ledger
-- nur lesen und anhaengen. Der Trigger greift auch fuer den Tabelleneigentuemer.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nio_app') THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON audit_ledger FROM nio_app;
    END IF;
END;
$$;
