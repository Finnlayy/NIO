/**
 * Core domain identifiers recognized by the classifier.
 */
import type { ConversationCompression } from './chat_compression';

export type ComplexDomain = 'ml_30core' | 'dev_dp' | 'generic' | 'unknown';

/**
 * Urgency levels used for prompt wrapping and telemetry.
 */
export type UrgencyTier = 'low' | 'normal' | 'high' | 'critical';

/**
 * Politeness tier for empirical tone experiments.
 * Reference: Dobariya & Kumar (2025) observed +4.0 pp accuracy
 * for very-rude over very-polite prompts on ChatGPT-4o.
 */
export type PolitenessTier = 'very_polite' | 'polite' | 'neutral' | 'rude' | 'very_rude';

/**
 * Incoming task context supplied by upstream callers.
 */
export interface PromptContext {
  /** Human-readable description of the task. */
  taskDescription: string;

  /** Explicit flag from the caller; if true the task is treated as complex. */
  isComplexWorkflow: boolean;

  /** Optional explicit domain hint, e.g. 'ml_30core' or 'dev_dp'. */
  domainHint?: ComplexDomain;

  /** Optional algorithm tag, e.g. 'xgboost', 'transformer_selection', 'knapsack_01'. */
  algorithmTag?: string;

  /** Optional desired politeness tier for tone experiments. */
  politenessTier?: PolitenessTier;

  /** Optional agent role for model tier resolution (manifest role_overrides). */
  role?: string;

  /** Optional request source for telemetry (telegram, console, api). */
  source?: 'telegram' | 'api' | 'console';

  /** Optional limb template id from Agent Library. */
  templateId?: string;

  /**
   * Predictive Delta Compression bundle (baseline + hot window + deltas).
   * When present, middleware rehydrates conversation context within tokenBudget.
   */
  conversationCompression?: ConversationCompression;
}

/**
 * Result of deterministic domain / complexity classification.
 */
export interface ClassificationResult {
  domain: ComplexDomain;
  algorithmTag: string | null;
  complexityScore: number;
  isComplex: boolean;
}

/**
 * Parsed system template structure.
 */
export interface SystemTemplate {
  metadata: {
    domain: string;
    node_id: string;
    urgency_tier: UrgencyTier;
    expected_accuracy: number;
    version: string;
    author: string;
  };
  execution: {
    preamble: string;
    instruction: string;
    urgency_injection_slot: string;
    closing: string;
  };
}

/**
 * Final wrapped prompt bundle.
 */
export interface WrappedPrompt {
  systemPrompt: string;
  userPrompt: string;
  urgencyBlock: string;
  isComplex: boolean;
  domain: ComplexDomain;
  expectedAccuracy: number;
  politenessTier: PolitenessTier;
  /** Present when upstream supplied PDC-compressed conversation state. */
  conversationCompression?: ConversationCompression;
}

/**
 * Single telemetry event persisted for empirical analysis.
 */
export interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  domain: ComplexDomain;
  algorithmTag: string | null;
  isComplex: boolean;
  politenessTier: PolitenessTier;
  urgencyTier: UrgencyTier;
  promptVariant: 'baseline' | 'urgency_wrapped';
  expectedAccuracy: number;
  observedAccuracy?: number;
  latencyMs?: number;
  taskDescriptionHash: string;
  source?: 'telegram' | 'api' | 'console';
  agentId?: string;
  limbInstanceId?: string;
  /** PDC: tokensBefore / tokensAfter when conversationCompression is present. */
  compressionRatio?: number;
  /** PDC: baseline.summaryVersion at request time. */
  baselineVersion?: number;
  /** PDC: number of turns in hot window (not message bodies). */
  hotWindowSize?: number;
}

/**
 * Abstraction for the downstream Neural Core. Inject a real HTTP client,
 * local model wrapper or deterministic simulator here.
 */
export interface CoreExecuteContext {
  resolvedModel?: import('../../shared/manifest-schema').ResolvedModel;
  role?: string;
}

export interface NeuralCoreAdapter {
  execute(prompt: WrappedPrompt, context?: CoreExecuteContext): Promise<NeuralCoreResponse>;
}

/**
 * Response shape returned by the Neural Core adapter.
 */
export interface NeuralCoreResponse {
  coreNodeId: string;
  output: string;
  latencyMs: number;
  metadata: Record<string, unknown>;
}

/**
 * Runtime configuration for the middleware pipeline.
 */
export interface MiddlewareConfig {
  /** Absolute or relative path to the YAML system template. */
  systemTemplatePath: string;

  /** Expected accuracy target (default read from template). */
  expectedAccuracy?: number;

  /** Threshold above which a complexity score triggers urgency mode. */
  complexityThreshold?: number;

  /** Default politeness tier for experiments. */
  defaultPolitenessTier?: PolitenessTier;

  /** Telemetry sink. */
  telemetry?: TelemetrySink;

  /** Downstream core adapter. */
  coreAdapter: NeuralCoreAdapter;

  /** Model router for tier resolution (optional). */
  modelRouter?: import('./model_router').ModelRouter;

  /** Dynamic limb instance pool (Atlas detachable limbs). */
  limbInstanceStore?: import('./limb_instance_store').LimbInstanceStore;
}

/**
 * Telemetry sink contract.
 */
export interface TelemetrySink {
  record(event: TelemetryEvent): Promise<void> | void;
}

/**
 * Minimal Express-like request / response / next types so the middleware
 * remains framework-agnostic.
 */
export interface HttpRequest {
  body: {
    taskDescription?: string;
    isComplexWorkflow?: boolean;
    domainHint?: ComplexDomain;
    algorithmTag?: string;
    politenessTier?: PolitenessTier;
    role?: string;
    /** Caller channel — skips duplicate Telegram alert when Cody already replies. */
    source?: 'telegram' | 'api' | 'console';
    templateId?: string;
    conversationCompression?: ConversationCompression;
  };
}

export interface HttpResponse {
  status(code: number): HttpResponse;
  json(body: unknown): HttpResponse;
}

export type NextFunction = (err?: unknown) => void;
