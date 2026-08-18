import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';

const DEFAULT_BASE = 'https://api.openai.com/v1';

export async function openAiChat(
  modelId: string,
  messages: ChatMessage[],
): Promise<ChatCompletionResult> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new ProviderError('OPENAI_API_KEY is not set', 'openai', undefined, false);
  }

  const baseUrl = process.env.OPENAI_BASE_URL ?? DEFAULT_BASE;

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
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
      `OpenAI ${response.status}: ${body.slice(0, 300)}`,
      'openai',
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
    throw new ProviderError('OpenAI returned empty content', 'openai');
  }

  return {
    content,
    provider: 'openai',
    model_id: modelId,
    inputTokens: data.usage?.prompt_tokens,
    outputTokens: data.usage?.completion_tokens,
  };
}
