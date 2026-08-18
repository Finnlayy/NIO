import { randomUUID } from 'crypto';

export type LimbLifecycleState =
  | 'draft'
  | 'deployed'
  | 'active'
  | 'completing'
  | 'post-mortem'
  | 'archived'
  | 'failed';

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
  task_description_hash?: string;
  swarm_run_id?: string;
  source?: string;
  latency_ms?: number;
}

export class LimbInstanceStore {
  private readonly instances = new Map<string, LimbInstance>();

  deploy(params: {
    template_id: string;
    mock_id: string;
    display_name: string;
    task_id: string;
    task_description_hash?: string;
    source?: string;
    swarm_run_id?: string;
  }): LimbInstance {
    const limb_instance_id = `limb-${randomUUID().slice(0, 8)}`;
    const instance: LimbInstance = {
      limb_instance_id,
      template_id: params.template_id,
      mock_id: params.mock_id,
      display_name: params.display_name,
      task_id: params.task_id,
      state: 'deployed',
      agentId: limb_instance_id,
      deployed_at: new Date().toISOString(),
      task_description_hash: params.task_description_hash,
      swarm_run_id: params.swarm_run_id,
      source: params.source,
    };
    this.instances.set(limb_instance_id, instance);
    return instance;
  }

  get(instanceId: string): LimbInstance | undefined {
    return this.instances.get(instanceId);
  }

  transition(instanceId: string, state: LimbLifecycleState): LimbInstance | undefined {
    const instance = this.instances.get(instanceId);
    if (!instance) return undefined;

    const now = new Date().toISOString();
    const next: LimbInstance = { ...instance, state };

    if (state === 'active' && !next.activated_at) next.activated_at = now;
    if (state === 'completing' || state === 'post-mortem') next.completed_at = now;
    if (state === 'archived' || state === 'failed') next.archived_at = now;

    this.instances.set(instanceId, next);
    return next;
  }

  setLatency(instanceId: string, latencyMs: number): void {
    const instance = this.instances.get(instanceId);
    if (instance) {
      this.instances.set(instanceId, { ...instance, latency_ms: latencyMs });
    }
  }

  getActive(): LimbInstance[] {
    return [...this.instances.values()].filter((i) =>
      ['deployed', 'active', 'completing', 'post-mortem'].includes(i.state),
    );
  }

  getAll(): LimbInstance[] {
    return [...this.instances.values()];
  }

  remove(instanceId: string): void {
    this.instances.delete(instanceId);
  }
}
