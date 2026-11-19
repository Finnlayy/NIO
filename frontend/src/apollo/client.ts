/** Live server bridge: errors stay errors; there is no simulated fallback. */

export interface SynthesisRequest {
  endpointUrl: string;
  providerId?: string;
  model: string;
  messages: Array<{ role: "system" | "user" | "assistant"; content: string }>;
  temperature: number;
  maxTokens: number;
}

export interface SynthesisResult {
  ok: boolean;
  text: string;
  provider?: string;
  model?: string;
  latencyMs?: number;
  error?: string;
}

/** Ask the server-side proxy; never call a third-party origin from the tab. */
export async function requestSynthesis(payload: SynthesisRequest): Promise<SynthesisResult> {
  const started = Date.now();
  try {
    const response = await fetch("/api/apollo", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(25_000),
    });
    const data = (await response.json()) as {
      ok?: boolean;
      text?: string;
      provider?: string;
      model?: string;
      error?: string;
    };
    return {
      ok: Boolean(response.ok && data.ok),
      text: data.text ?? "",
      provider: data.provider,
      model: data.model,
      latencyMs: Date.now() - started,
      error: data.error ?? (response.ok ? undefined : `HTTP ${response.status}`),
    };
  } catch (error) {
    return {
      ok: false,
      text: "",
      latencyMs: Date.now() - started,
      error: error instanceof Error ? error.message : "network error",
    };
  }
}

export interface SandboxResult {
  ok: boolean;
  command: string;
  stdout: string;
  code: number;
  error?: string;
  mode?: string;
}

/** Read-only command jail; the route enforces the allowlist, not the client. */
export async function runSandboxCommand(command: string): Promise<SandboxResult> {
  try {
    const response = await fetch("/api/sandbox", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ command }),
      signal: AbortSignal.timeout(8_000),
    });
    const data = (await response.json()) as Partial<SandboxResult> & { error?: string };
    return {
      ok: Boolean(response.ok && data.ok),
      command,
      stdout: data.stdout ?? "",
      code: data.code ?? (response.ok ? 0 : 1),
      error: data.error,
      mode: data.mode,
    };
  } catch (error) {
    return {
      ok: false,
      command,
      stdout: "",
      code: 1,
      error: error instanceof Error ? error.message : "network error",
    };
  }
}

export interface VaultNote {
  path: string;
  title: string;
  snippet: string;
}

export interface VaultResult {
  ok: boolean;
  path?: string;
  committed?: boolean;
  notes?: VaultNote[];
  error?: string;
}

/** Notes stay on this machine; the route runs them through the orchestrator. */
export async function callVault(request: { action: "search"; query: string } | { action: "capture"; text: string }): Promise<VaultResult> {
  try {
    const response = await fetch("/api/apollo/vault", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(16_000),
    });
    const data = (await response.json()) as Partial<VaultResult>;
    return { ...data, ok: Boolean(response.ok && data.ok) };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "network error" };
  }
}


export interface KanbanResult<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}

/** Ein Signal, das nach `timeoutMs` oder beim Abbruch von `extra` auslöst (ohne `AbortSignal.any`). */
export function combinedSignal(timeoutMs: number, extra?: AbortSignal): AbortSignal {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  if (extra) {
    if (extra.aborted) controller.abort();
    else extra.addEventListener("abort", () => controller.abort(), { once: true });
  }
  controller.signal.addEventListener("abort", () => clearTimeout(timer), { once: true });
  return controller.signal;
}

export async function kanbanRequest<T = unknown>(
  path: string,
  method: "GET" | "POST" | "DELETE" = "POST",
  payload?: unknown,
  signal?: AbortSignal,
): Promise<KanbanResult<T>> {
  try {
    const response = await fetch("/api/apollo/kanban", {
      method: "POST", // Proxied request is always POST to proxy
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, method, payload }),
      signal: combinedSignal(10_000, signal),
    });
    const data = await response.json();

    // Server returns plain error JSON on proxy failure (400, 403, 503)
    if (!response.ok && data && typeof data.error === 'string') {
       return { ok: false, error: data.error };
    }

    // Target backend response (Kanban API)
    if (!response.ok) {
       const detail = data?.detail || `HTTP ${response.status}`;
       return { ok: false, error: detail };
    }

    return { ok: true, data: data as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "network error" };
  }
}

/* ==================================================================== */
/* Control plane (Phase 4): /api/runtime über den Server-Proxy            */
/* Das Operator-Token liegt nur im Server; hier fließt nie ein Secret.    */
/* ==================================================================== */

export interface DagLineage {
  session_id: string;
  branch_name: string;
  head_turn_id: string | null;
  ordered_turn_ids: string[];
  messages: Array<Record<string, unknown>>;
  working_state: Record<string, unknown>;
}

export interface DagView {
  lineage: DagLineage;
  branches: Record<string, string | null>;
}

export interface PendingApproval {
  id: string;
  session_id: string;
  tool: string;
  status: string;
  expires_ms: number;
}

/** Fehler der API kommen als `detail` (FastAPI) oder `error` (Proxy); beides wird gelesen. */
export async function runtimeRequest<T = unknown>(
  path: string,
  method: "GET" | "POST",
  payload?: unknown,
  signal?: AbortSignal,
): Promise<KanbanResult<T>> {
  try {
    const response = await fetch(`/api/runtime${path}`, {
      method,
      headers: payload === undefined ? undefined : { "content-type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      cache: "no-store",
      signal: combinedSignal(10_000, signal),
    });
    const data = (await response.json().catch(() => null)) as { detail?: unknown; error?: unknown } | null;
    if (!response.ok) {
      const message = typeof data?.error === "string" ? data.error : typeof data?.detail === "string" ? data.detail : `HTTP ${response.status}`;
      return { ok: false, error: message };
    }
    return { ok: true, data: data as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "network error" };
  }
}

export interface ApprovalStreamHandlers {
  onPending: (ticket: PendingApproval) => void;
  onResolved: (ticketId: string) => void;
  onAbort?: (sessionId: string, reason: string) => void;
}

/**
 * Abonniert den Freigabe-Strom (SSE über den Kanban-Bus). Kein Polling.
 * Gibt die Schließfunktion zurück; ohne EventSource (SSR, Tests) passiert nichts.
 */
export function subscribeApprovalStream(handlers: ApprovalStreamHandlers): () => void {
  if (typeof EventSource === "undefined") return () => {};
  const source = new EventSource("/api/runtime/approvals/stream");
  const payloadOf = <T,>(event: Event): T | null => {
    try {
      return ((JSON.parse((event as MessageEvent<string>).data) as { payload?: T }).payload ?? null) as T | null;
    } catch {
      return null;
    }
  };
  source.addEventListener("approval.pending", (event) => {
    const p = payloadOf<Omit<PendingApproval, "id"> & { ticket_id: string }>(event);
    if (p) handlers.onPending({ id: p.ticket_id, session_id: p.session_id, tool: p.tool, status: p.status, expires_ms: p.expires_ms });
  });
  source.addEventListener("approval.resolved", (event) => {
    const p = payloadOf<{ ticket_id: string }>(event);
    if (p) handlers.onResolved(p.ticket_id);
  });
  source.addEventListener("runtime.abort", (event) => {
    const p = payloadOf<{ session_id: string; reason: string }>(event);
    if (p) handlers.onAbort?.(p.session_id, p.reason);
  });
  return () => source.close();
}

const APOLLO_BOARD_NAME = "Apollo";

/* Boards get generated ids, so the Apollo board is found by name. */
export async function apolloBoardId(signal?: AbortSignal): Promise<KanbanResult<string>> {
  const boards = await kanbanRequest<{ id: string; name: string }[]>("/api/v1/kanban/boards", "GET", undefined, signal);
  if (!boards.ok) return { ok: false, error: boards.error };
  const existing = boards.data?.find((board) => board.name === APOLLO_BOARD_NAME);
  if (existing) return { ok: true, data: existing.id };
  const created = await kanbanRequest<{ id: string }>("/api/v1/kanban/boards", "POST", { name: APOLLO_BOARD_NAME }, signal);
  if (!created.ok || !created.data) return { ok: false, error: created.error ?? "board not created" };
  return { ok: true, data: created.data.id };
}

export async function createApolloTask(title: string, description: string): Promise<KanbanResult<{ id: string }>> {
  const board = await apolloBoardId();
  if (!board.ok) return { ok: false, error: board.error };
  return kanbanRequest<{ id: string }>("/api/v1/kanban/tasks", "POST", {
    board_id: board.data,
    title,
    description,
    dependencies: [],
    required_skills: [],
  });
}

/** Skill of the chat worker (`deploy/workers/apollo.soul.md`); other workers never pick chat tasks. */
export const CHAT_SKILL = "apollo";
const CHAT_TITLE_MAX = 120;

export interface ChatTask {
  id: string;
  board_id: string;
  status: string;
  block_reason?: string;
  result_payload?: { text?: string; provider?: string; model?: string } | null;
}

/** Title is the first line (clipped); the full text goes to the description only when it adds something. */
export function chatTaskFields(text: string): { title: string; description: string } {
  const clean = text.trim();
  const firstLine = clean.split(/\r?\n/, 1)[0];
  const title = firstLine.length > CHAT_TITLE_MAX ? `${firstLine.slice(0, CHAT_TITLE_MAX - 1)}…` : firstLine;
  return { title, description: title === clean ? "" : clean };
}

export async function createChatTask(text: string, signal?: AbortSignal): Promise<KanbanResult<ChatTask>> {
  const board = await apolloBoardId(signal);
  if (!board.ok) return { ok: false, error: board.error };
  return kanbanRequest<ChatTask>(
    "/api/v1/kanban/tasks",
    "POST",
    {
      board_id: board.data,
      ...chatTaskFields(text),
      dependencies: [],
      required_skills: [CHAT_SKILL],
    },
    signal,
  );
}

export async function fetchChatTask(boardId: string, taskId: string, signal?: AbortSignal): Promise<KanbanResult<ChatTask>> {
  const tasks = await kanbanRequest<ChatTask[]>(
    `/api/v1/kanban/tasks?board_id=${encodeURIComponent(boardId)}`,
    "GET",
    undefined,
    signal,
  );
  if (!tasks.ok) return { ok: false, error: tasks.error };
  const task = tasks.data?.find((candidate) => candidate.id === taskId);
  return task ? { ok: true, data: task } : { ok: false, error: "task_not_found" };
}

export interface OpsRun {
  run_id: string;
  agent: string;
  state: string;
  created_at: string;
}

export async function fetchRuns(): Promise<KanbanResult<OpsRun[]>> {
  try {
    const response = await fetch("/api/ops", { cache: "no-store", signal: AbortSignal.timeout(10_000) });
    if (!response.ok) return { ok: false, error: `HTTP ${response.status}` };
    const data = (await response.json()) as { runs?: OpsRun[]; errors?: { runs?: boolean } };
    if (data.errors?.runs) return { ok: false, error: "run store unreadable" };
    return { ok: true, data: data.runs ?? [] };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "network error" };
  }
}

export async function secureKanbanRequest<T = unknown>(
  path: string,
  method: "POST" | "DELETE",
  pin: string,
  payload?: unknown
): Promise<KanbanResult<T>> {
  try {
    const response = await fetch("/api/apollo/kanban/secure", {
      method: "POST", // Proxied request is always POST to proxy
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, method, pin, payload }),
      signal: AbortSignal.timeout(10_000),
    });
    const data = await response.json();

    if (!response.ok && data && typeof data.error === 'string') {
       return { ok: false, error: data.error };
    }

    if (!response.ok) {
       const detail = data?.detail || `HTTP ${response.status}`;
       return { ok: false, error: detail };
    }

    return { ok: true, data: data as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "network error" };
  }
}
