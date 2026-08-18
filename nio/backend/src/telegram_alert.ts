/** Fire-and-forget Telegram alert — same bot config as Cody (`telegram_notify.py`). */

const TELEGRAM_API = 'https://api.telegram.org/bot';

function telegramEnabled(): boolean {
  const flag = process.env.TELEGRAM_NOTIFICATIONS_ENABLED?.trim().toLowerCase();
  if (flag === '0' || flag === 'false' || flag === 'off') return false;
  return Boolean(process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID);
}

/** Send alert without blocking the HTTP response. */
export function notifyTelegram(text: string): void {
  if (!telegramEnabled()) return;

  const token = process.env.TELEGRAM_BOT_TOKEN!;
  const chatId = process.env.TELEGRAM_CHAT_ID!;

  void fetch(`${TELEGRAM_API}${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  }).catch((err) => {
    console.error('Telegram alert failed:', err instanceof Error ? err.message : err);
  });
}

export function notifyTelegramAlertAsync(message: string, source = 'NIO'): void {
  notifyTelegram(`⚡ Cody alert — ${source}\n${message}`);
}

export function notifyQuotaExceeded(source = 'neural-orchestrator'): void {
  notifyTelegramAlertAsync('Quota Exceeded', source);
}
