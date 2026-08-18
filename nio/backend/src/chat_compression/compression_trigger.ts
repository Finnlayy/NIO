import type { ModelRouter } from '../model_router';
import { emptyBaseline, mergeDeltaIntoBaseline } from './baseline_store';
import { encodeDelta, stripFiller } from './delta_encoder';
import { enrichCompressionWithLlmSummary, needsLlmSummarization } from './llm_summarizer';
import type {
  ChatTurn,
  CompressionConfig,
  ConversationCompression,
  SessionBaseline,
  TurnDelta,
} from './types';
import { DEFAULT_COMPRESSION_CONFIG } from './types';
import { estimateTokens } from './rehydrator';

export { needsLlmSummarization };

function turnsFromMessages(messages: ChatTurn[]): ChatTurn[] {
  return messages.filter((m) => m.content.trim().length > 0);
}

function heuristicSummary(baseline: SessionBaseline, recentTurns: ChatTurn[]): string {
  const snippets = recentTurns
    .slice(-4)
    .map((t) => `${t.role}: ${stripFiller(t.content).slice(0, 120)}`);
  const base = baselineToCompact(baseline);
  return [base, ...snippets].filter(Boolean).join(' · ').slice(0, 480);
}

function baselineToCompact(baseline: SessionBaseline): string {
  const parts: string[] = [];
  if (baseline.topics.length) parts.push(`topics: ${baseline.topics.slice(-3).join(', ')}`);
  if (baseline.decisions.length) parts.push(`decisions: ${baseline.decisions.slice(-2).join(', ')}`);
  if (baseline.openTasks.length) parts.push(`open: ${baseline.openTasks.slice(-3).join(', ')}`);
  return parts.join('; ');
}

/**
 * Decide whether cold-tier compression should run (history exceeds token budget).
 */
export function shouldCompress(
  messages: ChatTurn[],
  config: CompressionConfig = DEFAULT_COMPRESSION_CONFIG,
): boolean {
  const text = messages.map((m) => m.content).join('\n');
  return estimateTokens(text) > config.tokenBudget;
}

/**
 * Compress cold turns into baseline + deltas; retain hot window at full fidelity.
 * Deterministic heuristics only (no LLM on hot path).
 */
export function compressSession(
  messages: ChatTurn[],
  existingBaseline?: SessionBaseline,
  existingDeltas?: TurnDelta[],
  config: CompressionConfig = DEFAULT_COMPRESSION_CONFIG,
): ConversationCompression {
  const turns = turnsFromMessages(messages);
  const hotCount = Math.min(config.hotWindowTurns * 2, turns.length); // user+assistant pairs approx
  const hotWindow = turns.slice(-hotCount);
  const coldTurns = turns.slice(0, Math.max(0, turns.length - hotCount));

  let baseline = existingBaseline ?? emptyBaseline();
  const deltas: TurnDelta[] = [...(existingDeltas ?? [])];

  for (let i = 0; i < coldTurns.length; i++) {
    const turn = coldTurns[i]!;
    const delta = encodeDelta(turn, baseline, i);
    deltas.push(delta);
    baseline = mergeDeltaIntoBaseline(baseline, delta);
  }

  // Fold overflow deltas into narrative summary
  while (deltas.length > config.maxDeltas) {
    const dropped = deltas.shift();
    if (dropped) {
      baseline = mergeDeltaIntoBaseline(baseline, dropped);
    }
  }

  baseline = {
    ...baseline,
    narrativeSummary: heuristicSummary(baseline, turns),
    summaryVersion: baseline.summaryVersion + 1,
  };

  return {
    baseline,
    hotWindow,
    deltas: deltas.slice(-config.maxDeltas),
    tokenBudget: config.tokenBudget,
    hotWindowTurns: config.hotWindowTurns,
  };
}

/**
 * Incremental update: append new turns, compress if over budget.
 */
export function updateCompressionState(
  messages: ChatTurn[],
  prior?: ConversationCompression | null,
  config: CompressionConfig = DEFAULT_COMPRESSION_CONFIG,
): ConversationCompression {
  if (!shouldCompress(messages, config) && prior) {
    const turns = turnsFromMessages(messages);
    const hotCount = Math.min((config.hotWindowTurns ?? 3) * 2, turns.length);
    return {
      ...prior,
      hotWindow: turns.slice(-hotCount),
      tokenBudget: config.tokenBudget,
    };
  }
  return compressSession(
    messages,
    prior?.baseline,
    prior?.deltas,
    config,
  );
}

export interface CompressSessionOptions {
  modelRouter?: ModelRouter;
  /** When true (default), run LLM summarization on cold path if heuristic exceeds budget. */
  llmSummarize?: boolean;
}

/**
 * Async compression with optional LLM cold-path summarization (ManifestLlmAdapter chain).
 */
export async function compressSessionAsync(
  messages: ChatTurn[],
  existingBaseline?: SessionBaseline,
  existingDeltas?: TurnDelta[],
  config: CompressionConfig = DEFAULT_COMPRESSION_CONFIG,
  options: CompressSessionOptions = {},
): Promise<ConversationCompression> {
  const heuristic = compressSession(messages, existingBaseline, existingDeltas, config);
  const llmSummarize = options.llmSummarize !== false;
  if (!llmSummarize || !needsLlmSummarization(heuristic)) {
    return heuristic;
  }
  const turns = turnsFromMessages(messages);
  return enrichCompressionWithLlmSummary(heuristic, turns, options.modelRouter);
}

/**
 * Async incremental update with optional LLM summarization.
 */
export async function updateCompressionStateAsync(
  messages: ChatTurn[],
  prior?: ConversationCompression | null,
  config: CompressionConfig = DEFAULT_COMPRESSION_CONFIG,
  options: CompressSessionOptions = {},
): Promise<ConversationCompression> {
  const sync = updateCompressionState(messages, prior, config);
  const llmSummarize = options.llmSummarize !== false;
  if (!llmSummarize || !needsLlmSummarization(sync)) {
    return sync;
  }
  const turns = turnsFromMessages(messages);
  return enrichCompressionWithLlmSummary(sync, turns, options.modelRouter);
}
