import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';

const DEFAULT_BASE = 'https://openrouter.ai/api/v1';

export async function openRouterChat(
  modelId: string,
  messages: ChatMessage[],
): Promise<ChatCompletionResult> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new ProviderError('OPENROUTER_API_KEY is not set', 'openrouter', undefined, false);
  }

  const baseUrl = process.env.OPENROUTER_BASE_URL ?? DEFAULT_BASE;
  const referer = process.env.OPENROUTER_REFERER ?? 'https://github.com/finnp/General';
  const title = process.env.OPENROUTER_APP_TITLE ?? 'NIO Platform';

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': referer,
      'X-Title': title,
    },
    body: JSON.stringify({
      model: modelId,
      messages,
      max_tokens: 512,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ProviderError(
      `OpenRouter ${response.status}: ${body.slice(0, 300)}`,
      'openrouter',
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
    throw new ProviderError('OpenRouter returned empty content', 'openrouter');
  }

  return {
    content,
    provider: 'openrouter',
    model_id: modelId,
    inputTokens: data.usage?.prompt_tokens,
    outputTokens: data.usage?.completion_tokens,
  };
}
