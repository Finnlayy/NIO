import type { ResolvedModel, ModelTier } from '../../shared/manifest-schema';
import { chatWithFallback, isLmStudioEnabled, lmStudioResolvedModel } from './providers';
import type { ChatMessage } from './providers/chat_types';
import { ModelRouter } from './model_router';
import {
  CoreExecuteContext,
  NeuralCoreAdapter,
  NeuralCoreResponse,
  WrappedPrompt,
} from './types';

function tierCandidates(router: ModelRouter, tier: ModelTier): ResolvedModel[] {
  const manifest = router.getManifest();
  const tierDef = manifest.tiers[tier];
  if (!tierDef) return [];
  return tierDef.models.map((entry) => ({
    tier,
    provider: entry.provider,
    model_id: entry.model_id,
    cost_per_1m_input: entry.cost_per_1m_input,
  }));
}

function buildMessages(wrapped: WrappedPrompt): ChatMessage[] {
  return [
    { role: 'system', content: wrapped.systemPrompt },
    { role: 'user', content: wrapped.userPrompt },
  ];
}

/**
 * Manifest-driven LLM adapter. Resolves model from role/tier via ModelRouter,
 * then calls OpenRouter / OpenAI / Anthropic with tier fallback chain.
 */
export class ManifestLlmAdapter implements NeuralCoreAdapter {
  constructor(private readonly router: ModelRouter) {}

  async execute(
    prompt: WrappedPrompt,
    context?: CoreExecuteContext,
  ): Promise<NeuralCoreResponse> {
    const role = context?.role ?? 'worker';
    const primary = context?.resolvedModel ?? this.router.resolveRole(role);

    const candidates: ResolvedModel[] = [];

    if (isLmStudioEnabled()) {
      const local = lmStudioResolvedModel();
      candidates.push({
        tier: primary.tier,
        provider: local.provider,
        model_id: local.model_id,
        cost_per_1m_input: local.cost_per_1m_input,
      });
    }

    candidates.push(
      primary,
      ...tierCandidates(this.router, primary.tier).filter(
        (m) => m.provider !== primary.provider || m.model_id !== primary.model_id,
      ),
    );

    const manifest = this.router.getManifest();
    for (const fallbackTier of manifest.defaults.fallback_chain) {
      if (fallbackTier === primary.tier) continue;
      for (const model of tierCandidates(this.router, fallbackTier)) {
        const dup = candidates.some(
          (c) => c.provider === model.provider && c.model_id === model.model_id,
        );
        if (!dup) candidates.push(model);
      }
    }

    const started = performance.now();
    const result = await chatWithFallback(candidates, buildMessages(prompt));
    const latencyMs = Math.round(performance.now() - started);

    return {
      coreNodeId: 'manifest-llm-core',
      output: result.content,
      latencyMs,
      metadata: {
        provider: result.provider,
        model_id: result.model_id,
        inputTokens: result.inputTokens,
        outputTokens: result.outputTokens,
        politenessTier: prompt.politenessTier,
        urgencyBlockLength: prompt.urgencyBlock.length,
        mode: 'live',
        ...(prompt.conversationCompression
          ? {
              pdcEnabled: true,
              pdcHotWindowTurns: prompt.conversationCompression.hotWindow.length,
              pdcDeltaCount: prompt.conversationCompression.deltas.length,
              pdcBaselineVersion: prompt.conversationCompression.baseline.summaryVersion,
            }
          : {}),
      },
    };
  }
}
