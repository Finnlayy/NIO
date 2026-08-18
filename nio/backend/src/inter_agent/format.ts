import type { InterAgentMessage } from './types';

export type InterAgentSeverity = 'info' | 'success' | 'warning' | 'error';

export interface FormattedInterAgentLine {
  messageId: string;
  timestamp: string;
  severity: InterAgentSeverity;
  headline: string;
  body: string;
  actors: { from: string; to: string };
}

const CHANNEL_LABELS: Record<string, string> = {
  orchestrator: 'Atlas',
  subagent: 'Subagent',
  limb: 'Limb',
  cody: 'Cody',
  user: 'You',
};

function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel] ?? channel;
}

function str(payload: Record<string, unknown>, key: string): string | undefined {
  const v = payload[key];
  return typeof v === 'string' && v.trim() ? v.trim() : undefined;
}

function num(payload: Record<string, unknown>, key: string): number | undefined {
  const v = payload[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined;
}

function bool(payload: Record<string, unknown>, key: string): boolean | undefined {
  const v = payload[key];
  return typeof v === 'boolean' ? v : undefined;
}

function truncate(text: string, max = 120): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

/** Map a single inter-agent message to a user-readable line. */
export function formatInterAgentMessage(msg: InterAgentMessage): FormattedInterAgentLine {
  const actors = { from: channelLabel(msg.from), to: channelLabel(msg.to) };
  const payload = msg.payload ?? {};

  switch (msg.type) {
    case 'dispatch': {
      if (msg.to === 'limb' || msg.to === 'cody') {
        const displayName = str(payload, 'displayName') ?? msg.targetId ?? 'limb';
        const taskId = str(payload, 'taskId');
        const taskDescription = str(payload, 'taskDescription');
        return {
          messageId: msg.messageId,
          timestamp: msg.timestamp,
          severity: 'info',
          headline: 'Limb deployed',
          body: taskDescription
            ? `Atlas deployed **${displayName}** for: ${truncate(taskDescription)}`
            : taskId
              ? `Atlas deployed **${displayName}** (task ${taskId})`
              : `Atlas deployed **${displayName}**`,
          actors,
        };
      }
      return {
        messageId: msg.messageId,
        timestamp: msg.timestamp,
        severity: 'info',
        headline: 'Dispatch queued',
        body: 'Atlas queued subagent dispatch',
        actors,
      };
    }

    case 'gate_checkpoint': {
      const passed = bool(payload, 'passed') ?? msg.gateResults?.every((g) => g.passed) ?? true;
      const blockedBy = str(payload, 'blockedBy');
      const failed = msg.gateResults?.find((g) => !g.passed);
      if (!passed || blockedBy || failed) {
        const gateId = blockedBy ?? failed?.gateId ?? 'checkpoint';
        const reason = failed?.reason ?? str(payload, 'reason') ?? 'failed';
        return {
          messageId: msg.messageId,
          timestamp: msg.timestamp,
          severity: 'error',
          headline: 'Gate blocked',
          body: `Gate blocked at **${gateId}**: ${reason}`,
          actors,
        };
      }
      return {
        messageId: msg.messageId,
        timestamp: msg.timestamp,
        severity: 'success',
        headline: 'Gates passed',
        body: 'All gates passed — proceeding',
        actors,
      };
    }

    case 'task_result': {
      const displayName = str(payload, 'displayName') ?? msg.targetId ?? 'Limb';
      const latencyMs = num(payload, 'latencyMs');
      const success = bool(payload, 'success') ?? true;
      return {
        messageId: msg.messageId,
        timestamp: msg.timestamp,
        severity: success ? 'success' : 'error',
        headline: success ? 'Task complete' : 'Task failed',
        body:
          latencyMs != null
            ? `**${displayName}** ${success ? 'finished' : 'failed'} in ${latencyMs}ms`
            : `**${displayName}** ${success ? 'finished' : 'failed'}`,
        actors,
      };
    }

    case 'approval_request': {
      const reason = str(payload, 'reason') ?? 'Approval required';
      const blockedBy = str(payload, 'blockedBy');
      return {
        messageId: msg.messageId,
        timestamp: msg.timestamp,
        severity: 'warning',
        headline: 'Approval needed',
        body: blockedBy ? `Approval needed at **${blockedBy}**: ${reason}` : `Approval needed: ${reason}`,
        actors,
      };
    }

    case 'approval_response':
      return {
        messageId: msg.messageId,
        timestamp: msg.timestamp,
        severity: 'info',
        headline: 'Approval response',
        body: str(payload, 'approved') === 'true' ? 'User approved the operation' : 'User declined the operation',
        actors,
      };

    default:
      return {
        messageId: msg.messageId,
        timestamp: msg.timestamp,
        severity: 'info',
        headline: msg.type,
        body: `${channelLabel(msg.from)} → ${channelLabel(msg.to)}`,
        actors,
      };
  }
}

/** Format messages newest-first for display (input order preserved if already reversed). */
export function formatInterAgentTimeline(messages: InterAgentMessage[]): FormattedInterAgentLine[] {
  return messages.map(formatInterAgentMessage);
}

/** User-relevant messages Cody should relay (to cody/user channels or cody-facing types). */
export function isUserVisibleInterAgentMessage(msg: InterAgentMessage): boolean {
  if (msg.to === 'cody' || msg.to === 'user') return true;
  if (msg.type === 'approval_request') return true;
  return false;
}

/** Delta filter: return lines after a given messageId (chronological order for alerts). */
export function filterTimelineSince(
  timeline: FormattedInterAgentLine[],
  sinceMessageId?: string,
): FormattedInterAgentLine[] {
  if (!sinceMessageId) return timeline;
  const idx = timeline.findIndex((l) => l.messageId === sinceMessageId);
  if (idx === -1) return timeline;
  return timeline.slice(0, idx);
}
