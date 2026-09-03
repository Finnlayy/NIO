import { DataEvaluation, KnowledgeEntry, LearningTask, Outcome, RiskGuard } from './schemas';
import { normalizeTokens, taskSignatureHash } from './tokenizer';
import { InMemoryLearningStore, LearningStore } from './store';

/**
 * Deterministic evaluators for the data the system processes, its outcomes,
 * and its accumulated knowledge. These are the raw signals that drive the
 * learning algorithm.
 */

/** Score a piece of data by completeness, type clarity and anomaly load. */
export function evaluateData(input: Record<string, unknown>): DataEvaluation {
  const entries = Object.entries(input);
  const nullValues = entries.filter(([, value]) => value === null || value === undefined).length;
  const supported = ['string', 'number', 'boolean', 'object', 'array', 'null', 'undefined'];
  const unsupported = entries.filter(([, value]) => value !== null && value !== undefined && !supported.includes(typeof value)).length;
  const missingKeys = entries.filter(([, value]) => value === '' || value === undefined).map(([key]) => key);
  const observations: string[] = [];

  const completenessScore = entries.length === 0
    ? 0
    : Math.max(0, 1 - nullValues / entries.length - missingKeys.length / entries.length);

  const typeScore = entries.length === 0 ? 0 : Math.max(0, 1 - unsupported / entries.length);
  const anomalyScore = nullValues / (entries.length || 1);
  const dataScore = Math.min(1, completenessScore * 0.6 + typeScore * 0.4);

  if (entries.length === 0) observations.push('Data record is empty.');
  if (nullValues > 0) observations.push(`Contains ${nullValues} null/undefined value(s).`);
  if (missingKeys.length > 0) observations.push(`Missing or empty keys: ${missingKeys.join(', ')}.`);
  if (unsupported > 0) observations.push(`Contains ${unsupported} unsupported value type(s).`);

  return {
    dataScore,
    completenessScore,
    typeScore,
    anomalyScore,
    missingKeys,
    nullValues,
    unsupportedTypes: unsupported,
    observations,
  };
}

/** Score an outcome using feedback and raw correctness signals. */
export function evaluateOutcome(
  outcome: Outcome,
  feedbacks: readonly { verdict: string; score?: number }[],
): number {
  let score = outcome.correctnessScore ?? outcome.observedAccuracy ?? outcome.expectedAccuracy ?? 0;
  if (!Number.isFinite(score)) score = 0;

  const weightedFeedbacks = feedbacks.map((feedback) => {
    const verdictWeight =
      feedback.verdict === 'correct' ? 1 :
      feedback.verdict === 'partial' ? 0.5 :
      feedback.verdict === 'incorrect' ? 0 :
      0.5;
    const explicit = feedback.score ?? score;
    return verdictWeight * explicit;
  });

  const feedbackAverage = weightedFeedbacks.length
    ? weightedFeedbacks.reduce((sum, value) => sum + value, 0) / weightedFeedbacks.length
    : null;

  const combined = feedbackAverage === null
    ? score
    : Math.min(1, Math.max(0, score * 0.5 + feedbackAverage * 0.5));
  return round(combined);
}

/** Evaluate a single knowledge entry for quality and retrievability. */
export function evaluateKnowledge(entry: KnowledgeEntry): number {
  let score = 0.6;
  if (entry.body.length >= 120) score += 0.1;
  if (entry.tokenIds.length >= 12) score += 0.1;
  if (entry.tags.length >= 2) score += 0.05;
  if (entry.evidence.length > 0) score += 0.05;
  if (entry.source.ref) score += 0.05;
  if (entry.embedding && entry.embedding.length > 0) score += 0.05;
  return round(Math.min(1, score));
}

/**
 * Deterministic quality score of a learning task. Takes into account the
 * resulting proficiency risk, error history and whether research is needed.
 */
export function evaluateTask(task: LearningTask): number {
  let score = task.priority;
  if (task.status === 'in_progress') score += 0.1;
  if (task.results?.knowledgeEntryIds && task.results.knowledgeEntryIds.length > 0) score += 0.05;
  if (task.results?.improvedSkillId) score += 0.05;
  return round(Math.min(1, Math.max(0, score)));
}

/**
 * Compute a pre-execution risk guard from known error patterns. Returns a
 * documented prevention signal when a repeated failure is about to happen.
 */
export function evaluateRisk(
  tokens: string[],
  domain: string,
  algorithmTag: string | null,
  store: LearningStore,
  now: Date = new Date(),
): RiskGuard {
  const signatureHash = taskSignatureHash(tokens);
  const patterns = [...store.listErrorPatterns()];
  let lastSeenAt = new Date(0);

  const matchedPatterns = patterns
    .filter(
      (pattern) =>
        pattern.fingerprint === signatureHash ||
        (pattern.domain === domain && (algorithmTag ? pattern.algorithmTag === algorithmTag : true)),
    )
    .filter((pattern) => {
      const seen = new Date(pattern.lastSeenAt).getTime();
      if (seen > lastSeenAt.getTime()) lastSeenAt = new Date(seen);
      return true;
    })
    .sort((a, b) => b.occurrences - a.occurrences);

  const skills = [...store.listSkills()];
  const matchedAntiPatterns: string[] = [];
  let antiPatternCount = 0;

  for (const skill of skills) {
    if (skill.domain !== domain) continue;
    if (algorithmTag && skill.algorithmTag !== algorithmTag && !skill.errorFingerprints.includes(signatureHash)) continue;
    matchedAntiPatterns.push(...skill.antiPatterns);
    antiPatternCount += skill.errorFingerprints.filter((f) => f === signatureHash).length;
  }

  const uniqueAntiPatterns = [...new Set(matchedAntiPatterns)];
  const recencyFactor = matchedPatterns.length > 0
    ? Math.max(0, 1 - (now.getTime() - lastSeenAt.getTime()) / (30 * 24 * 60 * 60 * 1000))
    : 0;

  const topPattern = matchedPatterns[0];
  const bestOccurrence = topPattern?.occurrences ?? 0;
  const bestScore = topPattern?.lastCorrectnessScore ?? 0.5;
  const patternRisk = bestOccurrence > 0
    ? Math.min(1, bestOccurrence / 5 + (1 - bestScore) * 0.4 + recencyFactor * 0.3)
    : 0;
  const antiRisk = Math.min(0.6, uniqueAntiPatterns.length * 0.2 + antiPatternCount * 0.05);
  const risk = round(Math.max(patternRisk, antiRisk));

  const recommendation = risk >= 0.6
    ? knownErrorRecommendation(matchedPatterns, uniqueAntiPatterns)
    : risk >= 0.3
      ? 'Review the task against recorded anti-patterns before execution.'
      : 'No blocking signal. Execute with normal validation.';

  return {
    risk,
    hasKnownPattern: matchedPatterns.length > 0 || uniqueAntiPatterns.length > 0,
    matchedPatterns,
    matchedAntiPatterns: uniqueAntiPatterns,
    recommendation,
  };
}

function knownErrorRecommendation(
  patterns: { errorClass: string; message: string }[],
  antiPatterns: string[],
): string {
  const parts: string[] = [];
  if (patterns.length > 0) {
    const p = patterns[0]!;
    parts.push(`Known repeated ${p.errorClass} error: ${p.message}`);
  }
  if (antiPatterns.length > 0) {
    parts.push(`Avoid: ${antiPatterns.slice(0, 4).join('; ')}`);
  }
  return parts.join(' ') || 'Use a different approach and validate the output before use.';
}

function round(value: number): number {
  return Math.round(value * 10000) / 10000;
}

export type { LearningTask };
