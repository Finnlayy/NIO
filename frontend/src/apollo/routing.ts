import { POOL_ENDPOINTS, POOL_PROVIDERS } from "./catalog";
import type {
  ActiveTask,
  FreeLLMModelCandidate,
  FreeLLMProviderKey,
  FreeLLMRoutingConfig,
  RouterSnapshot,
} from "./types";

/* ==================================================================== */
/* FreeLLMAPI routing — pure functions                                    */
/*                                                                        */
/* Everything in this module is deterministic and side-effect free so the */
/* ranking, the failover decision and the handoff note can be unit tested */
/* without React, a network or a clock.                                   */
/* ==================================================================== */

export type Weights = FreeLLMRoutingConfig["weights"];

export const DEFAULT_WEIGHTS: Weights = { reliability: 50, speed: 25, intelligence: 25 };

/**
 * Weights are percentages that should sum to 100; clamp and renormalise.
 *
 * The result is whole-ish percentages that sum to exactly 100 (any rounding
 * drift is absorbed by the largest bucket), so the deck can show "50 / 25 / 25"
 * and the router table agrees with the sliders. Weights are never floored to a
 * minimum: an operator who asks for 0% speed gets 0% speed.
 */
export function normalizeWeights(weights: Weights): Weights {
  const clamp = (value: number) => (Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0);
  const values: Weights = {
    reliability: clamp(weights.reliability),
    speed: clamp(weights.speed),
    intelligence: clamp(weights.intelligence),
  };
  const total = values.reliability + values.speed + values.intelligence;
  if (total <= 0) return { reliability: 100, speed: 0, intelligence: 0 };

  const scaled: Weights = {
    reliability: Math.round((values.reliability / total) * 100),
    speed: Math.round((values.speed / total) * 100),
    intelligence: Math.round((values.intelligence / total) * 100),
  };
  const drift = 100 - (scaled.reliability + scaled.speed + scaled.intelligence);
  if (drift !== 0) {
    const largest = (Object.keys(scaled) as Array<keyof Weights>).reduce((a, b) =>
      scaled[a] >= scaled[b] ? a : b,
    );
    scaled[largest] += drift;
  }
  return scaled;
}

/** Weighted 0-100 score, rounded to one decimal so the table is stable. */
export function compositeScore(
  candidate: Pick<FreeLLMModelCandidate, "reliability" | "speed" | "intelligence">,
  weights: Weights,
): number {
  const w = normalizeWeights(weights);
  const raw =
    (candidate.reliability * w.reliability +
      candidate.speed * w.speed +
      candidate.intelligence * w.intelligence) /
    100;
  return Math.round(raw * 10) / 10;
}

/**
 * Rank by composite score; ties break on reliability, then on id so the
 * leaderboard never reorders itself between renders.
 */
export function rankCandidates(
  candidates: readonly FreeLLMModelCandidate[],
  weights: Weights,
): FreeLLMModelCandidate[] {
  return candidates
    .map((candidate) => ({ ...candidate, compositeScore: compositeScore(candidate, weights) }))
    .sort(
      (a, b) =>
        b.compositeScore - a.compositeScore ||
        b.reliability - a.reliability ||
        a.id.localeCompare(b.id),
    );
}

/** First usable candidate in rank order, never the one currently active. */
export function chooseNextCandidate(
  ranked: readonly FreeLLMModelCandidate[],
  excludeId?: string,
): FreeLLMModelCandidate | null {
  return ranked.find((c) => c.status !== "LIMIT_REACHED" && c.id !== excludeId) ?? null;
}

/** How healthy is the pool right now? Drives the HUD ring and the badge. */
export function poolHealth(providers: readonly FreeLLMProviderKey[]) {
  const active = providers.filter((p) => p.status === "ACTIVE").length;
  const limited = providers.filter((p) => p.status === "LIMIT_REACHED").length;
  return {
    active,
    limited,
    standby: providers.length - active - limited,
    total: providers.length,
    ratio: providers.length === 0 ? 0 : active / providers.length,
  };
}

const clip = (text: string, max: number) =>
  text.length <= max ? text : `${text.slice(0, Math.max(0, max - 1)).trimEnd()}…`;

/**
 * The note that travels with a failover. It is deliberately terse: the next
 * model gets *state*, not a transcript. `resume` tells it where to continue.
 */
export function buildHandoffNote(input: {
  from: string;
  to: string;
  task?: ActiveTask | null;
  reason?: string;
  completed?: readonly string[];
  pending?: readonly string[];
  directive?: string;
  maxChars?: number;
}): string {
  const task = input.task ?? null;
  const completed = [...(input.completed ?? task?.completed ?? [])];
  const pending = [...(input.pending ?? task?.pending ?? [])];
  const list = (items: string[]) =>
    items.length === 0 ? "—" : items.slice(0, 4).map((item, i) => `${i + 1}) ${clip(item, 96)}`).join(" ");

  const lines = [
    "CONTEXT HANDOFF · NIO/APOLLO",
    `from: ${clip(input.from, 48)} → to: ${clip(input.to, 48)}`,
    `reason: ${clip(input.reason ?? "primary quota exhausted (HTTP 429)", 90)}`,
    `task: ${clip(task?.label ?? "idle · no task in flight", 90)}`,
    `completed: ${list(completed)}`,
    `pending: ${list(pending)}`,
    `resume: continue at the next pending objective; do not restate context.`,
  ];
  if (input.directive && input.directive.trim()) {
    // Inserted after `task:` so the note reads from → reason → task → directive
    // → completed → pending → resume. Appending would bury the instruction.
    lines.splice(4, 0, `directive: ${clip(input.directive.trim().replace(/\s+/g, " "), 160)}`);
  }
  const note = lines.join("\n");
  return clip(note, input.maxChars ?? 900);
}

/** One-line summary for the HUD / terminal. */
export function describeFailover(
  from: string,
  to: string,
  reason: string,
): string {
  return `Failover ${from} → ${to} · ${reason}`;
}

/** The snapshot the HUD and `/router status` render. */
export function routerSnapshot(input: {
  primaryModel: string;
  primaryQuotaPercent: number;
  activeModel: string;
  activeProvider: string;
  mode: RouterSnapshot["mode"];
  failoverCount: number;
  latencyMs: number;
  lastHandoffNote?: string;
}): RouterSnapshot {
  return {
    primaryModel: input.primaryModel,
    primaryQuotaPercent: Math.round(input.primaryQuotaPercent * 10) / 10,
    activeModel: input.activeModel,
    activeProvider: input.activeProvider,
    mode: input.mode,
    poolEndpoints: POOL_ENDPOINTS,
    poolProviders: POOL_PROVIDERS,
    failoverCount: input.failoverCount,
    latencyMs: input.latencyMs,
    lastHandoffNote: input.lastHandoffNote,
  };
}

/** Text table used by `/router status` in the hybrid CLI. */
export function formatRouterTable(
  providers: readonly FreeLLMProviderKey[],
  ranked: readonly FreeLLMModelCandidate[],
  weights: Weights,
): string {
  const w = normalizeWeights(weights);
  const header = `MODE  ranking · reliability ${w.reliability.toFixed(0)}% / speed ${w.speed.toFixed(0)}% / intelligence ${w.intelligence.toFixed(0)}%`;
  const rows = ranked.slice(0, 8).map((c, index) => {
    const rank = String(index + 1).padStart(2, " ");
    const score = c.compositeScore.toFixed(1).padStart(5, " ");
    const status = c.status === "LIMIT_REACHED" ? "limit" : c.status === "ACTIVE" ? "active" : "ready";
    return `${rank}. ${score}  ${c.name.padEnd(20, " ")} ${c.provider.padEnd(16, " ")} ${status}`;
  });
  const health = poolHealth(providers);
  const foot = `pool: ${health.active} active · ${health.standby} standby · ${health.limited} limited · ${POOL_ENDPOINTS} endpoints / ${POOL_PROVIDERS} providers`;
  return [header, ...rows, foot].join("\n");
}
