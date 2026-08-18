import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { InMemoryTelemetryStore } from '../telemetry';
import { runGateSpecs, createGateContext } from './gate_runner';
import { DEFAULT_SUBAGENT_GATE_SPECS } from './types';
import { interAgentMessageBus } from './message_bus';

describe('inter-agent hard gates', () => {
  it('passes default gates for normal tasks', async () => {
    const telemetry = new InMemoryTelemetryStore();
    const ctx = createGateContext({ taskDescription: 'Implement PDC module' });
    const result = await runGateSpecs(DEFAULT_SUBAGENT_GATE_SPECS, ctx, { telemetry });
    assert.equal(result.passed, true);
    assert.equal(result.results.length, 4);
  });

  it('blocks destructive tasks without parent approval', async () => {
    const ctx = createGateContext({
      taskDescription: 'Please run rm -rf on the project',
      isDestructive: true,
      parentApproved: false,
    });
    const result = await runGateSpecs(DEFAULT_SUBAGENT_GATE_SPECS, ctx);
    assert.equal(result.passed, false);
    assert.ok(result.blockedBy);
  });

  it('notifies Cody on gate checkpoint', async () => {
    const before = interAgentMessageBus.snapshot().length;
    const ctx = createGateContext({ taskDescription: 'Normal task' });
    await runGateSpecs(DEFAULT_SUBAGENT_GATE_SPECS, ctx);
    const after = interAgentMessageBus.snapshot();
    assert.ok(after.length > before);
    const codyMsg = after.find((m) => m.to === 'cody' && m.type === 'gate_checkpoint');
    assert.ok(codyMsg);
  });
});
