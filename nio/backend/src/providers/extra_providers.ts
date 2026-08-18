import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';
import { openAiCompatibleChat } from './openai_compatible';

export async function xaiChat(
  modelId: string,
  messages: ChatMessage[],
): Promise<ChatCompletionResult> {
  const apiKey = process.env.XAI_API_KEY;
  if (!apiKey) {
    throw new ProviderError('XAI_API_KEY is not set', 'xai', undefined, false);
  }
  const baseUrl = process.env.XAI_BASE_URL ?? 'https://api.x.ai/v1';
  return openAiCompatibleChat('xai', baseUrl, apiKey, modelId, messages);
}

export async function moonshotChat(
  modelId: string,
  messages: ChatMessage[],
): Promise<ChatCompletionResult> {
  const apiKey = process.env.MOONSHOT_API_KEY;
  if (!apiKey) {
    throw new ProviderError('MOONSHOT_API_KEY is not set', 'moonshot', undefined, false);
  }
  const baseUrl = process.env.MOONSHOT_BASE_URL ?? 'https://api.moonshot.cn/v1';
  return openAiCompatibleChat('moonshot', baseUrl, apiKey, modelId, messages);
}
