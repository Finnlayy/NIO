-- Phase 2: PDC conversation session persistence
-- Applied automatically by ConversationSessionStore when DATABASE_URL is set.

CREATE TABLE IF NOT EXISTS conversation_sessions (
  session_id UUID PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'api',
  baseline JSONB NOT NULL,
  hot_window JSONB NOT NULL DEFAULT '[]',
  deltas JSONB NOT NULL DEFAULT '[]',
  token_budget INT NOT NULL DEFAULT 2000,
  summary_version INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_source ON conversation_sessions (source);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_updated ON conversation_sessions (updated_at DESC);
