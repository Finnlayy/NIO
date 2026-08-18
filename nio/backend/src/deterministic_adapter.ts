import { CoreExecuteContext, NeuralCoreAdapter, NeuralCoreResponse, WrappedPrompt } from './types';

/**
 * Deterministic core adapter suitable for integration tests and local demos
 * when no LLM API keys are configured.
 */
export class DeterministicCoreAdapter implements NeuralCoreAdapter {
  async execute(prompt: WrappedPrompt, _context?: CoreExecuteContext): Promise<NeuralCoreResponse> {
    return {
      coreNodeId: 'deterministic-core',
      output: [
        `system_prompt_length=${prompt.systemPrompt.length}`,
        `user_prompt_length=${prompt.userPrompt.length}`,
        `is_complex=${prompt.isComplex}`,
        `domain=${prompt.domain}`,
        `expected_accuracy=${prompt.expectedAccuracy}`,
      ].join(';'),
      latencyMs: 0,
      metadata: {
        urgencyBlockLength: prompt.urgencyBlock.length,
        politenessTier: prompt.politenessTier,
        mode: 'deterministic',
      },
    };
  }
}
