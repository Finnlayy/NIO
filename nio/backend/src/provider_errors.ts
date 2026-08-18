/** Detect provider exhaustion / quota failures for user-facing alerts. */
export function isQuotaOrProviderExhausted(error: unknown): boolean {
  if (error instanceof Error && error.name === 'ProviderError') {
    return true;
  }
  const message = error instanceof Error ? error.message : String(error);
  return (
    message.includes('All model candidates failed') ||
    message.includes('402') ||
    message.includes('429') ||
    message.includes('403') ||
    message.includes('insufficient_quota') ||
    message.includes('requires more credits') ||
    message.includes('no API key') ||
    message.includes('LM Studio returned no loaded models')
  );
}

export const QUOTA_EXCEEDED_MESSAGE = 'Quota Exceeded';

export function toTaskErrorResponse(error: unknown): { error: string; code: string; detail?: string } {
  if (isQuotaOrProviderExhausted(error)) {
    return { error: QUOTA_EXCEEDED_MESSAGE, code: 'quota_exceeded' };
  }
  const detail = error instanceof Error ? error.message : String(error);
  return { error: detail, code: 'task_failed', detail };
}
