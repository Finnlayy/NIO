import { randomUUID } from 'crypto';
import type { MiddlewareConfig } from './types';
import { processTask } from './middleware';
import {
  buildCodySupervisorStatus,
  formatSupervisorReport,
  type CodySupervisorDeps,
} from './cody_supervisor';
import {
  buildCodySystemPrompt,
  isStatusQuery,
  loadCodyPersonaContext,
} from './cody_persona';
import {
  bumpCodyConsoleActivity,
  recordCodyConsoleHeartbeat,
  recordCodyConsoleMessage,
} from './cody_stats';
import type { ConversationCompression } from './chat_compression';

export interface CodyChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface CodyChatRequest {
  message: string;
  sessionId?: string;
  history?: CodyChatTurn[];
  conversationCompression?: ConversationCompression;
}

export interface CodyChatResponse {
  reply: string;
  sessionId: string;
  source: 'console';
  supervisorSnapshot?: {
    summary: string;
    activeLimbCount: number;
    gateFailuresRecent: number;
  };
  isStatusReport: boolean;
  latencyMs: number;
}

export interface CodyChatDeps {
  middlewareConfig: MiddlewareConfig;
  supervisorDeps: CodySupervisorDeps;
  defaultRole?: string;
}

function buildTaskDescription(
  systemPrompt: string,
  message: string,
  history: CodyChatTurn[],
): string {
  const transcript = history
    .slice(-6)
    .map((t) => `${t.role === 'user' ? 'User' : 'Cody'}: ${t.content.trim()}`)
    .join('\n');
  return (
    'You are Cody replying in the NIO console. Follow your persona and answer the latest user message.\n\n' +
    `${systemPrompt.slice(0, 2000)}\n\n` +
    (transcript ? `Conversation:\n${transcript}\n\n` : '') +
    `Latest user message: ${message.trim()}\n\n` +
    'Reply as Cody to the latest user message only. Be concise.'
  );
}

/** Handle console chat — status queries shortcut to supervisor report. */
export async function handleCodyChat(
  req: CodyChatRequest,
  deps: CodyChatDeps,
): Promise<CodyChatResponse> {
  const message = req.message?.trim();
  if (!message) {
    throw new Error('message is required');
  }

  const sessionId = req.sessionId?.trim() || randomUUID();
  const history = Array.isArray(req.history) ? req.history : [];

  recordCodyConsoleHeartbeat();
  recordCodyConsoleMessage('user');

  const supervisor = buildCodySupervisorStatus(deps.supervisorDeps);

  if (isStatusQuery(message)) {
    const reply = formatSupervisorReport(supervisor);
    recordCodyConsoleMessage('assistant');
    return {
      reply,
      sessionId,
      source: 'console',
      supervisorSnapshot: {
        summary: supervisor.summary,
        activeLimbCount: supervisor.activeLimbCount,
        gateFailuresRecent: supervisor.gateFailuresRecent,
      },
      isStatusReport: true,
      latencyMs: 0,
    };
  }

  const persona = loadCodyPersonaContext();
  const systemPrompt = buildCodySystemPrompt(persona);
  const taskDescription = buildTaskDescription(systemPrompt, message, history);

  const start = performance.now();
  const result = await processTask(
    {
      taskDescription,
      isComplexWorkflow: false,
      role: deps.defaultRole ?? 'worker',
      source: 'telegram',
      politenessTier: 'neutral',
      conversationCompression: req.conversationCompression,
    },
    deps.middlewareConfig,
  );
  const latencyMs = Math.round(performance.now() - start);

  const reply = typeof result.output === 'string' && result.output.trim()
    ? result.output.trim()
    : 'Sorry — I did not get a reply from the orchestrator.';

  recordCodyConsoleMessage('assistant');
  bumpCodyConsoleActivity();

  return {
    reply,
    sessionId,
    source: 'console',
    supervisorSnapshot: {
      summary: supervisor.summary,
      activeLimbCount: supervisor.activeLimbCount,
      gateFailuresRecent: supervisor.gateFailuresRecent,
    },
    isStatusReport: false,
    latencyMs,
  };
}
