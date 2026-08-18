/**
 * Inter-agent communication types — orchestrator ↔ subagent messaging with hard gates.
 */

import type { TaskLimbContext } from '../limb_lifecycle';

export type AgentChannel = 'orchestrator' | 'subagent' | 'limb' | 'cody' | 'user';

export type GateKind =
  | 'budget_check'
  | 'policy_check'
  | 'telemetry_emit'
  | 'parent_approval';

export interface GateSpec {
  id: string;
  kind: GateKind;
  /** When true, failure blocks subagent dispatch. */
  required: boolean;
  description?: string;
}

export interface GateContext {
  taskDescription: string;
  source?: string;
  role?: string;
  templateId?: string;
  /** Set when operation is destructive (file delete, force push, etc.). */
  isDestructive?: boolean;
  /** Parent orchestrator explicitly approved destructive op. */
  parentApproved?: boolean;
  limbInstanceId?: string;
  subagentId?: string;
}

export interface GateResult {
  gateId: string;
  kind: GateKind;
  passed: boolean;
  required: boolean;
  reason?: string;
  timestamp: string;
}

export interface GateRunResult {
  passed: boolean;
  results: GateResult[];
  blockedBy?: string;
}

export type InterAgentMessageType =
  | 'dispatch'
  | 'gate_checkpoint'
  | 'task_result'
  | 'approval_request'
  | 'approval_response';

export interface InterAgentMessage {
  messageId: string;
  type: InterAgentMessageType;
  from: AgentChannel;
  to: AgentChannel;
  /** Target subagent / limb instance id when applicable. */
  targetId?: string;
  payload: Record<string, unknown>;
  timestamp: string;
  gateResults?: GateResult[];
}

/** Default gate pipeline for subagent dispatch (hard checkpoints). */
export const DEFAULT_SUBAGENT_GATE_SPECS: GateSpec[] = [
  {
    id: 'gate-budget',
    kind: 'budget_check',
    required: true,
    description: 'Daily model budget must not be exceeded (clamp or block).',
  },
  {
    id: 'gate-policy',
    kind: 'policy_check',
    required: true,
    description: 'Task must not violate orchestrator policy (empty/destructive without approval).',
  },
  {
    id: 'gate-telemetry',
    kind: 'telemetry_emit',
    required: true,
    description: 'Emit gate checkpoint telemetry before subagent proceeds.',
  },
  {
    id: 'gate-parent-approval',
    kind: 'parent_approval',
    required: true,
    description: 'Destructive operations require explicit parent approval.',
  },
];

export interface SubagentDispatchRequest {
  taskDescription: string;
  role?: string;
  templateId?: string;
  source?: string;
  isDestructive?: boolean;
  parentApproved?: boolean;
  gateSpecs?: GateSpec[];
}

export interface SubagentDispatchResult {
  dispatched: boolean;
  limbInstanceId?: string;
  taskId?: string;
  limbContext?: TaskLimbContext;
  gateRun: GateRunResult;
  messages: InterAgentMessage[];
}
