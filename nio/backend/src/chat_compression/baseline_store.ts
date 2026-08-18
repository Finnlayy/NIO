import type { SessionBaseline, TurnDelta } from './types';

export function emptyBaseline(): SessionBaseline {
  return {
    topics: [],
    decisions: [],
    openTasks: [],
    entities: [],
    summaryVersion: 0,
    updatedAt: new Date().toISOString(),
  };
}

function mergeUnique(existing: string[], incoming: string[], limit = 24): string[] {
  const seen = new Set(existing.map((s) => s.toLowerCase()));
  const merged = [...existing];
  for (const item of incoming) {
    const key = item.toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged.slice(-limit);
}

function removeResolved(openTasks: string[], resolved: string[]): string[] {
  if (resolved.length === 0) return openTasks;
  const resolvedLower = new Set(resolved.map((r) => r.toLowerCase()));
  return openTasks.filter((t) => !resolvedLower.has(t.toLowerCase()));
}

/**
 * Fold a turn delta into the session baseline (predictive state update).
 */
export function mergeDeltaIntoBaseline(
  baseline: SessionBaseline,
  delta: TurnDelta,
): SessionBaseline {
  const topics = mergeUnique(baseline.topics, delta.newFacts.filter((f) => f.length < 80));
  const decisions = mergeUnique(baseline.decisions, [
    ...delta.newFacts.filter((f) => /decid|agreed|will use|chosen|picked/i.test(f)),
    ...delta.changedFacts,
  ]);
  const openTasks = removeResolved(
    mergeUnique(baseline.openTasks, delta.newFacts.filter((f) => /todo|need to|task|fix|implement/i.test(f))),
    delta.resolvedTasks,
  );
  const entities = mergeUnique(
    baseline.entities,
    delta.newFacts.filter((f) => /^[@#]|^[A-Z][a-zA-Z0-9_-]{2,}$/.test(f.trim())),
  );

  return {
    topics,
    decisions,
    openTasks,
    entities,
    summaryVersion: baseline.summaryVersion + 1,
    narrativeSummary: baseline.narrativeSummary,
    updatedAt: new Date().toISOString(),
  };
}

export function baselineToSummary(baseline: SessionBaseline): string {
  const parts: string[] = [];
  if (baseline.narrativeSummary) {
    parts.push(`Summary: ${baseline.narrativeSummary}`);
  }
  if (baseline.topics.length) {
    parts.push(`Topics: ${baseline.topics.join('; ')}`);
  }
  if (baseline.decisions.length) {
    parts.push(`Decisions: ${baseline.decisions.join('; ')}`);
  }
  if (baseline.openTasks.length) {
    parts.push(`Open tasks: ${baseline.openTasks.join('; ')}`);
  }
  if (baseline.entities.length) {
    parts.push(`Entities: ${baseline.entities.join(', ')}`);
  }
  return parts.join('\n');
}
