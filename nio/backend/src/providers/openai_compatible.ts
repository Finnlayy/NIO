import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';

export async function openAiCompatibleChat(
  provider: string,
  baseUrl: string,
  apiKey: string,
  modelId: string,
  messages: ChatMessage[],
  maxTokens = 512,
): Promise<ChatCompletionResult> {
  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: modelId,
      messages,
      max_tokens: maxTokens,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ProviderError(
      `${provider} ${response.status}: ${body.slice(0, 300)}`,
      provider,
      response.status,
      response.status >= 500 || response.status === 429,
    );
  }

  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };

  const content = data.choices?.[0]?.message?.content?.trim();
  if (!content) {
    throw new ProviderError(`${provider} returned empty content`, provider);
  }

  return {
    content,
    provider,
    model_id: modelId,
    inputTokens: data.usage?.prompt_tokens,
    outputTokens: data.usage?.completion_tokens,
  };
}
