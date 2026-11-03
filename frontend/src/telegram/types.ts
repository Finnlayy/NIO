/** Mirrors `to_dict()` of `orchestrator/telegram/models.py`. */

export type LoginState = "unconfigured" | "disconnected" | "code_sent" | "needs_password" | "authorized";
export type SuggestionStatus = "pending" | "sending" | "sent" | "failed" | "dismissed";
export type ApprovalStatus = "pending" | "approved" | "rejected";
export type Direction = "bullish" | "bearish" | "neutral";

export interface Dialog {
  id: number;
  name: string;
  kind: "user" | "group" | "channel";
  is_bot: boolean;
  unread: number;
}

export interface Message {
  peer: number;
  msg_id: number;
  sender: string;
  text: string;
  ts: string;
  outgoing: boolean;
  is_bot: boolean;
}

export interface Suggestion {
  id: string;
  source_peer: number;
  target_peer: number;
  text: string;
  based_on_msg_id: number | null;
  origin: "llm" | "rules";
  status: SuggestionStatus;
  created_at: string;
  decided_at: string | null;
  error: string | null;
}

export interface Approval {
  id: string;
  request_id: string | null;
  title: string;
  detail: string;
  status: ApprovalStatus;
  created_at: string;
  decided_at: string | null;
  callback_url: string | null;
}

export interface Signal {
  id: string;
  symbol: string;
  direction: Direction;
  strength: number;
  peer: number;
  msg_id: number;
  evidence: string;
  created_at: string;
  kanban_task_id: string | null;
}

export interface TickReport {
  at: string;
  peers: number;
  fetched: number;
  routed: number;
  errors: string[];
  flood_wait_s: number | null;
}

export interface Quota {
  target: number;
  used: number;
  limit: number;
}

export interface Status {
  state: LoginState;
  me: { id: number; name: string; username: string } | null;
  flood_wait_until: string | null;
  gather: { running: boolean; last_tick: TickReport | null; interval_s: number };
  symbols: { count: number; source: string; loaded_at: string | null; quotes_count: number };
  llm_configured: boolean;
  kanban_enabled: boolean;
  send_rate_per_hour: number;
  send_quota: Quota[];
}

export interface Pairing {
  source: number;
  target: number;
}

export interface Allowlist {
  store: Array<number | string>;
  env: Array<number | string>;
}

export interface AskResult {
  symbol: string | null;
  context_count: number;
  answer: string;
  source: "llm" | "rules";
}

export interface TelegramData {
  status: Status | null;
  dialogs: Dialog[];
  monitored: number[];
  pairings: Pairing[];
  allowlist: Allowlist;
  suggestions: Suggestion[];
  approvals: Approval[];
  signals: Signal[];
  messages: Message[];
}
