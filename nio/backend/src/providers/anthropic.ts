import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';

const DEFAULT_BASE = 'https://api.anthropic.com/v1';

export async function anthropicChat(
  modelId: string,
  messages: ChatMessage[],
): Promise<ChatCompletionResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new ProviderError('ANTHROPIC_API_KEY is not set', 'anthropic', undefined, false);
  }

  const baseUrl = process.env.ANTHROPIC_BASE_URL ?? DEFAULT_BASE;
  const system = messages.find((m) => m.role === 'system')?.content;
  const chatMessages = messages
    .filter((m) => m.role !== 'system')
    .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }));

  const response = await fetch(`${baseUrl}/messages`, {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: modelId,
      max_tokens: 512,
      ...(system ? { system } : {}),
      messages: chatMessages,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ProviderError(
      `Anthropic ${response.status}: ${body.slice(0, 300)}`,
      'anthropic',
      response.status,
      response.status >= 500 || response.status === 429,
    );
  }

  const data = (await response.json()) as {
    content?: Array<{ type?: string; text?: string }>;
    usage?: { input_tokens?: number; output_tokens?: number };
  };

  const content = data.content
    ?.filter((block) => block.type === 'text')
    .map((block) => block.text ?? '')
    .join('')
    .trim();

  if (!content) {
    throw new ProviderError('Anthropic returned empty content', 'anthropic');
  }

  return {
    content,
    provider: 'anthropic',
    model_id: modelId,
    inputTokens: data.usage?.input_tokens,
    outputTokens: data.usage?.output_tokens,
  };
}
