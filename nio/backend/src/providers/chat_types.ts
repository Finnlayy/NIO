export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatCompletionResult {
  content: string;
  provider: string;
  model_id: string;
  inputTokens?: number;
  outputTokens?: number;
}

export class ProviderError extends Error {
  constructor(
    message: string,
    readonly provider: string,
    readonly statusCode?: number,
    readonly retryable = false,
  ) {
    super(message);
    this.name = 'ProviderError';
  }
}
