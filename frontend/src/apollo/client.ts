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

export async function kanbanRequest<T = unknown>(
  path: string,
  method: "GET" | "POST" | "DELETE" = "POST",
  payload?: unknown
): Promise<KanbanResult<T>> {
  try {
    const response = await fetch("/api/apollo/kanban", {
      method: "POST", // Proxied request is always POST to proxy
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, method, payload }),
      signal: AbortSignal.timeout(10_000),
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

const APOLLO_BOARD_NAME = "Apollo";

/* Boards get generated ids, so the Apollo board is found by name. */
export async function apolloBoardId(): Promise<KanbanResult<string>> {
  const boards = await kanbanRequest<{ id: string; name: string }[]>("/api/v1/kanban/boards", "GET");
  if (!boards.ok) return { ok: false, error: boards.error };
  const existing = boards.data?.find((board) => board.name === APOLLO_BOARD_NAME);
  if (existing) return { ok: true, data: existing.id };
  const created = await kanbanRequest<{ id: string }>("/api/v1/kanban/boards", "POST", { name: APOLLO_BOARD_NAME });
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
