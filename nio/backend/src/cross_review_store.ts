import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';
import { getCrossReviewDir } from './workspace_paths';

export type CrossReviewVerdict = 'pending' | 'approved' | 'changes_requested';

export interface ManifestProposal {
  proposal_id: string;
  created_at: string;
  target: 'core' | 'limb' | 'policy';
  agent_id?: string;
  op: string;
  value: unknown;
  reason: string;
  evidence: number[];
  requires_cross_review: boolean;
  boundary_allowed: boolean;
  boundary_violations: string[];
  boundary_warnings: string[];
  boundary_path: string;
  review_verdict: CrossReviewVerdict;
  review_notes?: string;
  reviewed_at?: string;
  reviewer?: string;
  applied_at?: string;
}

function ensureDir(): string {
  const dir = getCrossReviewDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function storeProposal(proposal: Omit<ManifestProposal, 'proposal_id' | 'created_at'>): ManifestProposal {
  const dir = ensureDir();
  const full: ManifestProposal = {
    ...proposal,
    proposal_id: `prop-${randomUUID().slice(0, 8)}`,
    created_at: new Date().toISOString(),
  };
  writeFileSync(join(dir, `${full.proposal_id}.json`), JSON.stringify(full, null, 2), 'utf-8');
  return full;
}

export function loadProposal(proposalId: string): ManifestProposal | null {
  const path = join(getCrossReviewDir(), `${proposalId}.json`);
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, 'utf-8')) as ManifestProposal;
}

export function recordReview(
  proposalId: string,
  params: { verdict: 'approved' | 'changes_requested'; notes?: string; reviewer?: string },
): ManifestProposal | null {
  const proposal = loadProposal(proposalId);
  if (!proposal) return null;

  const updated: ManifestProposal = {
    ...proposal,
    review_verdict: params.verdict,
    review_notes: params.notes,
    reviewed_at: new Date().toISOString(),
    reviewer: params.reviewer ?? 'cross-review',
  };

  writeFileSync(join(getCrossReviewDir(), `${proposalId}.json`), JSON.stringify(updated, null, 2), 'utf-8');
  return updated;
}

export function markProposalApplied(proposalId: string): ManifestProposal | null {
  const proposal = loadProposal(proposalId);
  if (!proposal) return null;

  const updated: ManifestProposal = {
    ...proposal,
    applied_at: new Date().toISOString(),
  };
  writeFileSync(join(getCrossReviewDir(), `${proposalId}.json`), JSON.stringify(updated, null, 2), 'utf-8');
  return updated;
}

export function listProposals(limit = 50): ManifestProposal[] {
  const dir = getCrossReviewDir();
  if (!existsSync(dir)) return [];

  return readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .map((f) => JSON.parse(readFileSync(join(dir, f), 'utf-8')) as ManifestProposal)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, limit);
}

export function requiresCrossReview(params: {
  target: string;
  agentId?: string;
  boundaryAllowed: boolean;
  templateRequiresReview?: boolean;
}): boolean {
  if (params.target === 'core' || params.target === 'policy') return true;
  if (
    params.agentId &&
    ['atlas-orchestrator', 'aegis-security', 'echo-memory'].includes(params.agentId)
  ) {
    return true;
  }
  if (params.templateRequiresReview) return true;
  return false;
}
