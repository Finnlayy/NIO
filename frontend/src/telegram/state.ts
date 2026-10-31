import type { Allowlist, Approval, Dialog, Message, Quota, Signal, Status, Suggestion, TelegramData } from "./types";

export const MESSAGE_CAP = 300;
export const LIST_CAP = 200;

export function emptyData(): TelegramData {
  return {
    status: null,
    dialogs: [],
    monitored: [],
    pairings: [],
    allowlist: { store: [], env: [] },
    suggestions: [],
    approvals: [],
    signals: [],
    messages: [],
  };
}

/** Replaces by id, or prepends a new row; lists stay newest first. */
export function upsert<T extends { id: string }>(rows: T[], row: T): T[] {
  const index = rows.findIndex((r) => r.id === row.id);
  if (index < 0) return [row, ...rows].slice(0, LIST_CAP);
  const next = rows.slice();
  next[index] = row;
  return next;
}

/** Oldest first, deduped by (peer, msg_id): SSE can overlap a reload. */
export function mergeMessages(current: Message[], incoming: Message[]): Message[] {
  const byKey = new Map<string, Message>();
  for (const m of [...current, ...incoming]) byKey.set(`${m.peer}:${m.msg_id}`, m);
  return [...byKey.values()].sort((a, b) => a.ts.localeCompare(b.ts) || a.msg_id - b.msg_id).slice(-MESSAGE_CAP);
}

export function applyEvent(data: TelegramData, event: string, payload: unknown): TelegramData {
  switch (event) {
    case "message":
      return { ...data, messages: mergeMessages(data.messages, [payload as Message]) };
    case "signal":
      return { ...data, signals: upsert(data.signals, payload as Signal) };
    case "suggestion":
      return { ...data, suggestions: upsert(data.suggestions, payload as Suggestion) };
    case "approval":
      return { ...data, approvals: upsert(data.approvals, payload as Approval) };
    case "kanban_task": {
      const { signal_id, task_id } = payload as { signal_id: string; task_id: string };
      return { ...data, signals: data.signals.map((s) => (s.id === signal_id ? { ...s, kanban_task_id: task_id } : s)) };
    }
    default:
      return data;
  }
}

export function peerName(dialogs: Dialog[], peer: number): string {
  return dialogs.find((d) => d.id === peer)?.name || String(peer);
}

export function sendAllowed(allowlist: Allowlist, peer: number): boolean {
  return allowlist.store.includes(peer) || allowlist.env.includes(peer);
}

export function pairedTarget(data: Pick<TelegramData, "pairings">, source: number): number | null {
  return data.pairings.find((p) => p.source === source)?.target ?? null;
}

export function quotaFor(status: Status | null, target: number): Quota | null {
  return status?.send_quota.find((q) => q.target === target) ?? null;
}

export function quotaLeft(quota: Quota): number {
  return Math.max(0, quota.limit - quota.used);
}

export function openSuggestions(rows: Suggestion[]): Suggestion[] {
  return rows.filter((s) => s.status === "pending" || s.status === "sending" || s.status === "failed");
}

export function recentSent(rows: Suggestion[], count = 5): Suggestion[] {
  return rows.filter((s) => s.status === "sent").slice(0, count);
}

export type ConnectionTone = "ok" | "warn" | "off";

export interface ConnectionView {
  tone: ConnectionTone;
  label: string;
  hint: string | null;
}

export function connectionView(status: Status | null, errorCode: string | null): ConnectionView {
  if (errorCode === "not_running") {
    return { tone: "off", label: "Nicht gestartet", hint: "Telegram läuft nicht in der Hermes-API." };
  }
  if (errorCode === "no_token") {
    return { tone: "off", label: "Kein Token", hint: "NIO_KANBAN_API_TOKEN fehlt in frontend/.env.local." };
  }
  if (errorCode === "backend_down") {
    return { tone: "off", label: "API offline", hint: "Die Hermes-API antwortet nicht. Läuft neu kanban serve?" };
  }
  if (!status) return { tone: "off", label: "Lädt", hint: null };
  if (status.state === "authorized") return { tone: "ok", label: "Verbunden", hint: null };
  if (status.state === "unconfigured") {
    return { tone: "off", label: "Nicht eingerichtet", hint: "NIO_TELEGRAM_API_ID und NIO_TELEGRAM_API_HASH fehlen." };
  }
  return { tone: "warn", label: "Nicht eingeloggt", hint: "Login nur per CLI: neu telegram login, danach serve neu starten." };
}

export function formatWait(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  return `${Math.ceil(seconds / 60)} min`;
}

export function formatTime(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}
