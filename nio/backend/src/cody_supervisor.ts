/**
 * Cody supervisor — cross-layer status aggregation for the human-facing coordinator.
 * Cody monitors orchestrator, subagents/limbs, gates, budget, and persistence.
 */

import type { LimbInstanceStore } from './limb_instance_store';
import type { ModelRouter } from './model_router';
import type { TelemetrySink, TelemetryEvent } from './types';
import { conversationSessionStore } from './conversation_session_store';
import type { InterAgentMessage, GateResult } from './inter_agent/types';
import { interAgentMessageBus } from './inter_agent/message_bus';
import {
  formatInterAgentTimeline,
  filterTimelineSince,
  type FormattedInterAgentLine,
} from './inter_agent/format';

export interface CodySupervisorLimbStatus {
  limbInstanceId: string;
  displayName: string;
  templateId: string;
  taskId: string;
  state: string;
  source?: string;
  latencyMs?: number;
}

export interface CodySupervisorGateEvent {
  gateId: string;
  kind: string;
  passed: boolean;
  reason?: string;
  timestamp: string;
  blockedDispatch?: boolean;
}

export interface CodySupervisorStatus {
  role: 'supervisor';
  nioHealthy: boolean;
  coreAdapter: string;
  activeLimbs: CodySupervisorLimbStatus[];
  activeLimbCount: number;
  budget: {
    dailySpendUsd: number;
    dailyBudgetUsd: number;
    onExceeded: string;
  };
  gateEventsRecent: CodySupervisorGateEvent[];
  gateFailuresRecent: number;
  interAgentMessagesRecent: InterAgentMessage[];
  interAgentTimeline: FormattedInterAgentLine[];
  persistenceEnabled: boolean;
  recentTelemetryCount: number;
  lastTaskAt: string | null;
  summary: string;
}

export interface CodySupervisorDeps {
  coreAdapterMode: string;
  nioHealthy: boolean;
  limbInstanceStore: LimbInstanceStore;
  modelRouter: ModelRouter;
  telemetry: TelemetrySink & { recent?(limit: number): TelemetryEvent[] };
}

function limbsToStatus(store: LimbInstanceStore): CodySupervisorLimbStatus[] {
  return store.getActive().map((l) => ({
    limbInstanceId: l.limb_instance_id,
    displayName: l.display_name,
    templateId: l.template_id,
    taskId: l.task_id,
    state: l.state,
    source: l.source,
    latencyMs: l.latency_ms,
  }));
}

function gateEventsFromMessages(limit: number): CodySupervisorGateEvent[] {
  const events: CodySupervisorGateEvent[] = [];

  for (const msg of interAgentMessageBus.recent(limit * 2)) {
    if (msg.type !== 'gate_checkpoint' && msg.type !== 'dispatch') continue;
    for (const gr of msg.gateResults ?? []) {
      events.push({
        gateId: gr.gateId,
        kind: gr.kind,
        passed: gr.passed,
        reason: gr.reason,
        timestamp: gr.timestamp,
        blockedDispatch: msg.type === 'gate_checkpoint' && !gr.passed,
      });
    }
  }
  return events.slice(0, limit);
}

function buildSummary(
  limbs: CodySupervisorLimbStatus[],
  gateFailures: number,
  budget: CodySupervisorStatus['budget'],
  nioHealthy: boolean,
): string {
  const parts: string[] = [];
  parts.push(nioHealthy ? 'NIO online' : 'NIO offline');
  parts.push(`${limbs.length} active limb${limbs.length === 1 ? '' : 's'}`);
  if (gateFailures > 0) parts.push(`${gateFailures} recent gate failure(s)`);
  parts.push(`budget $${budget.dailySpendUsd.toFixed(2)}/$${budget.dailyBudgetUsd}`);
  return parts.join(' · ');
}

/** Aggregate supervisor dashboard Cody reads for monitoring + mediation. */
export function buildCodySupervisorStatus(deps: CodySupervisorDeps): CodySupervisorStatus {
  const activeLimbs = limbsToStatus(deps.limbInstanceStore);
  const budgetStatus = deps.modelRouter.getBudgetStatus();
  const gateEventsRecent = gateEventsFromMessages(15);
  const gateFailuresRecent = gateEventsRecent.filter((g) => !g.passed).length;
  const interAgentMessagesRecent = interAgentMessageBus.recent(20);
  const interAgentTimeline = formatInterAgentTimeline(interAgentMessagesRecent);
  const recentTelemetry = deps.telemetry.recent?.(50) ?? [];
  const lastTask = recentTelemetry.find((e) => e.agentId && !e.agentId.startsWith('gate:'));

  return {
    role: 'supervisor',
    nioHealthy: deps.nioHealthy,
    coreAdapter: deps.coreAdapterMode,
    activeLimbs,
    activeLimbCount: activeLimbs.length,
    budget: {
      dailySpendUsd: budgetStatus.dailySpendUsd,
      dailyBudgetUsd: budgetStatus.dailyBudgetUsd,
      onExceeded: budgetStatus.onExceeded,
    },
    gateEventsRecent,
    gateFailuresRecent,
    interAgentMessagesRecent,
    interAgentTimeline,
    persistenceEnabled: conversationSessionStore.isEnabled(),
    recentTelemetryCount: recentTelemetry.length,
    lastTaskAt: lastTask?.timestamp ?? null,
    summary: buildSummary(
      activeLimbs,
      gateFailuresRecent,
      {
        dailySpendUsd: budgetStatus.dailySpendUsd,
        dailyBudgetUsd: budgetStatus.dailyBudgetUsd,
        onExceeded: budgetStatus.onExceeded,
      },
      deps.nioHealthy,
    ),
  };
}

/** Format gate results for Cody → user Telegram mediation. */
export function formatGateAlert(gateResults: GateResult[], blockedBy?: string): string {
  const failed = gateResults.filter((g) => !g.passed);
  if (failed.length === 0) return '';
  const lines = failed.map((g) => `• ${g.gateId} (${g.kind}): ${g.reason ?? 'failed'}`);
  const header = blockedBy
    ? `⚠️ Gate blocked dispatch at \`${blockedBy}\`:`
    : '⚠️ Gate checkpoint failed:';
  return `${header}\n${lines.join('\n')}`;
}

/** Human-readable status report for "what are agents doing?" */
export function formatSupervisorReport(status: CodySupervisorStatus): string {
  const lines: string[] = [
    `📊 Agent status — ${status.summary}`,
    '',
    `Orchestrator: ${status.nioHealthy ? '✅ online' : '❌ offline'} (${status.coreAdapter})`,
    `Budget: $${status.budget.dailySpendUsd.toFixed(2)} / $${status.budget.dailyBudgetUsd} daily`,
    `Persistence: ${status.persistenceEnabled ? 'PostgreSQL on' : 'in-memory only'}`,
  ];

  if (status.activeLimbs.length === 0) {
    lines.push('', 'Active limbs: none');
  } else {
    lines.push('', 'Active limbs:');
    for (const limb of status.activeLimbs) {
      lines.push(`• ${limb.displayName} (${limb.state}) — task ${limb.taskId}`);
    }
  }

  if (status.gateFailuresRecent > 0) {
    lines.push('', `Recent gate failures: ${status.gateFailuresRecent}`);
    for (const g of status.gateEventsRecent.filter((e) => !e.passed).slice(0, 3)) {
      lines.push(`• ${g.gateId}: ${g.reason ?? 'failed'}`);
    }
  }

  if (status.lastTaskAt) {
    lines.push('', `Last task telemetry: ${status.lastTaskAt}`);
  }

  return lines.join('\n');
}

/** Build comms delta for pet/Telegram polling. */
export function buildCodyCommsResponse(sinceMessageId?: string): {
  timeline: FormattedInterAgentLine[];
  latestMessageId: string | null;
} {
  const messages = interAgentMessageBus.recent(50);
  const timeline = formatInterAgentTimeline(messages);
  const delta = filterTimelineSince(timeline, sinceMessageId);
  const latestMessageId = messages[0]?.messageId ?? null;
  return { timeline: delta, latestMessageId };
}
