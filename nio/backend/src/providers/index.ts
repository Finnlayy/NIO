import type { ResolvedModel } from '../../../shared/manifest-schema';
import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';
import { anthropicChat } from './anthropic';
import { bytePlusArkChat, isBytePlusArkEnabled } from './byteplus';
import { moonshotChat, xaiChat } from './extra_providers';
import {
  isLmStudioEnabled,
  lmStudioChat,
  lmStudioResolvedModel,
  resolveLmStudioModelId,
} from './lmstudio';
import { openAiChat } from './openai';
import { openRouterChat } from './openrouter';

/** Extra env-backed models tried when manifest providers fail. */
const EXTRA_CANDIDATES: Array<{ provider: string; model_id: string; hasKey: () => boolean; call: (messages: ChatMessage[]) => Promise<ChatCompletionResult> }> = [
  {
    provider: 'byteplus',
    model_id: process.env.BYTEPLUS_ARK_MODEL ?? process.env.BYTEPLUS_API_NAME ?? 'doubao-seed-1-6-250615',
    hasKey: isBytePlusArkEnabled,
    call: (messages) => bytePlusArkChat(messages),
  },
  {
    provider: 'xai',
    model_id: process.env.XAI_MODEL ?? 'grok-3-mini',
    hasKey: () => Boolean(process.env.XAI_API_KEY),
    call: (messages) => xaiChat(process.env.XAI_MODEL ?? 'grok-3-mini', messages),
  },
  {
    provider: 'moonshot',
    model_id: process.env.MOONSHOT_MODEL ?? 'moonshot-v1-8k',
    hasKey: () => Boolean(process.env.MOONSHOT_API_KEY),
    call: (messages) => moonshotChat(process.env.MOONSHOT_MODEL ?? 'moonshot-v1-8k', messages),
  },
];

function providerHasKey(provider: string): boolean {
  switch (provider) {
    case 'lmstudio':
      return isLmStudioEnabled();
    case 'byteplus':
      return isBytePlusArkEnabled();
    case 'openrouter':
      return Boolean(process.env.OPENROUTER_API_KEY);
    case 'openai':
      return Boolean(process.env.OPENAI_API_KEY);
    case 'anthropic':
      return Boolean(process.env.ANTHROPIC_API_KEY);
    case 'xai':
      return Boolean(process.env.XAI_API_KEY);
    case 'moonshot':
      return Boolean(process.env.MOONSHOT_API_KEY);
    default:
      return false;
  }
}

async function callProvider(
  model: ResolvedModel,
  messages: ChatMessage[],
): Promise<ChatCompletionResult> {
  switch (model.provider) {
    case 'lmstudio':
      return lmStudioChat(messages, model.model_id === 'local' ? undefined : model.model_id);
    case 'byteplus':
      return bytePlusArkChat(messages, model.model_id);
    case 'openrouter':
      return openRouterChat(model.model_id, messages);
    case 'openai':
      return openAiChat(model.model_id, messages);
    case 'anthropic':
      return anthropicChat(model.model_id, messages);
    default:
      throw new ProviderError(`Unsupported provider: ${model.provider}`, model.provider);
  }
}

/** Try models in order; skip providers without API keys. */
export async function chatWithFallback(
  candidates: ResolvedModel[],
  messages: ChatMessage[],
): Promise<ChatCompletionResult> {
  const errors: string[] = [];

  if (isLmStudioEnabled()) {
    const local = lmStudioResolvedModel();
    try {
      const modelId = await resolveLmStudioModelId();
      return await lmStudioChat(messages, modelId);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      errors.push(`lmstudio/${local.model_id}: ${message}`);
    }
  }

  for (const model of candidates) {
    if (!providerHasKey(model.provider)) {
      errors.push(`${model.provider}/${model.model_id}: no API key`);
      continue;
    }
    try {
      return await callProvider(model, messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      errors.push(`${model.provider}/${model.model_id}: ${message}`);
    }
  }

  for (const extra of EXTRA_CANDIDATES) {
    if (!extra.hasKey()) continue;
    try {
      return await extra.call(messages);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      errors.push(`${extra.provider}/${extra.model_id}: ${message}`);
    }
  }

  throw new ProviderError(
    `All model candidates failed:\n${errors.join('\n')}`,
    'router',
    undefined,
    false,
  );
}

export { providerHasKey, isBytePlusArkEnabled };
export { isLmStudioEnabled, lmStudioResolvedModel } from './lmstudio';
