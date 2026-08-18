import type {
  AgentRegistryEntry,
  CodyChatResponse,
  CodyCommsResponse,
  CodyStats,
  CodySupervisorStatus,
  CommsFilterScope,
  ModelManifest,
  ResolvedModel,
  TaskResponse,
  TelemetryEvent,
} from "./manifest-types";

const API_BASE =
  typeof window !== "undefined"
    ? "/nio-api"
    : (process.env.NIO_API_URL ?? "http://localhost:4000");

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error ?? `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const data = await fetchJson<{ status: string }>("/health");
    return data.status === "ok";
  } catch {
    return false;
  }
}

export async function fetchManifest(): Promise<ModelManifest> {
  return fetchJson<ModelManifest>("/api/models/manifest");
}

export async function resolveModel(role: string): Promise<ResolvedModel> {
  return fetchJson<ResolvedModel>(`/api/models/resolve?role=${encodeURIComponent(role)}`);
}

export async function fetchTelemetry(limit = 20): Promise<TelemetryEvent[]> {
  const data = await fetchJson<{ events: TelemetryEvent[] }>(`/api/telemetry?limit=${limit}`);
  return data.events;
}

export async function fetchAgentRegistry(): Promise<{
  agents: AgentRegistryEntry[];
  budget: {
    dailySpendUsd: number;
    dailyBudgetUsd: number;
    swarmBudgetUsd: number;
    onExceeded: string;
  };
}> {
  return fetchJson("/api/agents/registry");
}

export async function fetchCodyStats(): Promise<CodyStats> {
  return fetchJson<CodyStats>("/api/agents/cody/stats");
}

export async function fetchCodySupervisor(): Promise<CodySupervisorStatus> {
  return fetchJson<CodySupervisorStatus>("/api/agents/cody/supervisor");
}

export async function fetchCodyComms(opts?: {
  since?: string;
  filter?: CommsFilterScope;
  limit?: number;
}): Promise<CodyCommsResponse> {
  const params = new URLSearchParams();
  if (opts?.since) params.set("since", opts.since);
  if (opts?.filter) params.set("filter", opts.filter);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<CodyCommsResponse>(`/api/agents/cody/comms${qs}`);
}

export async function postInterAgentApproval(body: {
  messageId: string;
  approved: boolean;
  reason?: string;
}): Promise<{ ok: boolean; responseMessageId?: string }> {
  return fetchJson("/api/inter-agent/approve", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function sendCodyChatMessage(body: {
  message: string;
  sessionId?: string;
  history?: Array<{ role: "user" | "assistant"; content: string }>;
  publishToBus?: boolean;
}): Promise<CodyChatResponse> {
  return fetchJson<CodyChatResponse>("/api/agents/cody/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchActiveLimbs(): Promise<{ limbs: import("./manifest-types").LimbInstance[] }> {
  return fetchJson("/api/limbs/active");
}

export async function fetchLibraryTemplates(): Promise<{ templates: import("./manifest-types").LimbTemplate[] }> {
  return fetchJson("/api/library/templates");
}

export async function fetchLibraryArchive(
  limit = 50,
): Promise<{ entries: import("./manifest-types").ArchiveEntry[] }> {
  return fetchJson(`/api/library/archive?limit=${limit}`);
}

export async function proposeManifestMutation(body: {
  target: string;
  agentId?: string;
  op: string;
  value: unknown;
  reason: string;
  evidence: number[];
  boundaryVerdict: {
    allowed: boolean;
    violations: string[];
    warnings: string[];
    path: string;
  };
}): Promise<{ proposal: import("./manifest-types").ManifestProposal; canApply: boolean }> {
  return fetchJson("/api/manifest/propose", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function submitCrossReview(
  proposalId: string,
  body: { verdict: "approved" | "changes_requested"; notes?: string },
): Promise<{ proposal: import("./manifest-types").ManifestProposal }> {
  return fetchJson(`/api/manifest/review/${proposalId}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function applyManifestProposal(
  proposalId: string,
): Promise<{ applied: boolean; proposal: import("./manifest-types").ManifestProposal }> {
  return fetchJson(`/api/manifest/apply/${proposalId}`, { method: "POST" });
}

export interface RunTaskBody {
  taskDescription: string;
  isComplexWorkflow?: boolean;
  role?: string;
  domainHint?: string;
  algorithmTag?: string;
  politenessTier?: string;
  source?: "telegram" | "api" | "console";
  templateId?: string;
}

export async function runTask(body: RunTaskBody): Promise<TaskResponse> {
  return fetchJson<TaskResponse>("/api/task", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function dispatchSubagent(body: {
  taskDescription: string;
  role?: string;
  templateId?: string;
  source?: string;
  isDestructive?: boolean;
  parentApproved?: boolean;
}): Promise<{
  dispatched: boolean;
  limbInstanceId?: string;
  taskId?: string;
  gateRun: { passed: boolean; blockedBy?: string };
}> {
  return fetchJson("/api/inter-agent/dispatch", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
