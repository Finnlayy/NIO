import { AgentTraceEvent, AgentStatus } from '../types/agent';

export async function triggerAgentCycle(
  prompt: string,
  options?: {
    trigger?: 'USER_PROMPT' | 'SIGNAL_ALERT' | 'SWARM_HYPOTHESIS' | 'SCHEDULED_AUDIT';
    sessionAuth?: string;
    signalMetadata?: {
      strategyId?: string;
      symbol?: string;
      side?: 'BUY' | 'SELL';
      quantity?: number;
      timestamp?: number;
    };
  }
): Promise<{ success: boolean; trace: AgentTraceEvent }> {
  const response = await fetch('/api/agent/cycle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      trigger: options?.trigger || 'USER_PROMPT',
      sessionAuth: options?.sessionAuth,
      signalMetadata: options?.signalMetadata,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `HTTP error ${response.status}`);
  }

  return response.json();
}

export async function fetchAgentTraces(): Promise<AgentTraceEvent[]> {
  const response = await fetch('/api/agent/traces');
  if (!response.ok) {
    throw new Error(`Failed to fetch agent traces: ${response.status}`);
  }
  const data = await response.json();
  return data.traces || [];
}

export async function fetchAgentTraceById(id: string): Promise<AgentTraceEvent | null> {
  const response = await fetch(`/api/agent/traces/${encodeURIComponent(id)}`);
  if (!response.ok) {
    return null;
  }
  const data = await response.json();
  return data.trace || null;
}

export async function fetchAgentStatus(): Promise<AgentStatus> {
  const response = await fetch('/api/agent/status');
  if (!response.ok) {
    throw new Error(`Failed to fetch agent status: ${response.status}`);
  }
  return response.json();
}

export async function clearAgentTraces(): Promise<void> {
  const response = await fetch('/api/agent/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to clear agent traces: ${response.status}`);
  }
}
