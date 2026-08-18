import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

const globalForDb = globalThis as typeof globalThis & {
  __arenaNextJsPostgresqlPool?: Pool;
};

function getDatabaseUrl(): string | null {
  return process.env.DATABASE_URL ?? null;
}

function getPool(): Pool | null {
  const databaseUrl = getDatabaseUrl();
  if (!databaseUrl) return null;

  if (!globalForDb.__arenaNextJsPostgresqlPool) {
    globalForDb.__arenaNextJsPostgresqlPool = new Pool({ connectionString: databaseUrl });
  }
  return globalForDb.__arenaNextJsPostgresqlPool;
}

export const pool = new Proxy({} as Pool, {
  get(_target, prop) {
    const live = getPool();
    if (!live) {
      throw new Error("DATABASE_URL is required");
    }
    const value = live[prop as keyof Pool];
    return typeof value === "function" ? value.bind(live) : value;
  },
});

export const db = new Proxy({} as ReturnType<typeof drizzle>, {
  get(_target, prop) {
    const live = getPool();
    if (!live) {
      throw new Error("DATABASE_URL is required");
    }
    const liveDb = drizzle(live);
    const value = liveDb[prop as keyof ReturnType<typeof drizzle>];
    return typeof value === "function" ? value.bind(liveDb) : value;
  },
});

export function isDatabaseConfigured(): boolean {
  return Boolean(getDatabaseUrl());
}
