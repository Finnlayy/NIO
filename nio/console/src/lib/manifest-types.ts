export type ModelTier = "frontier" | "standard" | "economy" | "free";

export type AgentRole =
  | "coordinator"
  | "judge"
  | "gate"
  | "worker"
  | "aggregator"
  | "heartbeat"
  | "invent-skills-draft";

export interface ResolvedModel {
  tier: ModelTier;
  provider: string;
  model_id: string;
  cost_per_1m_input: number;
}

export interface ModelManifest {
  version: number;
  defaults: {
    fallback_chain: ModelTier[];
    cost_budget_usd_per_swarm: number;
    cost_budget_usd_per_day: number;
    on_daily_budget_exceeded: string;
    daily_budget_reset: string;
  };
  providers: Record<string, Record<string, string>>;
  tiers: Record<
    ModelTier,
    {
      priority: number;
      models: Array<{ provider: string; model_id: string; cost_per_1m_input: number }>;
      rate_limit_rpm?: number;
    }
  >;
  role_overrides: Record<string, ModelTier>;
}

export interface AgentRegistryEntry {
  agentId: string;
  displayName: string;
  role: AgentRole;
  modelTier: ModelTier;
  resolvedModel: ResolvedModel;
  description?: string;
}

export interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  domain: string;
  algorithmTag: string | null;
  isComplex: boolean;
  politenessTier: string;
  urgencyTier: string;
  promptVariant: string;
  expectedAccuracy: number;
  observedAccuracy?: number;
  latencyMs?: number;
  taskDescriptionHash: string;
  source?: "telegram" | "api" | "console";
  agentId?: string;
  limbInstanceId?: string;
}

export interface TaskResponse {
  coreNodeId: string;
  output: string;
  latencyMs: number;
  metadata: Record<string, unknown>;
}

export interface CodyStats {
  agentId: "cody";
  displayName: string;
  role?: "supervisor";
  online: boolean;
  startedAt: string | null;
  lastHeartbeatAt: string | null;
  lastActivityAt: string | null;
  uptimeMs: number;
  messagesUser: number;
  messagesAssistant: number;
  messagesTotal: number;
  nioTasksTotal: number;
  nioTasksSuccess: number;
  nioTasksFailed: number;
  quotaEvents: number;
  telegramTelemetryCount: number;
  route: string;
  channels?: { telegram: boolean; console: boolean };
  supervisor?: {
    nioHealthy: boolean;
    activeLimbCount: number;
    gateFailuresRecent: number;
    persistenceEnabled: boolean;
    summary: string;
  };
}

export type CodyMood =
  | "offline"
  | "idle"
  | "listening"
  | "thinking"
  | "working"
  | "alert"
  | "celebrating";

export type InterAgentMessageType =
  | "dispatch"
  | "gate_checkpoint"
  | "task_result"
  | "approval_request"
  | "approval_response"
  | "user_message"
  | "cody_relay";

export type AgentChannel = "orchestrator" | "subagent" | "limb" | "cody" | "user";

export interface FormattedInterAgentLine {
  messageId: string;
  timestamp: string;
  severity: "info" | "success" | "warning" | "error";
  headline: string;
  body: string;
  actors: { from: string; to: string };
  type?: InterAgentMessageType;
  isUserVisible?: boolean;
  channel?: { from: AgentChannel; to: AgentChannel };
  requiresAction?: boolean;
  actionPayload?: {
    gateId?: string;
    taskId?: string;
    blockedBy?: string;
  };
}

export interface CodySupervisorStatus {
  role: "supervisor";
  nioHealthy: boolean;
  coreAdapter: string;
  activeLimbCount: number;
  gateFailuresRecent: number;
  summary: string;
  interAgentTimeline?: FormattedInterAgentLine[];
  budget?: {
    dailySpendUsd: number;
    dailyBudgetUsd: number;
    onExceeded: string;
  };
}

export interface CodyChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  severity?: FormattedInterAgentLine["severity"];
}

export interface CodyChatResponse {
  reply: string;
  sessionId: string;
  source: "console";
  supervisorSnapshot?: {
    summary: string;
    activeLimbCount: number;
    gateFailuresRecent: number;
  };
  isStatusReport: boolean;
  latencyMs: number;
}

export type CommsFilterScope = "relevant" | "all";

export interface CodyCommsResponse {
  timeline: FormattedInterAgentLine[];
  latestMessageId: string | null;
  filter?: CommsFilterScope;
  totalAvailable?: number;
}

export type LimbLifecycleState =
  | "draft"
  | "deployed"
  | "active"
  | "completing"
  | "post-mortem"
  | "archived"
  | "failed";

export interface LimbInstance {
  limb_instance_id: string;
  template_id: string;
  mock_id: string;
  display_name: string;
  task_id: string;
  state: LimbLifecycleState;
  agentId: string;
  deployed_at: string;
  activated_at?: string;
  completed_at?: string;
  archived_at?: string;
  latency_ms?: number;
}

export interface LimbTemplate {
  template_id: string;
  mock_id: string;
  display_name: string;
  role: string;
  tools: string[];
  model_tier: ModelTier;
  limb_runtime: string;
  output_contract?: string;
  routing_weight?: number;
  requires_cross_review?: boolean;
  description?: string;
}

export interface ArchiveEntry {
  archive_id: string;
  limb_instance_id: string;
  template_id: string;
  task_id: string;
  archived_at: string;
  post_mortem: {
    whatWorked: string[];
    whatFailed: string[];
    learningDelta: number;
  };
}

export interface ManifestProposal {
  proposal_id: string;
  created_at: string;
  target: "core" | "limb" | "policy";
  agent_id?: string;
  op: string;
  reason: string;
  requires_cross_review: boolean;
  boundary_allowed: boolean;
  review_verdict: "pending" | "approved" | "changes_requested";
  review_notes?: string;
}

export const TIER_PRIORITY: Record<ModelTier, number> = {
  frontier: 1,
  standard: 2,
  economy: 3,
  free: 4,
};

export const MANIFEST_MODEL_TIERS: Record<string, ModelTier> = {
  "claude-opus-4-6": "frontier",
  "gpt-5.2": "frontier",
  "google/gemini-3.1-pro-preview": "frontier",
  "anthropic/claude-sonnet-4": "standard",
  "gpt-4o": "standard",
  "google/gemini-2.5-flash": "economy",
  "gpt-4o-mini": "economy",
  "google/gemini-2.0-flash-exp:free": "free",
  "qwen/qwen-2.5-72b-instruct:free": "free",
};
