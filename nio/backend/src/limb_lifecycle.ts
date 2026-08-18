import { randomUUID } from 'crypto';
import type { LimbInstanceStore } from './limb_instance_store';
import { resolveTemplateForTask, type LimbTemplate } from './library_templates';
import { executePostMortem } from './post_mortem';
import { hashTaskDescription } from './telemetry';

export interface TaskLimbContext {
  instanceId: string;
  template: LimbTemplate;
  taskId: string;
}

export function deployLimbForTask(
  store: LimbInstanceStore,
  params: {
    taskDescription: string;
    templateId?: string;
    role?: string;
    domainHint?: string;
    source?: string;
  },
): TaskLimbContext {
  const template = resolveTemplateForTask({
    templateId: params.templateId,
    role: params.role,
    domainHint: params.domainHint,
  });
  const taskId = `task-${randomUUID().slice(0, 8)}`;
  const instance = store.deploy({
    template_id: template.template_id,
    mock_id: template.mock_id,
    display_name: template.display_name,
    task_id: taskId,
    task_description_hash: hashTaskDescription(params.taskDescription),
    source: params.source,
  });
  store.transition(instance.limb_instance_id, 'active');
  return { instanceId: instance.limb_instance_id, template, taskId };
}

export function retireLimbAfterTask(
  store: LimbInstanceStore,
  context: TaskLimbContext,
  params: {
    eventId: string;
    taskDescription: string;
    latencyMs: number;
    success: boolean;
    source?: string;
  },
): void {
  const instance = store.get(context.instanceId);
  if (!instance) return;

  store.setLatency(context.instanceId, params.latencyMs);
  store.transition(context.instanceId, 'completing');

  const score = params.success ? 88 : params.success === false ? 62 : 75;
  const outcome = params.success ? 'passed' : 'revised';

  store.transition(context.instanceId, 'post-mortem');

  executePostMortem({
    eventId: params.eventId,
    taskId: context.taskId,
    taskType: context.template.role,
    outcome,
    score,
    agentsUsed: [
      {
        agentId: instance.agentId,
        role: context.template.role,
        performanceScore: score,
        executionTimeMs: params.latencyMs,
      },
    ],
    evidence: {
      logs: [`Task completed via NIO middleware (${params.source ?? 'api'})`],
      artifacts: [],
      errors: params.success ? [] : ['Task did not meet success threshold'],
    },
    limbInstance: { ...instance, state: 'post-mortem', latency_ms: params.latencyMs },
    template: context.template,
  });

  store.transition(context.instanceId, 'archived');
  store.remove(context.instanceId);
}
