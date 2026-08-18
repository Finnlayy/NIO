import { createServer, IncomingMessage, ServerResponse } from 'http';
import { join } from 'path';
import { URL } from 'url';
import { buildAgentRegistry } from './agent_registry';
import { createCoreAdapter } from './create_core_adapter';
import {
  listProposals,
  loadProposal,
  markProposalApplied,
  recordReview,
  requiresCrossReview,
  storeProposal,
} from './cross_review_store';
import {
  createNeuralCoreMiddleware,
  InMemoryTelemetryStore,
} from './index';
import { loadEnvFiles } from './load_env';
import { LimbInstanceStore } from './limb_instance_store';
import { loadLibraryTemplates } from './library_templates';
import { ModelRouter } from './model_router';
import { buildCodyStatsResponse, loadCodyStatsFile, bumpCodyQuotaEvent } from './cody_stats';
import {
  buildCodySupervisorStatus,
  buildCodyCommsResponse,
  formatSupervisorReport,
} from './cody_supervisor';
import { handleCodyChat } from './cody_chat';
import { loadArchiveEntries } from './post_mortem';
import { notifyTelegramAlertAsync } from './telegram_alert';
import { isQuotaOrProviderExhausted, QUOTA_EXCEEDED_MESSAGE, toTaskErrorResponse } from './provider_errors';
import { HttpRequest, HttpResponse } from './types';
import { rehydrateConversation } from './chat_compression';
import {
  compressSessionAsync,
  updateCompressionStateAsync,
} from './chat_compression/compression_trigger';
import type { ChatTurn, ConversationCompression } from './chat_compression';
import { conversationSessionStore } from './conversation_session_store';
import {
  dispatchSubagentWithGates,
  interAgentMessageBus,
  runGateSpecs,
  DEFAULT_SUBAGENT_GATE_SPECS,
  formatInterAgentTimeline,
} from './inter_agent';
import type { AgentChannel } from './inter_agent/types';
import { randomUUID } from 'crypto';
import { registerCodyShutdownHandlers, startCodyWorker } from './cody_worker';

loadEnvFiles();

const PORT = Number(process.env.PORT ?? 4000);
const HOST = process.env.HOST ?? '0.0.0.0';
const ROOT = process.cwd();
const TEMPLATE_PATH = join(ROOT, 'prompts', 'system', 'neural_core.yaml');
const AGENTS_DIR = join(ROOT, 'agents');

const telemetry = new InMemoryTelemetryStore();
const modelRouter = new ModelRouter();
const limbInstanceStore = new LimbInstanceStore();
const { adapter: coreAdapter, mode: coreAdapterMode } = createCoreAdapter(modelRouter);

const handler = createNeuralCoreMiddleware({
  systemTemplatePath: TEMPLATE_PATH,
  complexityThreshold: 1,
  defaultPolitenessTier: 'neutral',
  telemetry,
  coreAdapter,
  modelRouter,
  limbInstanceStore,
});

const middlewareConfig = {
  systemTemplatePath: TEMPLATE_PATH,
  complexityThreshold: 1,
  defaultPolitenessTier: 'neutral' as const,
  telemetry,
  coreAdapter,
  modelRouter,
  limbInstanceStore,
};

const supervisorDeps = () => ({
  coreAdapterMode,
  nioHealthy: true,
  limbInstanceStore,
  modelRouter,
  telemetry,
});

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(payload);
}

async function readJsonBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  if (chunks.length === 0) {
    return {};
  }

  const raw = Buffer.concat(chunks).toString('utf-8');
  return JSON.parse(raw) as Record<string, unknown>;
}

function toMiddlewareResponse(res: ServerResponse): HttpResponse {
  let statusCode = 200;

  const response: HttpResponse = {
    status(code: number) {
      statusCode = code;
      return response;
    },
    json(body: unknown) {
      sendJson(res, statusCode, body);
      return response;
    },
  };

  return response;
}

function parseUrl(url: string): URL {
  return new URL(url, 'http://localhost');
}

const server = createServer(async (req, res) => {
  const method = req.method ?? 'GET';
  const url = req.url ?? '/';
  const parsed = parseUrl(url);

  if (method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  if (method === 'GET' && parsed.pathname === '/health') {
    sendJson(res, 200, {
      status: 'ok',
      service: 'neural-orchestrator',
      coreAdapter: coreAdapterMode,
    });
    return;
  }

  if (method === 'GET' && parsed.pathname === '/') {
    sendJson(res, 200, {
      service: 'neural-orchestrator',
      endpoints: {
        health: 'GET /health',
        task: 'POST /api/task',
        manifest: 'GET /api/models/manifest',
        resolve: 'GET /api/models/resolve?role=worker',
        telemetry: 'GET /api/telemetry?limit=20',
        registry: 'GET /api/agents/registry',
        activeLimbs: 'GET /api/limbs/active',
        libraryTemplates: 'GET /api/library/templates',
        libraryArchive: 'GET /api/library/archive',
        manifestProposals: 'GET /api/manifest/proposals',
        manifestPropose: 'POST /api/manifest/propose',
        manifestReview: 'POST /api/manifest/review/:proposalId',
        codyStats: 'GET /api/agents/cody/stats',
        codySupervisor: 'GET /api/agents/cody/supervisor',
        chatCompress: 'POST /api/chat/compress',
        chatSession: 'GET /api/chat/sessions/:sessionId',
        interAgentDispatch: 'POST /api/inter-agent/dispatch',
        interAgentMessages: 'GET /api/inter-agent/messages',
        interAgentGateCheck: 'POST /api/inter-agent/gate-check',
      },
      example: {
        method: 'POST',
        path: '/api/task',
        body: {
          taskDescription: 'Solve the 0/1 knapsack problem with dynamic programming.',
          isComplexWorkflow: true,
          role: 'worker',
          domainHint: 'dev_dp',
          algorithmTag: 'knapsack_01',
          politenessTier: 'neutral',
          templateId: 'python-test-engineer',
        },
      },
    });
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/models/manifest') {
    try {
      sendJson(res, 200, modelRouter.getManifest());
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load manifest';
      sendJson(res, 500, { error: message });
    }
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/models/resolve') {
    try {
      const role = parsed.searchParams.get('role') ?? 'worker';
      const resolved = modelRouter.resolveRole(role);
      sendJson(res, 200, resolved);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to resolve model';
      sendJson(res, 500, { error: message });
    }
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/telemetry') {
    const limit = Number(parsed.searchParams.get('limit') ?? 20);
    sendJson(res, 200, { events: telemetry.recent(Number.isFinite(limit) ? limit : 20) });
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/limbs/active') {
    sendJson(res, 200, { limbs: limbInstanceStore.getActive() });
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/library/templates') {
    sendJson(res, 200, { templates: loadLibraryTemplates() });
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/library/archive') {
    const limit = Number(parsed.searchParams.get('limit') ?? 50);
    sendJson(res, 200, { entries: loadArchiveEntries(Number.isFinite(limit) ? limit : 50) });
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/manifest/proposals') {
    const limit = Number(parsed.searchParams.get('limit') ?? 50);
    sendJson(res, 200, { proposals: listProposals(Number.isFinite(limit) ? limit : 50) });
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/agents/registry') {
    try {
      const agents = buildAgentRegistry(modelRouter, AGENTS_DIR, limbInstanceStore.getActive());
      sendJson(res, 200, { agents, budget: modelRouter.getBudgetStatus() });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to build registry';
      sendJson(res, 500, { error: message });
    }
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/agents/cody/stats') {
    try {
      const telegramEvents = telemetry
        .recent(200)
        .filter((e) => e.source === 'telegram' || e.agentId === 'cody').length;
      const supervisor = buildCodySupervisorStatus({
        coreAdapterMode,
        nioHealthy: true,
        limbInstanceStore,
        modelRouter,
        telemetry,
      });
      sendJson(res, 200, buildCodyStatsResponse(loadCodyStatsFile(), telegramEvents, {
        nioHealthy: supervisor.nioHealthy,
        activeLimbCount: supervisor.activeLimbCount,
        gateFailuresRecent: supervisor.gateFailuresRecent,
        persistenceEnabled: supervisor.persistenceEnabled,
        summary: supervisor.summary,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load Cody stats';
      sendJson(res, 500, { error: message });
    }
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/agents/cody/supervisor') {
    try {
      const format = parsed.searchParams.get('format');
      const status = buildCodySupervisorStatus(supervisorDeps());
      if (format === 'text') {
        sendJson(res, 200, { report: formatSupervisorReport(status), status });
        return;
      }
      sendJson(res, 200, status);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load Cody supervisor status';
      sendJson(res, 500, { error: message });
    }
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/agents/cody/comms') {
    try {
      const since = parsed.searchParams.get('since') ?? undefined;
      sendJson(res, 200, buildCodyCommsResponse(since ?? undefined));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load Cody comms';
      sendJson(res, 500, { error: message });
    }
    return;
  }

  if (method === 'POST' && parsed.pathname === '/api/agents/cody/chat') {
    try {
      const body = await readJsonBody(req);
      const message = typeof body.message === 'string' ? body.message : '';
      const sessionId = typeof body.sessionId === 'string' ? body.sessionId : undefined;
      const history = Array.isArray(body.history) ? body.history : undefined;
      const conversationCompression = body.conversationCompression as import('./chat_compression').ConversationCompression | undefined;
      const result = await handleCodyChat(
        { message, sessionId, history, conversationCompression },
        {
          middlewareConfig,
          supervisorDeps: supervisorDeps(),
          defaultRole: typeof body.role === 'string' ? body.role : process.env.NIO_TASK_ROLE ?? 'worker',
        },
      );
      sendJson(res, 200, result);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Cody chat failed';
      sendJson(res, 400, { error: message });
    }
    return;
  }

  if (method === 'POST' && parsed.pathname === '/api/manifest/propose') {
    try {
      const body = await readJsonBody(req);
      const target = body.target as string;
      const agentId = typeof body.agentId === 'string' ? body.agentId : undefined;
      const op = typeof body.op === 'string' ? body.op : 'unknown';
      const reason = typeof body.reason === 'string' ? body.reason : '';
      const evidence = Array.isArray(body.evidence) ? (body.evidence as number[]) : [];
      const boundary = (body.boundaryVerdict ?? {}) as {
        allowed?: boolean;
        violations?: string[];
        warnings?: string[];
        path?: string;
      };

      const needsReview = requiresCrossReview({
        target,
        agentId,
        boundaryAllowed: boundary.allowed === true,
        templateRequiresReview: body.templateRequiresReview === true,
      });

      const proposal = storeProposal({
        target: target as 'core' | 'limb' | 'policy',
        agent_id: agentId,
        op,
        value: body.value,
        reason,
        evidence,
        requires_cross_review: needsReview,
        boundary_allowed: boundary.allowed === true,
        boundary_violations: boundary.violations ?? [],
        boundary_warnings: boundary.warnings ?? [],
        boundary_path: boundary.path ?? '',
        review_verdict: needsReview ? 'pending' : boundary.allowed ? 'approved' : 'changes_requested',
      });

      sendJson(res, 201, { proposal, canApply: !needsReview && boundary.allowed === true });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid proposal body';
      sendJson(res, 400, { error: message });
    }
    return;
  }

  const reviewMatch = parsed.pathname.match(/^\/api\/manifest\/review\/([^/]+)$/);
  if (method === 'POST' && reviewMatch) {
    try {
      const proposalId = reviewMatch[1]!;
      const body = await readJsonBody(req);
      const verdict = body.verdict === 'approved' ? 'approved' : 'changes_requested';
      const updated = recordReview(proposalId, {
        verdict,
        notes: typeof body.notes === 'string' ? body.notes : undefined,
        reviewer: typeof body.reviewer === 'string' ? body.reviewer : 'cross-review',
      });
      if (!updated) {
        sendJson(res, 404, { error: 'Proposal not found' });
        return;
      }
      sendJson(res, 200, { proposal: updated });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid review body';
      sendJson(res, 400, { error: message });
    }
    return;
  }

  const applyMatch = parsed.pathname.match(/^\/api\/manifest\/apply\/([^/]+)$/);
  if (method === 'POST' && applyMatch) {
    const proposalId = applyMatch[1]!;
    const proposal = loadProposal(proposalId);
    if (!proposal) {
      sendJson(res, 404, { error: 'Proposal not found' });
      return;
    }
    if (proposal.requires_cross_review && proposal.review_verdict !== 'approved') {
      sendJson(res, 403, {
        error: 'Cross-review approval required before apply',
        proposal,
      });
      return;
    }
    if (!proposal.boundary_allowed && !proposal.requires_cross_review) {
      sendJson(res, 403, { error: 'Boundary validation rejected this mutation', proposal });
      return;
    }
    const applied = markProposalApplied(proposalId);
    sendJson(res, 200, {
      applied: true,
      proposal: applied,
      note:
        proposal.target === 'core' || proposal.target === 'policy'
          ? 'Core mutation recorded in manifest audit trail; runtime core agents remain immutable.'
          : 'Limb mutation approved for apply.',
    });
    return;
  }

  if (method === 'POST' && parsed.pathname === '/api/chat/compress') {
    try {
      const body = await readJsonBody(req);
      const messages = Array.isArray(body.messages) ? (body.messages as ChatTurn[]) : [];
      const tokenBudget = typeof body.tokenBudget === 'number' ? body.tokenBudget : 2000;
      const hotWindowTurns = typeof body.hotWindowTurns === 'number' ? body.hotWindowTurns : 3;
      const prior = body.conversationCompression as ConversationCompression | undefined;
      const sessionId =
        typeof body.sessionId === 'string' && body.sessionId.trim()
          ? body.sessionId.trim()
          : undefined;
      const source =
        body.source === 'telegram' || body.source === 'console' || body.source === 'api'
          ? body.source
          : 'api';
      const useLlm = body.llmSummarize !== false;

      const config = { tokenBudget, hotWindowTurns, maxDeltas: 12 };
      const compression = prior
        ? await updateCompressionStateAsync(messages, prior, config, {
            modelRouter,
            llmSummarize: useLlm,
          })
        : await compressSessionAsync(messages, undefined, undefined, config, {
            modelRouter,
            llmSummarize: useLlm,
          });

      const rehydrated = rehydrateConversation(compression);

      let persisted = false;
      const effectiveSessionId = sessionId ?? randomUUID();
      if (sessionId || conversationSessionStore.isEnabled()) {
        persisted = await conversationSessionStore.saveSession(
          effectiveSessionId,
          source,
          compression,
        );
      }

      sendJson(res, 200, {
        conversationCompression: compression,
        rehydrated,
        sessionId: persisted ? effectiveSessionId : undefined,
        persisted,
        llmSummarized: Boolean(compression.baseline.narrativeSummary),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Compression failed';
      sendJson(res, 400, { error: message });
    }
    return;
  }

  const sessionMatch = parsed.pathname.match(/^\/api\/chat\/sessions\/([^/]+)$/);
  if (method === 'GET' && sessionMatch) {
    try {
      const sessionId = sessionMatch[1]!;
      const compression = await conversationSessionStore.loadSession(sessionId);
      if (!compression) {
        sendJson(res, 404, { error: 'Session not found or DATABASE_URL not configured' });
        return;
      }
      sendJson(res, 200, { sessionId, conversationCompression: compression });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load session';
      sendJson(res, 500, { error: message });
    }
    return;
  }

  if (method === 'POST' && parsed.pathname === '/api/inter-agent/dispatch') {
    try {
      const body = await readJsonBody(req);
      const taskDescription = typeof body.taskDescription === 'string' ? body.taskDescription : '';
      const result = await dispatchSubagentWithGates(
        {
          taskDescription,
          role: typeof body.role === 'string' ? body.role : undefined,
          templateId: typeof body.templateId === 'string' ? body.templateId : undefined,
          source: typeof body.source === 'string' ? body.source : 'api',
          isDestructive: body.isDestructive === true,
          parentApproved: body.parentApproved === true,
        },
        {
          limbInstanceStore,
          modelRouter,
          telemetry,
          messageBus: interAgentMessageBus,
        },
      );
      sendJson(res, result.dispatched ? 200 : 403, result);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Dispatch failed';
      sendJson(res, 400, { error: message });
    }
    return;
  }

  if (method === 'GET' && parsed.pathname === '/api/inter-agent/messages') {
    const limit = Number(parsed.searchParams.get('limit') ?? 50);
    const from = parsed.searchParams.get('from') as AgentChannel | null;
    const to = parsed.searchParams.get('to') as AgentChannel | null;
    const format = parsed.searchParams.get('format');
    const messages = interAgentMessageBus.recent(Number.isFinite(limit) ? limit : 50, {
      from: from ?? undefined,
      to: to ?? undefined,
    });
    if (format === 'timeline') {
      sendJson(res, 200, { messages, timeline: formatInterAgentTimeline(messages) });
      return;
    }
    sendJson(res, 200, { messages });
    return;
  }

  if (method === 'POST' && parsed.pathname === '/api/inter-agent/gate-check') {
    try {
      const body = await readJsonBody(req);
      const taskDescription = typeof body.taskDescription === 'string' ? body.taskDescription : '';
      const gateRun = await runGateSpecs(DEFAULT_SUBAGENT_GATE_SPECS, {
        taskDescription,
        source: typeof body.source === 'string' ? body.source : undefined,
        isDestructive: body.isDestructive === true,
        parentApproved: body.parentApproved === true,
      }, { modelRouter, telemetry });
      sendJson(res, gateRun.passed ? 200 : 403, gateRun);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Gate check failed';
      sendJson(res, 400, { error: message });
    }
    return;
  }

  if (method === 'POST' && parsed.pathname === '/api/task') {
    try {
      const body = await readJsonBody(req);
      const middlewareReq: HttpRequest = {
        body: {
          taskDescription: typeof body.taskDescription === 'string' ? body.taskDescription : undefined,
          isComplexWorkflow: body.isComplexWorkflow === true,
          domainHint: body.domainHint as HttpRequest['body']['domainHint'],
          algorithmTag: typeof body.algorithmTag === 'string' ? body.algorithmTag : undefined,
          politenessTier: body.politenessTier as HttpRequest['body']['politenessTier'],
          role: typeof body.role === 'string' ? body.role : undefined,
          templateId: typeof body.templateId === 'string' ? body.templateId : undefined,
          source:
            body.source === 'telegram' || body.source === 'console' || body.source === 'api'
              ? body.source
              : undefined,
          conversationCompression: body.conversationCompression as ConversationCompression | undefined,
        },
      };

      await handler(middlewareReq, toMiddlewareResponse(res), (err) => {
        if (err) {
          if (isQuotaOrProviderExhausted(err)) {
            bumpCodyQuotaEvent();
            if (middlewareReq.body.source !== 'telegram') {
              notifyTelegramAlertAsync(QUOTA_EXCEEDED_MESSAGE, 'neural-orchestrator');
            }
            sendJson(res, 503, toTaskErrorResponse(err));
            return;
          }
          const message = err instanceof Error ? err.message : 'Unknown error';
          sendJson(res, 500, { error: message });
        }
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid JSON body';
      sendJson(res, 400, { error: message });
    }
    return;
  }

  sendJson(res, 404, { error: 'Not found' });
});

registerCodyShutdownHandlers(() => {
  server.close(() => process.exit(0));
});

server.listen(PORT, HOST, () => {
  console.log(`neural-orchestrator listening on http://${HOST}:${PORT}`);
  console.log(`Core adapter: ${coreAdapterMode}`);
  console.log(
    'Endpoints: GET /health, GET /api/limbs/active, GET /api/library/templates, GET /api/library/archive, POST /api/task',
  );
  // Start Cody after NIO is accepting connections so the poller can reach the orchestrator.
  startCodyWorker();
});
