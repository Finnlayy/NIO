import { providerHasKey, isLmStudioEnabled, isBytePlusArkEnabled } from './providers';
import { DeterministicCoreAdapter } from './deterministic_adapter';
import { ManifestLlmAdapter } from './llm_adapter';
import { ModelRouter } from './model_router';
import { NeuralCoreAdapter } from './types';

export type CoreAdapterMode = 'live' | 'deterministic';

function hasAnyProviderKey(): boolean {
  return (
    isLmStudioEnabled() ||
    isBytePlusArkEnabled() ||
    providerHasKey('openrouter') ||
    providerHasKey('openai') ||
    providerHasKey('anthropic') ||
    providerHasKey('xai') ||
    providerHasKey('moonshot')
  );
}

export function detectCoreAdapterMode(): CoreAdapterMode {
  const forced = process.env.CORE_ADAPTER_MODE?.trim().toLowerCase();
  if (forced === 'live' || forced === 'deterministic') {
    return forced;
  }
  if (hasAnyProviderKey()) {
    return 'live';
  }
  return 'deterministic';
}

/** Create the best available core adapter based on env API keys. */
export function createCoreAdapter(router: ModelRouter): {
  adapter: NeuralCoreAdapter;
  mode: CoreAdapterMode;
} {
  const mode = detectCoreAdapterMode();
  if (mode === 'live') {
    if (!hasAnyProviderKey()) {
      console.warn(
        'CORE_ADAPTER_MODE=live but no LLM API keys found; calls will fail unless keys are injected at runtime.',
      );
    }
    return { adapter: new ManifestLlmAdapter(router), mode };
  }
  return { adapter: new DeterministicCoreAdapter(), mode: 'deterministic' };
}
