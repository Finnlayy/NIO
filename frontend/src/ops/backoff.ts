/** Shared reconnect/respawn ladder for the engine feed (client SSE + server hub). */

export const MAX_BACKOFF_MS = 30_000;

/** Exponential backoff with a ceiling: 1s, 2s, 4s … capped at MAX_BACKOFF_MS. */
export function backoffDelayMs(attempt: number): number {
  const safeAttempt = Math.max(0, Math.min(20, Math.floor(attempt)));
  return Math.min(MAX_BACKOFF_MS, 1000 * 2 ** safeAttempt);
}
