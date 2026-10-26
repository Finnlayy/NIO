/* ==================================================================== */
/* NIO ⇄ APOLLO tool contract                                           */
/*                                                                      */
/* These types are the wire format between the Apollo orchestrator and  */
/* the neural graph UI. The first block is the published contract; the  */
/* second block is what the UI needs on top of it (spawn staging,       */
/* impulses, task state) and is deliberately additive.                  */
/* ==================================================================== */

export type OrbState =
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "FAILOVER_SWITCH"
  | "DISPATCHING"
  | "SYNTHESIZING"
  | "ERROR";

export type NodeState =
  | "LYMP_SPAWNING"
  | "IDLE"
  | "PROCESSING"
  | "STREAMING"
  | "COMPLETED"
  | "FAULT";

export type NodeCategory =
  | "ORCHESTRATOR"
  | "FREELLM_ROUTER"
  | "SANDBOX"
  | "MCP_WORKER"
  | "DATA_STREAM"
  | "INFERENCE"
  | "MEMORY";

export interface FreeLLMProviderKey {
  providerId:
    | "google"
    | "groq"
    | "mistral"
    | "cerebras"
    | "openrouter"
    | "nvidia"
    | "cohere"
    | "huggingface";
  name: string;
  keyMasked: string;
  status: "ACTIVE" | "LIMIT_REACHED" | "STANDBY";
}

export interface FreeLLMModelCandidate {
  id: string;
  name: string;
  provider: string;
  reliability: number; // 0-100
  speed: number; // 0-100
  intelligence: number; // 0-100
  compositeScore: number; // weighted score (default 50% reliability, 25% speed, 25% intelligence)
  status: "ACTIVE" | "READY" | "LIMIT_REACHED";
}

export interface FreeLLMRoutingConfig {
  enabled: boolean;
  endpointUrl: string; // e.g. local FreeLLMAPI OpenAI-compatible proxy
  weights: { reliability: number; speed: number; intelligence: number };
  enableContextHandoffNote: boolean;
  lastHandoffNote?: string;
  providers: FreeLLMProviderKey[];
  fallbackChain: FreeLLMModelCandidate[];
}

export interface NioNode {
  id: string;
  label: string;
  category: NodeCategory;
  state: NodeState;
  position: { x: number; y: number };
  metrics?: { latencyMs: number; load: number; activeProvider?: string };
  lastOutput?: string | Record<string, unknown>;
}

export interface TerminalLogEntry {
  id: string;
  timestamp: string;
  origin: "USER" | "APOLLO" | "NIO_CORE" | "FREELLM_ROUTER" | "MCP_SANDBOX";
  level: "CHAT" | "INFO" | "DISPATCH" | "FAILOVER" | "WARN" | "ERROR";
  message: string;
  activeModel?: string;
  handoffNote?: string;
  /* Additive (UI): an answer that came from local simulation, a one-line
     secondary line (CLI hint, upstream reason), and structured telemetry. */
  simulated?: boolean;
  detail?: string;
  data?: Record<string, unknown>;
}

export interface ApolloConfiguration {
  primaryModel: string;
  primaryQuotaPercent: number;
  /* Additive: the quota bar's auto-failover trigger, 0-100. */
  failoverThresholdPercent: number;
  temperature: number;
  maxTokens: number;
  executionPolicy: "AUTONOMOUS" | "CONSERVATIVE" | "SANDBOX_STRICT";
  allowDynamicNodeSpawn: boolean;
  allowAppMutation: boolean;
  /* Additive: gates `/sandbox exec`, mirroring the permissions panel. */
  allowSandboxShell: boolean;
  freeLLMRouting: FreeLLMRoutingConfig;
  activeMcpServers: string[];
  systemDirective: string;
}

/* -------------------------------------------------------------------- */
/* Additive UI contract                                                  */
/* -------------------------------------------------------------------- */

/** Anything the Apollo side may not do unless the operator enabled it. */
export type Permission = "spawn" | "mutate-ui" | "sandbox-shell";

export type ImpulseKind = "outbound" | "inbound" | "failover" | "handshake";

/** A travelling packet on an axon. Positions are derived, never stored. */
export interface Impulse {
  id: string;
  nodeId: string;
  kind: ImpulseKind;
  /** Origin variant: handshake travels node -> orb, the rest orb -> node. */
  direction: "orbit-to-node" | "node-to-orbit";
  startedAt: number;
  durationMs: number;
  label?: string;
  payload?: Record<string, unknown>;
}

/** Stage 1 of the Lymp animation: the droplet before it crystallises. */
export interface Vesicle {
  id: string;
  nodeId: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
  startedAt: number;
  durationMs: number;
  hue: string;
}

export interface TaskStep {
  id: string;
  label: string;
  status: "PENDING" | "RUNNING" | "DONE" | "FAILED";
  nodeId?: string;
  detail?: string;
}

export interface ActiveTask {
  id: string;
  label: string;
  prompt: string;
  startedAt: number;
  steps: TaskStep[];
  completed: string[];
  pending: string[];
}

export type TerminalMode = "unified" | "raw";

export interface RouterSnapshot {
  primaryModel: string;
  primaryQuotaPercent: number;
  activeModel: string;
  activeProvider: string;
  mode: "PRIMARY" | "FAILOVER" | "EXHAUSTED";
  poolEndpoints: number;
  poolProviders: number;
  failoverCount: number;
  latencyMs: number;
  lastHandoffNote?: string;
}

export interface CommandResult {
  ok: boolean;
  /** Entries the command produced, already formatted for the terminal. */
  entries: Array<Omit<TerminalLogEntry, "id" | "timestamp">>;
  /** Machine-readable echo for `--json` style consumers. */
  data?: Record<string, unknown>;
}
