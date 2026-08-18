import type { ChatTurn, SessionBaseline, TurnDelta } from './types';
import { baselineToSummary } from './baseline_store';

const FILLER_PATTERN =
  /\b(um+|uh+|please|thanks|thank you|okay|ok|sure|great|hello|hi there|hey)\b/gi;

const REDUNDANT_PREFIXES = [
  'as i mentioned',
  'as i said',
  'like i said',
  'again',
  'to reiterate',
];

/**
 * Strip conversational filler (redundancy suppression — early pipeline).
 */
export function stripFiller(text: string): string {
  return text
    .replace(FILLER_PATTERN, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

/**
 * Remove sentences already present in baseline narrative (dedup vs predictive state).
 */
export function suppressRedundant(text: string, baseline: SessionBaseline): string[] {
  const baselineText = baselineToSummary(baseline).toLowerCase();
  const stripped: string[] = [];
  const kept: string[] = [];

  for (const sentence of splitSentences(text)) {
    const norm = sentence.toLowerCase().trim();
    if (!norm) continue;
    const isRedundant =
      baselineText.includes(norm) ||
      REDUNDANT_PREFIXES.some((p) => norm.startsWith(p)) ||
      baseline.topics.some((t) => t.toLowerCase() === norm) ||
      baseline.decisions.some((d) => d.toLowerCase() === norm);
    if (isRedundant) {
      stripped.push(sentence);
    } else {
      kept.push(sentence);
    }
  }
  return kept.length ? kept : stripped.length ? [stripped[0]!] : [text.slice(0, 120)];
}

export function splitSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function extractTasks(sentences: string[]): string[] {
  return sentences.filter((s) => /todo|need to|must|should|fix|implement|add|create|build/i.test(s));
}

function extractDecisions(sentences: string[]): string[] {
  return sentences.filter((s) => /decid|agreed|will use|chosen|let's go with|confirmed/i.test(s));
}

function extractResolved(sentences: string[]): string[] {
  return sentences.filter((s) => /done|completed|fixed|resolved|finished|closed/i.test(s));
}

function diffChanged(sentences: string[], baseline: SessionBaseline): string[] {
  const known = new Set(
    [...baseline.topics, ...baseline.decisions, ...baseline.openTasks].map((s) => s.toLowerCase()),
  );
  return sentences.filter((s) => {
    const lower = s.toLowerCase();
    return [...known].some((k) => lower.includes(k) && lower !== k) || /changed|updated|instead|rather than|now/i.test(s);
  });
}

/**
 * Encode a single turn as structured delta vs baseline (predictive coding).
 */
export function encodeDelta(
  turn: ChatTurn,
  baseline: SessionBaseline,
  turnIndex: number,
): TurnDelta {
  const cleaned = stripFiller(turn.content);
  const sentences = suppressRedundant(cleaned, baseline);
  const newFacts = sentences.filter(
    (s) =>
      !baseline.topics.some((t) => t.toLowerCase() === s.toLowerCase()) &&
      !baseline.decisions.some((d) => d.toLowerCase() === s.toLowerCase()),
  );
  const changedFacts = diffChanged(sentences, baseline);
  const resolvedTasks = extractResolved(sentences);
  const strippedRedundant = splitSentences(cleaned).filter(
    (s) => !sentences.includes(s) && !newFacts.includes(s),
  );

  // Ensure at least one signal per turn
  const signal =
    newFacts.length > 0
      ? newFacts
      : sentences.length > 0
        ? [sentences[0]!]
        : [cleaned.slice(0, 160)];

  return {
    turnIndex,
    role: turn.role,
    newFacts: signal.slice(0, 8),
    changedFacts: changedFacts.slice(0, 4),
    resolvedTasks: [...extractTasks(sentences), ...resolvedTasks].slice(0, 4),
    strippedRedundant: strippedRedundant.slice(0, 4),
    timestamp: turn.timestamp,
  };
}

export function deltaToCompactText(delta: TurnDelta): string {
  const parts: string[] = [`[${delta.role}@${delta.turnIndex}]`];
  if (delta.newFacts.length) parts.push(`+ ${delta.newFacts.join(' | ')}`);
  if (delta.changedFacts.length) parts.push(`~ ${delta.changedFacts.join(' | ')}`);
  if (delta.resolvedTasks.length) parts.push(`✓ ${delta.resolvedTasks.join(' | ')}`);
  return parts.join(' ');
}
