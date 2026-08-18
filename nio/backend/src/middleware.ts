import { classifyTask } from './domain_classifier';
import { retireLimbAfterTask } from './limb_lifecycle';
import { composeUrgencyBlock, enforceUrgencyContext } from './prompt_wrapping';
import { loadSystemTemplate, renderSystemPrompt } from './system_template_loader';
import {
  buildTelemetryEvent,
  defaultAccuracyForPoliteness,
  InMemoryTelemetryStore,
} from './telemetry';
import {
  buildCompressedUserPrompt,
  estimateTokens,
  enrichCompressionWithLlmSummary,
  needsLlmSummarization,
  rehydrateConversation,
} from './chat_compression';
import { conversationSessionStore } from './conversation_session_store';
import {
  dispatchSubagentWithGates,
  interAgentMessageBus,
} from './inter_agent';
import {
  HttpRequest,
  HttpResponse,
  MiddlewareConfig,
  NeuralCoreResponse,
  NextFunction,
  PolitenessTier,
  PromptContext,
  WrappedPrompt,
} from './types';

function assertConfig(config: MiddlewareConfig): void {
  if (!config.systemTemplatePath || typeof config.systemTemplatePath !== 'string') {
    throw new Error('middleware: systemTemplatePath is required.');
  }
  if (!config.coreAdapter || typeof config.coreAdapter.execute !== 'function') {
    throw new Error('middleware: coreAdapter with execute() is required.');
  }
}

/** Post-task LLM summarization + optional PostgreSQL persistence (best-effort). */
async function finalizeConversationAfterTask(
  context: PromptContext,
  config: MiddlewareConfig,
): Promise<void> {
  if (!context.conversationCompression) return;

  let compression = context.conversationCompression;
  if (needsLlmSummarization(compression)) {
    compression = await enrichCompressionWithLlmSummary(
      compression,
      compression.hotWindow,
      config.modelRouter,
    );
  }

  if (!conversationSessionStore.isEnabled()) return;

  const sessionId =
    process.env.CODY_SESSION_ID?.trim() ||
    `cody-${context.source ?? 'api'}`;

  await conversationSessionStore.saveSession(
    sessionId,
    context.source ?? 'api',
    compression,
  );
}

/**
 * Core orchestration pipeline: classify, wrap, record telemetry, execute.
 */
export async function processTask(
  context: PromptContext,
  config: MiddlewareConfig,
): Promise<NeuralCoreResponse> {
  assertConfig(config);

  const template = await loadSystemTemplate(config.systemTemplatePath);
  const classification = classifyTask(context, config.complexityThreshold);
  const politeness: PolitenessTier = context.politenessTier ?? config.defaultPolitenessTier ?? 'neutral';
  const expectedAccuracy = config.expectedAccuracy ?? template.metadata.expected_accuracy;

  const urgencyBlock = classification.isComplex
    ? composeUrgencyBlock(classification, politeness)
    : '';

  let userPrompt = classification.isComplex
    ? enforceUrgencyContext(context)
    : context.taskDescription;

  if (context.conversationCompression) {
    userPrompt = buildCompressedUserPrompt(
      context.conversationCompression,
      context.taskDescription,
    );
  }

  const systemPrompt = renderSystemPrompt(template, urgencyBlock);

  const wrapped: WrappedPrompt = {
    systemPrompt,
    userPrompt,
    urgencyBlock,
    isComplex: classification.isComplex,
    domain: classification.domain,
    expectedAccuracy,
    politenessTier: politeness,
    conversationCompression: context.conversationCompression,
  };

  const limbStore = config.limbInstanceStore;
  let limbContext: import('./limb_lifecycle').TaskLimbContext | null = null;

  if (limbStore && context.source !== 'telegram') {
    const dispatch = await dispatchSubagentWithGates(
      {
        taskDescription: context.taskDescription,
        templateId: context.templateId,
        role: context.role,
        source: context.source,
      },
      {
        limbInstanceStore: limbStore,
        modelRouter: config.modelRouter,
        telemetry: config.telemetry,
        messageBus: interAgentMessageBus,
      },
    );

    if (!dispatch.dispatched) {
      throw new Error(
        `Subagent dispatch blocked at gate: ${dispatch.gateRun.blockedBy ?? 'unknown'}`,
      );
    }

    limbContext = dispatch.limbContext ?? null;
  }

  const start = performance.now();
  const resolvedModel = config.modelRouter?.resolveRole(context.role ?? 'worker');
  const coreResponse = await config.coreAdapter.execute(wrapped, {
    resolvedModel,
    role: context.role ?? 'worker',
  });
  const latencyMs = Math.round(performance.now() - start);

  let estimatedCostUsd = 0;
  if (config.modelRouter && resolvedModel) {
    estimatedCostUsd = config.modelRouter.recordUsage(
      wrapped.systemPrompt.length + wrapped.userPrompt.length,
      resolvedModel,
    );
  }

  const telemetry = config.telemetry ?? new InMemoryTelemetryStore();

  let compressionRatio: number | undefined;
  let baselineVersion: number | undefined;
  let hotWindowSize: number | undefined;
  if (context.conversationCompression) {
    const cc = context.conversationCompression;
    const rehydrated = rehydrateConversation(cc);
    const rawText = [
      ...cc.hotWindow.map((m) => m.content),
      ...cc.deltas.flatMap((d) => [...d.newFacts, ...d.changedFacts, ...d.resolvedTasks]),
    ].join('\n');
    const tokensBefore = estimateTokens(rawText);
    const tokensAfter = rehydrated.estimatedTokens;
    compressionRatio = tokensAfter > 0 ? tokensBefore / tokensAfter : undefined;
    baselineVersion = cc.baseline.summaryVersion;
    hotWindowSize = cc.hotWindow.length;
  }

  const event = buildTelemetryEvent({
    domain: classification.domain,
    algorithmTag: classification.algorithmTag,
    isComplex: classification.isComplex,
    politenessTier: politeness,
    urgencyTier: template.metadata.urgency_tier,
    promptVariant: classification.isComplex ? 'urgency_wrapped' : 'baseline',
    expectedAccuracy,
    taskDescription: context.taskDescription,
    latencyMs,
    source: context.source,
    agentId: context.source === 'telegram' ? 'cody' : limbContext?.instanceId,
    limbInstanceId: limbContext?.instanceId,
    compressionRatio,
    baselineVersion,
    hotWindowSize,
  });
  await telemetry.record(event);

  if (limbStore && limbContext) {
    retireLimbAfterTask(limbStore, limbContext, {
      eventId: event.eventId,
      taskDescription: context.taskDescription,
      latencyMs,
      success: true,
      source: context.source,
    });

    interAgentMessageBus.publish({
      type: 'task_result',
      from: 'subagent',
      to: 'orchestrator',
      targetId: limbContext.instanceId,
      payload: {
        eventId: event.eventId,
        latencyMs,
        success: true,
      },
    });

    interAgentMessageBus.publish({
      type: 'task_result',
      from: 'subagent',
      to: 'cody',
      targetId: limbContext.instanceId,
      payload: {
        eventId: event.eventId,
        latencyMs,
        success: true,
        displayName: limbContext.template.display_name,
      },
    });
  }

  void finalizeConversationAfterTask(context, config).catch(() => {
    /* post-task PDC finalize is best-effort */
  });

  return {
    ...coreResponse,
    latencyMs,
    metadata: {
      ...coreResponse.metadata,
      domain: classification.domain,
      isComplex: classification.isComplex,
      algorithmTag: classification.algorithmTag,
      ...(resolvedModel
        ? {
            modelTier: resolvedModel.tier,
            resolvedModel: {
              provider: resolvedModel.provider,
              model_id: resolvedModel.model_id,
            },
            estimatedCostUsd,
          }
        : {}),
    },
  };
}

/**
 * Factory for an Express-style middleware handler.
 * Expects a JSON body containing at least `taskDescription` and
 * `isComplexWorkflow`.
 */
export function createNeuralCoreMiddleware(config: MiddlewareConfig) {
  assertConfig(config);

  return async (
    req: HttpRequest,
    res: HttpResponse,
    next: NextFunction,
  ): Promise<void> => {
    try {
      const {
        taskDescription,
        isComplexWorkflow,
        domainHint,
        algorithmTag,
        politenessTier,
        role,
        templateId,
        conversationCompression,
      } = req.body;

      if (typeof taskDescription !== 'string' || taskDescription.trim().length === 0) {
        res.status(400).json({ error: 'taskDescription is required.' });
        return;
      }

      const context: PromptContext = {
        taskDescription,
        isComplexWorkflow: isComplexWorkflow === true,
        domainHint,
        algorithmTag,
        politenessTier,
        role: typeof role === 'string' ? role : undefined,
        source:
          req.body.source === 'telegram' || req.body.source === 'console' || req.body.source === 'api'
            ? req.body.source
            : undefined,
        templateId: typeof templateId === 'string' ? templateId : undefined,
        conversationCompression,
      };

      const result = await processTask(context, config);
      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };
}
