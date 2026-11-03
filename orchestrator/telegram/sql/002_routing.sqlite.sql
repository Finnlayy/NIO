-- At-least-once-Zustellung: routed_at markiert Nachrichten, die alle Sinks durchlaufen haben.

ALTER TABLE messages ADD COLUMN routed_at TEXT;

CREATE INDEX IF NOT EXISTS idx_messages_peer_routed_at
    ON messages (peer, routed_at);
