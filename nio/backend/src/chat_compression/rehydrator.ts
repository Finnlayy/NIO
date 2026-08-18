import { baselineToSummary } from './baseline_store';
import { deltaToCompactText } from './delta_encoder';
import type { ConversationCompression, RehydratedConversation } from './types';

/** Rough token estimate (chars / 4). */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

/**
 * Reconstruct LLM-facing conversation block from baseline + deltas + hot window.
 * Respects tokenBudget by dropping oldest deltas first (cold tier compression).
 */
export function rehydrateConversation(
  compression: ConversationCompression,
): RehydratedConversation {
  const budget = compression.tokenBudget;
  const hotMessages = [...compression.hotWindow];

  const sections: string[] = ['## Session baseline (predictive state)'];
  sections.push(baselineToSummary(compression.baseline) || '(empty baseline)');

  sections.push('\n## Recent deltas (what changed vs baseline)');
  const deltaLines: string[] = [];
  for (const delta of compression.deltas) {
    deltaLines.push(deltaToCompactText(delta));
  }

  // Trim deltas from the front until within budget (keep hot window priority)
  let deltaBlock = deltaLines.join('\n');
  let baselineBlock = sections.join('\n');
  let hotBlock = hotMessages
    .map((t) => `${t.role === 'user' ? 'User' : 'Assistant'}: ${t.content}`)
    .join('\n');

  const hotTokens = estimateTokens(hotBlock);
  let remaining = budget - hotTokens - 200; // reserve for framing

  if (estimateTokens(baselineBlock) > remaining * 0.4) {
    const summary = compression.baseline.narrativeSummary ?? baselineToSummary(compression.baseline);
    baselineBlock = `## Session baseline\n${summary.slice(0, Math.floor(remaining * 0.4 * 4))}`;
  }
  remaining -= estimateTokens(baselineBlock);

  while (deltaLines.length > 0 && estimateTokens(deltaBlock) > remaining) {
    deltaLines.shift();
    deltaBlock = deltaLines.join('\n');
  }

  const conversationBlock = [
    baselineBlock,
    deltaLines.length ? `\n## Recent deltas\n${deltaBlock}` : '',
    hotBlock ? `\n## Hot window (full fidelity)\n${hotBlock}` : '',
  ]
    .filter(Boolean)
    .join('\n');

  return {
    conversationBlock,
    hotMessages,
    estimatedTokens: estimateTokens(conversationBlock),
  };
}

/**
 * Merge rehydrated block with an optional task instruction prefix.
 */
export function buildCompressedUserPrompt(
  compression: ConversationCompression,
  taskPrefix?: string,
): string {
  const { conversationBlock } = rehydrateConversation(compression);
  const prefix = taskPrefix?.trim() ?? 'Continue the conversation using the compressed context below.';
  return `${prefix}\n\n${conversationBlock}`;
}
