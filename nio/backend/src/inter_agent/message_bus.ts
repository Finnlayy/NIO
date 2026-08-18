import { randomUUID } from 'crypto';
import type { AgentChannel, InterAgentMessage } from './types';

/**
 * In-memory message bus for orchestrator ↔ subagent ↔ Cody communication.
 */
export class InterAgentMessageBus {
  private readonly messages: InterAgentMessage[] = [];
  private readonly maxMessages: number;

  constructor(maxMessages = 500) {
    this.maxMessages = maxMessages;
  }

  publish(message: Omit<InterAgentMessage, 'messageId' | 'timestamp'>): InterAgentMessage {
    const full: InterAgentMessage = {
      ...message,
      messageId: randomUUID(),
      timestamp: new Date().toISOString(),
    };
    this.messages.push(full);
    while (this.messages.length > this.maxMessages) {
      this.messages.shift();
    }
    return full;
  }

  recent(limit = 50, filter?: { from?: AgentChannel; to?: AgentChannel }): InterAgentMessage[] {
    let list = [...this.messages];
    if (filter?.from) list = list.filter((m) => m.from === filter.from);
    if (filter?.to) list = list.filter((m) => m.to === filter.to);
    return list.slice(-limit).reverse();
  }

  snapshot(): readonly InterAgentMessage[] {
    return Object.freeze([...this.messages]);
  }
}

export const interAgentMessageBus = new InterAgentMessageBus();
