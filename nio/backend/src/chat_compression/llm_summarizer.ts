import type { ModelRouter } from '../model_router';
import { chatWithFallback, isLmStudioEnabled, lmStudioResolvedModel } from '../providers';
import type { ChatMessage } from '../providers/chat_types';
import { baselineToSummary } from './baseline_store';
import { stripFiller } from './delta_encoder';
import { estimateTokens, rehydrateConversation } from './rehydrator';
import type { ChatTurn, ConversationCompression, SessionBaseline } from './types';

const SUMMARY_SYSTEM_PROMPT = `You compress conversation history into a dense narrative summary.
Output plain text only (no markdown headers). Max 400 characters.
Preserve: decisions, open tasks, key entities, unresolved questions. Drop filler.`;

function heuristicSummary(baseline: SessionBaseline, recentTurns: ChatTurn[]): string {
  const snippets = recentTurns
    .slice(-4)
    .map((t) => `${t.role}: ${stripFiller(t.content).slice(0, 120)}`);
  const base = baselineToSummary(baseline).replace(/\n/g, ' · ').slice(0, 200);
  return [base, ...snippets].filter(Boolean).join(' · ').slice(0, 480);
}

function buildSummarizationMessages(
  baseline: SessionBaseline,
  recentTurns: ChatTurn[],
): ChatMessage[] {
  const baselineText = baselineToSummary(baseline) || '(empty)';
  const turnsText = recentTurns
    .slice(-8)
    .map((t) => `${t.role}: ${t.content.slice(0, 300)}`)
    .join('\n');
  return [
    { role: 'system', content: SUMMARY_SYSTEM_PROMPT },
    {
      role: 'user',
      content: `Baseline state:\n${baselineText}\n\nRecent turns:\n${turnsText}\n\nSummarize:`,
    },
  ];
}

function resolveSummarizationCandidates(router: ModelRouter) {
  const manifest = router.getManifest();
  const economy = manifest.tiers.economy?.models[0];
  const standard = manifest.tiers.standard?.models[0];
  const candidates = [];

  if (isLmStudioEnabled()) {
    const local = lmStudioResolvedModel();
    candidates.push({
      tier: 'economy' as const,
      provider: local.provider,
      model_id: local.model_id,
      cost_per_1m_input: local.cost_per_1m_input,
    });
  }
  if (economy) {
    candidates.push({
      tier: 'economy' as const,
      provider: economy.provider,
      model_id: economy.model_id,
      cost_per_1m_input: economy.cost_per_1m_input,
    });
  }
  if (standard) {
    candidates.push({
      tier: 'standard' as const,
      provider: standard.provider,
      model_id: standard.model_id,
      cost_per_1m_input: standard.cost_per_1m_input,
    });
  }
  return candidates;
}

/** True when heuristic baseline still exceeds rehydration budget. */
export function needsLlmSummarization(compression: ConversationCompression): boolean {
  const rehydrated = rehydrateConversation(compression);
  if (rehydrated.estimatedTokens > compression.tokenBudget) {
    return true;
  }
  const narrative = compression.baseline.narrativeSummary ?? '';
  return estimateTokens(narrative) > Math.floor(compression.tokenBudget * 0.25);
}

/**
 * LLM cold-path summarization via ManifestLlmAdapter provider chain (LM Studio first).
 * Falls back to heuristic summary on failure or when no provider keys exist.
 */
export async function summarizeSessionBaseline(
  baseline: SessionBaseline,
  recentTurns: ChatTurn[],
  router?: ModelRouter,
): Promise<{ narrativeSummary: string; usedLlm: boolean }> {
  const fallback = heuristicSummary(baseline, recentTurns);

  if (!router) {
    return { narrativeSummary: fallback, usedLlm: false };
  }

  const candidates = resolveSummarizationCandidates(router);
  if (candidates.length === 0) {
    return { narrativeSummary: fallback, usedLlm: false };
  }

  try {
    const messages = buildSummarizationMessages(baseline, recentTurns);
    const result = await chatWithFallback(candidates, messages);
    const text = result.content.trim().slice(0, 480);
    if (text.length < 20) {
      return { narrativeSummary: fallback, usedLlm: false };
    }
    return { narrativeSummary: text, usedLlm: true };
  } catch {
    return { narrativeSummary: fallback, usedLlm: false };
  }
}

/** Apply LLM summary to compression bundle when budget requires it. */
export async function enrichCompressionWithLlmSummary(
  compression: ConversationCompression,
  allTurns: ChatTurn[],
  router?: ModelRouter,
): Promise<ConversationCompression> {
  if (!needsLlmSummarization(compression)) {
    return compression;
  }

  const { narrativeSummary, usedLlm } = await summarizeSessionBaseline(
    compression.baseline,
    allTurns.length ? allTurns : compression.hotWindow,
    router,
  );

  return {
    ...compression,
    baseline: {
      ...compression.baseline,
      narrativeSummary,
      summaryVersion: compression.baseline.summaryVersion + (usedLlm ? 1 : 0),
      updatedAt: new Date().toISOString(),
    },
  };
}
