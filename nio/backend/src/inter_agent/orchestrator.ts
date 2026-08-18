import type { LimbInstanceStore } from '../limb_instance_store';
import { deployLimbForTask, type TaskLimbContext } from '../limb_lifecycle';
import type { ModelRouter } from '../model_router';
import type { TelemetrySink } from '../types';
import { createGateContext, runGateSpecs } from './gate_runner';
import { interAgentMessageBus, type InterAgentMessageBus } from './message_bus';
import type {
  InterAgentMessage,
  SubagentDispatchRequest,
  SubagentDispatchResult,
} from './types';
import { DEFAULT_SUBAGENT_GATE_SPECS } from './types';

export { InterAgentMessageBus, interAgentMessageBus } from './message_bus';

export interface OrchestratorDeps {
  limbInstanceStore: LimbInstanceStore;
  modelRouter?: ModelRouter;
  telemetry?: TelemetrySink;
  messageBus: InterAgentMessageBus;
}

/**
 * Orchestrator dispatch: run hard gates, then deploy limb subagent if all pass.
 */
export async function dispatchSubagentWithGates(
  request: SubagentDispatchRequest,
  deps: OrchestratorDeps,
): Promise<SubagentDispatchResult> {
  const specs = request.gateSpecs ?? DEFAULT_SUBAGENT_GATE_SPECS;
  const ctx = createGateContext({
    taskDescription: request.taskDescription,
    source: request.source,
    role: request.role,
    templateId: request.templateId,
    isDestructive: request.isDestructive,
    parentApproved: request.parentApproved,
  });

  const gateRun = await runGateSpecs(specs, ctx, {
    modelRouter: deps.modelRouter,
    telemetry: deps.telemetry,
  });

  const messages: InterAgentMessage[] = [];

  messages.push(
    deps.messageBus.publish({
      type: 'dispatch',
      from: 'orchestrator',
      to: 'subagent',
      payload: {
        taskDescription: request.taskDescription,
        role: request.role,
        templateId: request.templateId,
      },
      gateResults: gateRun.results,
    }),
  );

  if (!gateRun.passed) {
    return { dispatched: false, gateRun, messages };
  }

  const limbContext = deployLimbForTask(deps.limbInstanceStore, {
    taskDescription: request.taskDescription,
    templateId: request.templateId,
    role: request.role,
    source: request.source,
  });

  messages.push(
    deps.messageBus.publish({
      type: 'dispatch',
      from: 'orchestrator',
      to: 'limb',
      targetId: limbContext.instanceId,
      payload: {
        taskId: limbContext.taskId,
        templateId: limbContext.template.template_id,
        displayName: limbContext.template.display_name,
        taskDescription: request.taskDescription.slice(0, 200),
      },
      gateResults: gateRun.results,
    }),
  );

  messages.push(
    deps.messageBus.publish({
      type: 'dispatch',
      from: 'orchestrator',
      to: 'cody',
      targetId: limbContext.instanceId,
      payload: {
        taskId: limbContext.taskId,
        templateId: limbContext.template.template_id,
        displayName: limbContext.template.display_name,
        taskDescription: request.taskDescription.slice(0, 200),
      },
      gateResults: gateRun.results,
    }),
  );

  return {
    dispatched: true,
    limbInstanceId: limbContext.instanceId,
    taskId: limbContext.taskId,
    limbContext,
    gateRun,
    messages,
  };
}
