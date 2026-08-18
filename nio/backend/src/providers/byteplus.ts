import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';
import { openAiCompatibleChat } from './openai_compatible';

const DEFAULT_BASE_URL = 'https://ark.ap-southeast.bytepluses.com/api/v3';

export function isBytePlusArkEnabled(): boolean {
  return Boolean(process.env.BYTEPLUS_ARK_API_KEY?.trim());
}

export function getBytePlusArkBaseUrl(): string {
  const base = process.env.BYTEPLUS_ARK_BASE_URL?.trim() || DEFAULT_BASE_URL;
  return base.replace(/\/$/, '');
}

export function getBytePlusArkModelId(): string {
  return (
    process.env.BYTEPLUS_ARK_MODEL?.trim() ||
    process.env.BYTEPLUS_API_NAME?.trim() ||
    'doubao-seed-1-6-250615'
  );
}

export async function bytePlusArkChat(
  messages: ChatMessage[],
  modelId?: string,
): Promise<ChatCompletionResult> {
  const apiKey = process.env.BYTEPLUS_ARK_API_KEY?.trim();
  if (!apiKey) {
    throw new ProviderError('BYTEPLUS_ARK_API_KEY is not set', 'byteplus', undefined, false);
  }

  const maxTokens = Number(process.env.BYTEPLUS_ARK_MAX_TOKENS ?? 512);
  return openAiCompatibleChat(
    'byteplus',
    getBytePlusArkBaseUrl(),
    apiKey,
    modelId ?? getBytePlusArkModelId(),
    messages,
    Number.isFinite(maxTokens) ? maxTokens : 512,
  );
}
