import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  filterTimelineSince,
  formatInterAgentMessage,
  formatInterAgentTimeline,
  isUserVisibleInterAgentMessage,
} from './format';
import type { InterAgentMessage } from './types';

function msg(partial: Partial<InterAgentMessage> & Pick<InterAgentMessage, 'type' | 'from' | 'to'>): InterAgentMessage {
  return {
    messageId: partial.messageId ?? 'msg-1',
    timestamp: partial.timestamp ?? '2026-07-14T12:00:00.000Z',
    payload: partial.payload ?? {},
    ...partial,
  };
}

describe('inter-agent format', () => {
  it('formats limb dispatch', () => {
    const line = formatInterAgentMessage(
      msg({
        type: 'dispatch',
        from: 'orchestrator',
        to: 'cody',
        payload: { displayName: 'Python Test Engineer', taskId: 'task-abc' },
      }),
    );
    assert.equal(line.headline, 'Limb deployed');
    assert.match(line.body, /Python Test Engineer/);
    assert.equal(line.severity, 'info');
  });

  it('formats gate failure', () => {
    const line = formatInterAgentMessage(
      msg({
        type: 'gate_checkpoint',
        from: 'orchestrator',
        to: 'cody',
        payload: { passed: false, blockedBy: 'gate-budget' },
        gateResults: [
          {
            gateId: 'gate-budget',
            kind: 'budget_check',
            passed: false,
            required: true,
            reason: 'Daily budget exceeded',
            timestamp: '2026-07-14T12:00:00.000Z',
          },
        ],
      }),
    );
    assert.equal(line.severity, 'error');
    assert.match(line.body, /gate-budget/);
  });

  it('formats task_result success', () => {
    const line = formatInterAgentMessage(
      msg({
        type: 'task_result',
        from: 'subagent',
        to: 'cody',
        targetId: 'limb-1',
        payload: { displayName: 'Atlas Worker', latencyMs: 4200, success: true },
      }),
    );
    assert.equal(line.severity, 'success');
    assert.match(line.body, /4200ms/);
  });

  it('formats approval_request', () => {
    const line = formatInterAgentMessage(
      msg({
        type: 'approval_request',
        from: 'orchestrator',
        to: 'user',
        payload: { reason: 'Destructive operation', blockedBy: 'gate-parent-approval' },
      }),
    );
    assert.equal(line.severity, 'warning');
    assert.match(line.body, /Approval needed/);
  });

  it('builds timeline and filters since messageId', () => {
    const messages = [
      msg({ messageId: 'b', type: 'task_result', from: 'subagent', to: 'cody', payload: { displayName: 'X', latencyMs: 100 } }),
      msg({ messageId: 'a', type: 'dispatch', from: 'orchestrator', to: 'cody', payload: { displayName: 'X' } }),
    ];
    const timeline = formatInterAgentTimeline(messages);
    assert.equal(timeline.length, 2);
    const delta = filterTimelineSince(timeline, 'b');
    assert.equal(delta.length, 0);
  });

  it('identifies user-visible messages', () => {
    assert.equal(
      isUserVisibleInterAgentMessage(msg({ type: 'dispatch', from: 'orchestrator', to: 'subagent' })),
      false,
    );
    assert.equal(
      isUserVisibleInterAgentMessage(msg({ type: 'gate_checkpoint', from: 'orchestrator', to: 'cody' })),
      true,
    );
  });
});
