import { randomUUID } from 'crypto';
import type { ModelRouter } from '../model_router';
import type { TelemetrySink } from '../types';
import { buildTelemetryEvent } from '../telemetry';
import { interAgentMessageBus } from './message_bus';
import type {
  GateContext,
  GateResult,
  GateRunResult,
  GateSpec,
} from './types';

export interface GateRunnerDeps {
  modelRouter?: ModelRouter;
  telemetry?: TelemetrySink;
}

function now(): string {
  return new Date().toISOString();
}

function runBudgetCheck(spec: GateSpec, deps: GateRunnerDeps): GateResult {
  const status = deps.modelRouter?.getBudgetStatus();
  if (!status) {
    return {
      gateId: spec.id,
      kind: spec.kind,
      passed: true,
      required: spec.required,
      reason: 'No model router — budget check skipped',
      timestamp: now(),
    };
  }

  const exceeded = status.dailySpendUsd >= status.dailyBudgetUsd;
  const clamped = exceeded && status.onExceeded === 'clamp_to_free_tier';
  const passed = !exceeded || clamped;

  return {
    gateId: spec.id,
    kind: spec.kind,
    passed,
    required: spec.required,
    reason: exceeded
      ? clamped
        ? `Daily budget exceeded ($${status.dailySpendUsd.toFixed(4)}/$${status.dailyBudgetUsd}); clamped to free tier`
        : `Daily budget exceeded ($${status.dailySpendUsd.toFixed(4)}/$${status.dailyBudgetUsd})`
      : `Budget OK ($${status.dailySpendUsd.toFixed(4)}/$${status.dailyBudgetUsd})`,
    timestamp: now(),
  };
}

function runPolicyCheck(spec: GateSpec, ctx: GateContext): GateResult {
  const trimmed = ctx.taskDescription.trim();
  if (trimmed.length === 0) {
    return {
      gateId: spec.id,
      kind: spec.kind,
      passed: false,
      required: spec.required,
      reason: 'Empty task description',
      timestamp: now(),
    };
  }

  const blockedPatterns = [
    /\brm\s+-rf\b/i,
    /\bforce\s+push\b/i,
    /\bdrop\s+table\b/i,
    /\btruncate\s+table\b/i,
  ];
  const matchesDestructive = blockedPatterns.some((p) => p.test(trimmed));
  if (matchesDestructive && !ctx.parentApproved) {
    return {
      gateId: spec.id,
      kind: spec.kind,
      passed: false,
      required: spec.required,
      reason: 'Destructive pattern detected — parent approval required',
      timestamp: now(),
    };
  }

  return {
    gateId: spec.id,
    kind: spec.kind,
    passed: true,
    required: spec.required,
    reason: 'Policy check passed',
    timestamp: now(),
  };
}

async function runTelemetryEmit(
  spec: GateSpec,
  ctx: GateContext,
  deps: GateRunnerDeps,
): Promise<GateResult> {
  if (deps.telemetry) {
    const event = buildTelemetryEvent({
      domain: 'generic',
      algorithmTag: null,
      isComplex: false,
      politenessTier: 'neutral',
      urgencyTier: 'normal',
      promptVariant: 'baseline',
      expectedAccuracy: 0.822,
      taskDescription: `[gate:${spec.id}] ${ctx.taskDescription.slice(0, 120)}`,
      source: ctx.source as 'telegram' | 'api' | 'console' | undefined,
      agentId: ctx.subagentId ?? ctx.limbInstanceId ?? 'orchestrator',
      limbInstanceId: ctx.limbInstanceId,
    });
    await deps.telemetry.record({
      ...event,
      agentId: `gate:${spec.id}`,
    });
  }

  return {
    gateId: spec.id,
    kind: spec.kind,
    passed: true,
    required: spec.required,
    reason: 'Gate telemetry emitted',
    timestamp: now(),
  };
}

function runParentApproval(spec: GateSpec, ctx: GateContext): GateResult {
  const needsApproval = ctx.isDestructive === true;
  if (!needsApproval) {
    return {
      gateId: spec.id,
      kind: spec.kind,
      passed: true,
      required: spec.required,
      reason: 'Non-destructive operation — approval not required',
      timestamp: now(),
    };
  }

  const passed = ctx.parentApproved === true;
  return {
    gateId: spec.id,
    kind: spec.kind,
    passed,
    required: spec.required,
    reason: passed ? 'Parent approved destructive operation' : 'Awaiting parent approval',
    timestamp: now(),
  };
}

/**
 * Run hard gate specs sequentially. Required gate failure blocks dispatch.
 * Gate telemetry flows to Cody supervisor via message bus + telemetry sink.
 */
export async function runGateSpecs(
  specs: GateSpec[],
  ctx: GateContext,
  deps: GateRunnerDeps = {},
): Promise<GateRunResult> {
  const results: GateResult[] = [];

  for (const spec of specs) {
    let result: GateResult;
    switch (spec.kind) {
      case 'budget_check':
        result = runBudgetCheck(spec, deps);
        break;
      case 'policy_check':
        result = runPolicyCheck(spec, ctx);
        break;
      case 'telemetry_emit':
        result = await runTelemetryEmit(spec, ctx, deps);
        break;
      case 'parent_approval':
        result = runParentApproval(spec, ctx);
        break;
      default:
        result = {
          gateId: spec.id,
          kind: spec.kind,
          passed: false,
          required: spec.required,
          reason: `Unknown gate kind: ${spec.kind as string}`,
          timestamp: now(),
        };
    }
    results.push(result);

    if (spec.required && !result.passed) {
      const gateRun: GateRunResult = { passed: false, results, blockedBy: spec.id };
      notifyCodyGateCheckpoint(gateRun, ctx);
      return gateRun;
    }
  }

  const gateRun: GateRunResult = { passed: true, results };
  notifyCodyGateCheckpoint(gateRun, ctx);
  return gateRun;
}

function notifyCodyGateCheckpoint(gateRun: GateRunResult, ctx: GateContext): void {
  interAgentMessageBus.publish({
    type: 'gate_checkpoint',
    from: 'orchestrator',
    to: 'cody',
    targetId: ctx.subagentId,
    payload: {
      passed: gateRun.passed,
      blockedBy: gateRun.blockedBy,
      taskDescription: ctx.taskDescription.slice(0, 200),
    },
    gateResults: gateRun.results,
  });

  if (!gateRun.passed) {
    interAgentMessageBus.publish({
      type: 'approval_request',
      from: 'orchestrator',
      to: 'user',
      payload: {
        blockedBy: gateRun.blockedBy,
        reason: gateRun.results.find((r) => !r.passed)?.reason,
        taskDescription: ctx.taskDescription.slice(0, 200),
      },
      gateResults: gateRun.results,
    });
  }
}

export function createGateContext(params: GateContext): GateContext {
  return { ...params, subagentId: params.subagentId ?? randomUUID().slice(0, 8) };
}
