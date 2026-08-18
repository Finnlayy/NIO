import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';
import { getLibraryArchiveDir, getLibraryLedgerDir } from './workspace_paths';
import type { LimbInstance } from './limb_instance_store';
import type { LimbTemplate } from './library_templates';

export interface PostMortemInput {
  eventId: string;
  taskId: string;
  taskType: string;
  outcome: 'passed' | 'revised' | 'escalated';
  score: number;
  agentsUsed: Array<{
    agentId: string;
    role?: string;
    performanceScore: number;
    executionTimeMs: number;
  }>;
  evidence: {
    logs: string[];
    artifacts: string[];
    errors: string[];
  };
  limbInstance?: LimbInstance;
  template?: LimbTemplate;
}

export interface PostMortemOutput {
  behavioralLedgerId: string;
  archiveId: string;
  whatWorked: string[];
  whatFailed: string[];
  rootCause: string | null;
  strategyUpdate: string | null;
  manifestChanges: Record<string, unknown> | null;
  learningDelta: number;
  shouldRetrain: boolean;
}

export interface ArchiveEntry {
  archive_id: string;
  limb_instance_id: string;
  template_id: string;
  task_id: string;
  archived_at: string;
  post_mortem: PostMortemOutput;
  limb_snapshot: LimbInstance;
  template_snapshot: LimbTemplate | null;
}

function ensureDir(dir: string): void {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function analyzeOutcome(input: PostMortemInput) {
  const success = input.outcome === 'passed';
  let rootCause: string | null = null;

  if (!success && input.evidence.errors.length > 0) {
    rootCause = input.evidence.errors[0] ?? 'Task failed';
  }

  return { success, rootCause };
}

function extractLearnings(input: PostMortemInput, success: boolean) {
  const whatWorked: string[] = [];
  const whatFailed: string[] = [];

  if (success) {
    whatWorked.push(`Task completed with score ${input.score}/100`);
    const high = input.agentsUsed.filter((a) => a.performanceScore >= 85);
    if (high.length > 0) {
      whatWorked.push(`High performers: ${high.map((a) => a.agentId).join(', ')}`);
    }
  } else {
    if (input.evidence.errors.length > 0) {
      whatFailed.push(...input.evidence.errors.slice(0, 3));
    }
    whatFailed.push(`Outcome: ${input.outcome}`);
  }

  return { whatWorked, whatFailed };
}

function calculateLearningDelta(input: PostMortemInput, success: boolean): number {
  if (success) return input.score >= 90 ? 8 : 4;
  return input.outcome === 'escalated' ? -12 : -6;
}

export function executePostMortem(input: PostMortemInput): PostMortemOutput {
  const { success, rootCause } = analyzeOutcome(input);
  const { whatWorked, whatFailed } = extractLearnings(input, success);
  const learningDelta = calculateLearningDelta(input, success);

  const strategyUpdate = !success
    ? `Avoid repeating failure mode for ${input.taskType}`
    : null;

  const manifestChanges =
    !success && input.template
      ? {
          template_id: input.template.template_id,
          recommendation: 'Review routing_weight after failure',
        }
      : null;

  const behavioralLedgerId = `ledger-${randomUUID().slice(0, 8)}`;
  const archiveId = `archive-${randomUUID().slice(0, 8)}`;

  const output: PostMortemOutput = {
    behavioralLedgerId,
    archiveId,
    whatWorked,
    whatFailed,
    rootCause,
    strategyUpdate,
    manifestChanges,
    learningDelta,
    shouldRetrain: !success && Math.abs(learningDelta) >= 10,
  };

  const ledgerDir = getLibraryLedgerDir();
  ensureDir(ledgerDir);
  writeFileSync(
    join(ledgerDir, `${behavioralLedgerId}.json`),
    JSON.stringify(
      {
        id: behavioralLedgerId,
        event_id: input.eventId,
        task_type: input.taskType,
        task_id: input.taskId,
        agents_used: input.agentsUsed,
        what_worked: whatWorked,
        what_failed: whatFailed,
        root_cause: rootCause,
        strategy_update: strategyUpdate,
        manifest_changes: manifestChanges,
        learning_delta: learningDelta,
        created_at: new Date().toISOString(),
      },
      null,
      2,
    ),
    'utf-8',
  );

  if (input.limbInstance) {
    const archiveDir = getLibraryArchiveDir();
    ensureDir(archiveDir);
    const entry: ArchiveEntry = {
      archive_id: archiveId,
      limb_instance_id: input.limbInstance.limb_instance_id,
      template_id: input.limbInstance.template_id,
      task_id: input.limbInstance.task_id,
      archived_at: new Date().toISOString(),
      post_mortem: output,
      limb_snapshot: input.limbInstance,
      template_snapshot: input.template ?? null,
    };
    writeFileSync(join(archiveDir, `${archiveId}.json`), JSON.stringify(entry, null, 2), 'utf-8');
  }

  return output;
}

export function loadArchiveEntries(limit = 50): ArchiveEntry[] {
  const dir = getLibraryArchiveDir();
  if (!existsSync(dir)) return [];

  return readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .map((f) => JSON.parse(readFileSync(join(dir, f), 'utf-8')) as ArchiveEntry)
    .sort((a, b) => b.archived_at.localeCompare(a.archived_at))
    .slice(0, limit);
}
