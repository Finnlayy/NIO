import { classifyTask } from './domain_classifier';
import { composeUrgencyBlock, enforceUrgencyContext } from './prompt_wrapping';
import { loadSystemTemplate, renderSystemPrompt } from './system_template_loader';
import {
  buildTelemetryEvent,
  defaultAccuracyForPoliteness,
  InMemoryTelemetryStore,
} from './telemetry';
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

  const userPrompt = classification.isComplex
    ? enforceUrgencyContext(context)
    : context.taskDescription;

  const systemPrompt = renderSystemPrompt(template, urgencyBlock);

  const wrapped: WrappedPrompt = {
    systemPrompt,
    userPrompt,
    urgencyBlock,
    isComplex: classification.isComplex,
    domain: classification.domain,
    expectedAccuracy,
    politenessTier: politeness,
  };

  const start = performance.now();
  const coreResponse = await config.coreAdapter.execute(wrapped);
  const latencyMs = Math.round(performance.now() - start);

  const telemetry = config.telemetry ?? new InMemoryTelemetryStore();
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
  });
  await telemetry.record(event);

  return coreResponse;
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
      const { taskDescription, isComplexWorkflow, domainHint, algorithmTag, politenessTier } = req.body;

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
      };

      const result = await processTask(context, config);
      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };
}
