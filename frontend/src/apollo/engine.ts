import type { ActiveTask, FreeLLMModelCandidate } from "./types";
import { buildHandoffNote, chooseNextCandidate, rankCandidates, type Weights, DEFAULT_WEIGHTS } from "./routing";

/* ==================================================================== */
/* Failover state machine                                                */
/*                                                                       */
/* Pure reducer: same input, same output. The store owns the side effects */
/* (timers, terminal lines, animations); this module only decides what    */
/* the router *is*, never what it looks like.                            */
/* ==================================================================== */

export type RouterMode = "PRIMARY" | "FAILOVER" | "EXHAUSTED";

export interface RouterState {
  primaryModel: string;
  primaryQuotaPercent: number;
  activeCandidateId: string | null;
  mode: RouterMode;
  failoverCount: number;
  lastHandoffNote?: string;
  chain: FreeLLMModelCandidate[];
}

export interface ModelRef {
  id: string;
  name: string;
  provider: string;
}

export interface FailoverOutcome {
  state: RouterState;
  switched: boolean;
  from: ModelRef;
  to: ModelRef | null;
  reason: string;
  note?: string;
}

export function initialRouterState(
  primaryModel: string,
  chain: readonly FreeLLMModelCandidate[],
  quota = 82,
): RouterState {
  return {
    primaryModel,
    primaryQuotaPercent: quota,
    activeCandidateId: null,
    mode: "PRIMARY",
    failoverCount: 0,
    chain: chain.map((c) => ({ ...c })),
  };
}

/** Whatever is answering right now. */
/**
 * Which model is actually answering right now.
 *
 * The result is memoised on the identity of `state`. Router state is immutable
 * (every action replaces the object), so a cache hit means "nothing changed".
 * This matters because the function is used directly as a zustand selector:
 * returning a fresh object on every call makes React's `getServerSnapshot`
 * check fail ("should be cached to avoid an infinite loop") and the page never
 * hydrates.
 */
let cachedFrom: RouterState | null = null;
let cachedModel: ModelRef | null = null;

export function activeModelOf(state: RouterState): ModelRef {
  if (state === cachedFrom && cachedModel) return cachedModel;

  let model: ModelRef;
  if (state.mode === "PRIMARY" || !state.activeCandidateId) {
    model = { id: "primary", name: state.primaryModel, provider: "primary endpoint" };
  } else {
    const candidate = state.chain.find((c) => c.id === state.activeCandidateId);
    model = candidate
      ? { id: candidate.id, name: candidate.name, provider: candidate.provider }
      : { id: "primary", name: state.primaryModel, provider: "primary endpoint" };
  }

  cachedFrom = state;
  cachedModel = model;
  return model;
}

/** Burn quota. `percent` is how much of the window the turn consumed. */
export function consumeQuota(state: RouterState, percent: number): RouterState {
  if (!Number.isFinite(percent) || percent <= 0) return state;
  const next = Math.max(0, Math.round((state.primaryQuotaPercent - percent) * 10) / 10);
  return { ...state, primaryQuotaPercent: next };
}

/** Under threshold (default 0) the primary is considered spent. */
export function shouldFailover(state: RouterState, threshold = 0): boolean {
  return state.primaryQuotaPercent <= threshold;
}

/**
 * Hot-swap to the best free candidate.
 *
 * Ordering rules that matter in practice:
 *  - never pick the model that just ran out of quota,
 *  - never pick a candidate already flagged LIMIT_REACHED,
 *  - keep the ranking tied to the operator's weights, not to a hardcoded list.
 */
export function failover(
  state: RouterState,
  options: {
    weights?: Weights;
    task?: ActiveTask | null;
    reason?: string;
    directive?: string;
    handoffNote?: boolean;
    now?: number;
  } = {},
): FailoverOutcome {
  const weights = options.weights ?? DEFAULT_WEIGHTS;
  const reason = options.reason ?? "primary quota exhausted (0% remaining, HTTP 429)";
  const from = activeModelOf(state);
  const ranked = rankCandidates(state.chain, weights);
  const next = chooseNextCandidate(ranked, state.activeCandidateId ?? undefined);

  if (!next) {
    return {
      state: { ...state, mode: "EXHAUSTED", primaryQuotaPercent: 0 },
      switched: false,
      from,
      to: null,
      reason: "no free candidate left in the pool",
    };
  }

  const chain = state.chain.map((c) => {
    if (c.id === next.id) return { ...c, status: "ACTIVE" as const, compositeScore: next.compositeScore };
    if (state.activeCandidateId && c.id === state.activeCandidateId) {
      return { ...c, status: "LIMIT_REACHED" as const };
    }
    return { ...c };
  });

  const note = options.handoffNote === false
    ? undefined
    : buildHandoffNote({
        from: from.name,
        to: next.name,
        task: options.task,
        reason,
        directive: options.directive,
      });

  return {
    state: {
      ...state,
      primaryQuotaPercent: state.mode === "PRIMARY" ? 0 : state.primaryQuotaPercent,
      activeCandidateId: next.id,
      mode: "FAILOVER",
      failoverCount: state.failoverCount + 1,
      lastHandoffNote: note,
      chain,
    },
    switched: true,
    from,
    to: { id: next.id, name: next.name, provider: next.provider },
    reason,
    note,
  };
}

/** Operator restores the primary (fresh quota window / new key). */
export function restorePrimary(state: RouterState, quota = 100): RouterState {
  return {
    ...state,
    mode: "PRIMARY",
    primaryQuotaPercent: quota,
    activeCandidateId: null,
    chain: state.chain.map((c) =>
      c.status === "ACTIVE" ? { ...c, status: "READY" as const } : { ...c },
    ),
  };
}

/** Roll one quota window forward: limited candidates become usable again. */
export function rollQuotaWindow(state: RouterState, quota = 100): RouterState {
  const restored = restorePrimary(state, quota);
  return {
    ...restored,
    failoverCount: state.failoverCount,
    lastHandoffNote: state.lastHandoffNote,
    chain: restored.chain.map((c) =>
      c.status === "LIMIT_REACHED" ? { ...c, status: "READY" as const } : c,
    ),
  };
}

/** `/config set` style quota mutation from the CLI. */
export function setQuota(state: RouterState, percent: number): RouterState {
  const clamped = Math.min(100, Math.max(0, Math.round(percent * 10) / 10));
  return { ...state, primaryQuotaPercent: clamped };
}
