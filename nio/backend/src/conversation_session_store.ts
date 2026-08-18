import type { Pool } from 'pg';
import type { ConversationCompression } from './chat_compression/types';

export interface ConversationSessionRow {
  session_id: string;
  source: string;
  baseline: ConversationCompression['baseline'];
  hot_window: ConversationCompression['hotWindow'];
  deltas: ConversationCompression['deltas'];
  token_budget: number;
  summary_version: number;
  updated_at: string;
}

const MIGRATION_SQL = `
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
`;

let pool: Pool | null = null;
let initPromise: Promise<boolean> | null = null;

async function loadPool(): Promise<Pool | null> {
  const url = process.env.DATABASE_URL?.trim();
  if (!url) return null;

  if (!pool) {
    const { Pool: PgPool } = await import('pg');
    pool = new PgPool({ connectionString: url });
  }
  return pool;
}

/** Optional PostgreSQL persistence for PDC conversation sessions. No-op when DATABASE_URL unset. */
export class ConversationSessionStore {
  isEnabled(): boolean {
    return Boolean(process.env.DATABASE_URL?.trim());
  }

  async ensureSchema(): Promise<boolean> {
    if (!this.isEnabled()) return false;
    if (!initPromise) {
      initPromise = this.runMigration();
    }
    return initPromise;
  }

  private async runMigration(): Promise<boolean> {
    const live = await loadPool();
    if (!live) return false;
    await live.query(MIGRATION_SQL);
    return true;
  }

  async saveSession(
    sessionId: string,
    source: string,
    compression: ConversationCompression,
  ): Promise<boolean> {
    if (!this.isEnabled()) return false;
    await this.ensureSchema();
    const live = await loadPool();
    if (!live) return false;

    await live.query(
      `INSERT INTO conversation_sessions
        (session_id, source, baseline, hot_window, deltas, token_budget, summary_version, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, now())
       ON CONFLICT (session_id) DO UPDATE SET
         source = EXCLUDED.source,
         baseline = EXCLUDED.baseline,
         hot_window = EXCLUDED.hot_window,
         deltas = EXCLUDED.deltas,
         token_budget = EXCLUDED.token_budget,
         summary_version = EXCLUDED.summary_version,
         updated_at = now()`,
      [
        sessionId,
        source,
        JSON.stringify(compression.baseline),
        JSON.stringify(compression.hotWindow),
        JSON.stringify(compression.deltas),
        compression.tokenBudget,
        compression.baseline.summaryVersion,
      ],
    );
    return true;
  }

  async loadSession(sessionId: string): Promise<ConversationCompression | null> {
    if (!this.isEnabled()) return null;
    await this.ensureSchema();
    const live = await loadPool();
    if (!live) return null;

    const result = await live.query<ConversationSessionRow>(
      `SELECT session_id, source, baseline, hot_window, deltas, token_budget, summary_version, updated_at
       FROM conversation_sessions WHERE session_id = $1`,
      [sessionId],
    );
    const row = result.rows[0];
    if (!row) return null;

    return {
      baseline: row.baseline,
      hotWindow: row.hot_window,
      deltas: row.deltas,
      tokenBudget: row.token_budget,
    };
  }

  async listRecent(limit = 20, source?: string): Promise<ConversationSessionRow[]> {
    if (!this.isEnabled()) return [];
    await this.ensureSchema();
    const live = await loadPool();
    if (!live) return [];

    if (source) {
      const result = await live.query<ConversationSessionRow>(
        `SELECT session_id, source, baseline, hot_window, deltas, token_budget, summary_version, updated_at
         FROM conversation_sessions WHERE source = $1 ORDER BY updated_at DESC LIMIT $2`,
        [source, limit],
      );
      return result.rows;
    }

    const result = await live.query<ConversationSessionRow>(
      `SELECT session_id, source, baseline, hot_window, deltas, token_budget, summary_version, updated_at
       FROM conversation_sessions ORDER BY updated_at DESC LIMIT $1`,
      [limit],
    );
    return result.rows;
  }
}

export const conversationSessionStore = new ConversationSessionStore();
