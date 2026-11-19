export type AgentStateNode =
  | 'INGEST'
  | 'SANITIZE'
  | 'IDEMPOTENCY_LOCK'
  | 'GUARDIAN_AUDIT'
  | 'DISPATCH'
  | 'RECONCILE'
  | 'EMIT';

export interface AgentNodeTransition {
  node: AgentStateNode;
  status: 'PASSED' | 'BLOCKED' | 'SKIPPED' | 'EXECUTING';
  durationMs: number;
  details: string;
  timestamp: number;
}

export interface AgentToolInvocation {
  id: string;
  toolName: string;
  args: Record<string, any>;
  result: any;
  durationMs: number;
  timestamp: number;
}

export interface AgentTraceEvent {
  traceId: string;
  timestamp: number;
  trigger: 'USER_PROMPT' | 'SIGNAL_ALERT' | 'SWARM_HYPOTHESIS' | 'SCHEDULED_AUDIT';
  inputPrompt: string;
  sanitized: boolean;
  idempotencyKey: string;
  idempotencyLockHit: boolean;
  guardianStatus: 'APPROVED' | 'REJECTED' | 'AUTH_REQUIRED' | 'FLAGGED';
  guardianReason: string;
  nodes: AgentNodeTransition[];
  thoughtTrace: string;
  toolInvocations: AgentToolInvocation[];
  reconciledState: {
    navUsd: number;
    cashUsd: number;
    openPositionsCount: number;
    driftDetected: boolean;
    timestamp: number;
  };
  finalDecision: string;
  totalDurationMs: number;
}

export interface AgentStatus {
  online: boolean;
  model: string;
  systemPromptVersion: string;
  geminiApiKeyConfigured: boolean;
  totalCycles: number;
  passedAudits: number;
  blockedAudits: number;
  activeIdempotencyLocks: number;
  lastCycleTimestamp: number | null;
}
