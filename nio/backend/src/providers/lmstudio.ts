import type { ChatCompletionResult, ChatMessage } from './chat_types';
import { ProviderError } from './chat_types';
import { openAiCompatibleChat } from './openai_compatible';

const DEFAULT_BASE_URL = 'http://localhost:1234/v1';
const DEFAULT_API_KEY = 'lm-studio';

let cachedModelId: string | null = null;

export function isLmStudioEnabled(): boolean {
  const flag = process.env.LMSTUDIO_ENABLED?.trim().toLowerCase();
  if (flag === '0' || flag === 'false' || flag === 'off') {
    return false;
  }
  if (flag === '1' || flag === 'true' || flag === 'on') {
    return true;
  }
  return Boolean(process.env.LMSTUDIO_BASE_URL?.trim());
}

export function getLmStudioBaseUrl(): string {
  const base = process.env.LMSTUDIO_BASE_URL?.trim() || DEFAULT_BASE_URL;
  return base.replace(/\/$/, '');
}

export function getLmStudioModelId(): string | undefined {
  const model = process.env.LMSTUDIO_MODEL?.trim();
  return model || undefined;
}

export async function resolveLmStudioModelId(): Promise<string> {
  const explicit = getLmStudioModelId();
  if (explicit) {
    return explicit;
  }
  if (cachedModelId) {
    return cachedModelId;
  }

  const response = await fetch(`${getLmStudioBaseUrl()}/models`);
  if (!response.ok) {
    const body = await response.text();
    throw new ProviderError(
      `LM Studio ${response.status}: ${body.slice(0, 300)}`,
      'lmstudio',
      response.status,
      response.status >= 500,
    );
  }

  const data = (await response.json()) as { data?: Array<{ id?: string }> };
  const modelId = data.data?.[0]?.id;
  if (!modelId) {
    throw new ProviderError(
      'LM Studio returned no loaded models. Load a model in LM Studio first.',
      'lmstudio',
    );
  }

  cachedModelId = modelId;
  return modelId;
}

export async function lmStudioChat(
  messages: ChatMessage[],
  modelId?: string,
): Promise<ChatCompletionResult> {
  const resolvedModelId = modelId ?? (await resolveLmStudioModelId());
  const apiKey = process.env.LMSTUDIO_API_KEY?.trim() || DEFAULT_API_KEY;
  const maxTokens = Number(process.env.LMSTUDIO_MAX_TOKENS ?? 512);

  return openAiCompatibleChat(
    'lmstudio',
    getLmStudioBaseUrl(),
    apiKey,
    resolvedModelId,
    messages,
    Number.isFinite(maxTokens) ? maxTokens : 512,
  );
}

export function lmStudioResolvedModel(): {
  provider: string;
  model_id: string;
  cost_per_1m_input: number;
} {
  return {
    provider: 'lmstudio',
    model_id: getLmStudioModelId() ?? 'local',
    cost_per_1m_input: 0,
  };
}
