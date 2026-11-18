-- Idempotenz fuer POST /kanban/tasks: ein wiederholter Request mit demselben
-- Schluessel liefert den bereits angelegten Task statt eines Duplikats.
CREATE TABLE kanban_idempotency (
    key        TEXT PRIMARY KEY,
    task_id    TEXT NOT NULL REFERENCES kanban_tasks(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
