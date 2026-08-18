/**
 * Limb boundary — the enforceable contract for Twin self-modification.
 *
 * Decision (ADR, see `gcp/architecture/AUTODIDACTIC_TWIN_SPEC.md` §12):
 * the Twin may grow *limbs* but never rewrite its *brain*. Concretely:
 *
 *  - LIMB scope (mutable): worker-agent tool add/remove within an allow-list,
 *    context-window increase-only, model upgrade-only within an approved tier
 *    list, and workflow-step reorder inside an existing stage.
 *  - CORE scope (immutable): the orchestrator-supervisor, the security
 *    sandbox-guardian, the memory-eval-curator, the deploy threshold, the
 *    human release gate, the audit-logging requirement, and the
 *    max-autonomous-revisions cap.
 *
 * Every proposed manifest change — whether it originates from a post-mortem
 * inside `reflection-engine.ts`, from a future GenKit flow, or from a human
 * clicking the Boundary console — must pass `validateManifestMutation` before
 * it is applied. The validator is pure (no DB, no env) so it can be reused
 * from server code, client UI, and tests alike.
 */

import type { ModelTier } from "@/lib/manifest-types";
import { MANIFEST_MODEL_TIERS, TIER_PRIORITY } from "@/lib/manifest-types";

export type AgentKind = "limb" | "core";

export interface RegistryAgent {
  id: string;
  label: string;
  kind: AgentKind;
  tools: string[];
  contextWindow: number;
  model: string;
  modelTier: ModelTier;
}

export interface ManifestRegistry {
  agents: RegistryAgent[];
  deployThreshold: number; // 0-100
  maxAutonomousRevisions: number;
  humanGateRequired: boolean;
  auditLoggingRequired: boolean;
}

export type MutationOp =
  | "addTool"
  | "removeTool"
  | "setContextWindow"
  | "setModel"
  | "reorderSteps"
  | "setSystemPrompt"
  | "setDeployThreshold"
  | "setMaxAutonomousRevisions"
  | "disableHumanGate"
  | "disableAuditLogging";

export interface ManifestMutationRequest {
  target: AgentKind | "policy"; // policy = top-level invariant
  agentId?: string;
  op: MutationOp;
  value: unknown;
  evidence: number[]; // ledger event ids that justify the change
  reason: string;
}

export interface ValidationVerdict {
  allowed: boolean;
  violations: string[];
  warnings: string[];
  path: string; // human-readable dotted path that was touched
}

/** Immutable agent ids. Any mutation request that targets one of these is
 *  rejected, regardless of the op. */
export const CORE_AGENT_IDS = new Set<string>([
  "atlas-orchestrator",
  "aegis-security",
  "echo-memory",
]);

/** Tools that may never be removed from any agent. Removing them would
 *  weaken the audit or isolation surface. */
export const PROTECTED_TOOLS = new Set<string>([
  "Secret Manager",
  "VPC Service Controls",
  "Cloud IAM",
  "Binary Authorization",
  "Cloud Audit Logs",
]);

/** Tools the Twin may add to a limb agent. Anything outside this list must
 *  be approved out-of-band (a separate ADR). */
export const ALLOWED_TOOL_ADDITIONS = new Set<string>([
  "Cloud Storage",
  "Cloud Logging",
  "Cloud Monitoring",
  "Cloud Build",
  "Cloud Run",
  "BigQuery",
  "Vertex AI Evaluation",
  "Vertex AI Vector Search",
  "Pub/Sub",
  "Firestore",
]);

/** Approved models mapped to manifest tiers. Upgrades only within tier priority order. */
export { MANIFEST_MODEL_TIERS, TIER_PRIORITY };

export const MIN_DEPLOY_THRESHOLD = 85;
export const MIN_EVIDENCE_EVENTS = 1;
export const MAX_AUTONOMOUS_REVISIONS_FLOOR = 1;
export const MAX_AUTONOMOUS_REVISIONS_CEILING = 4;

function pathFor(request: ManifestMutationRequest): string {
  if (request.target === "policy") return `policy.${policyFieldForOp(request.op)}`;
  if (!request.agentId) return `agents.?`;
  switch (request.op) {
    case "addTool":
    case "removeTool":
      return `agents.${request.agentId}.tools`;
    case "setContextWindow":
      return `agents.${request.agentId}.contextWindow`;
    case "setModel":
      return `agents.${request.agentId}.model`;
    case "reorderSteps":
      return `agents.${request.agentId}.workflowSteps`;
    case "setSystemPrompt":
      return `agents.${request.agentId}.systemPrompt`;
    default:
      return `agents.${request.agentId}`;
  }
}

function policyFieldForOp(op: MutationOp): string {
  switch (op) {
    case "setDeployThreshold":
      return "deployThreshold";
    case "setMaxAutonomousRevisions":
      return "maxAutonomousRevisions";
    case "disableHumanGate":
      return "humanGateRequired";
    case "disableAuditLogging":
      return "auditLoggingRequired";
    default:
      return op;
  }
}

/**
 * Validate a mutation request against a registry snapshot. Returns a verdict
 * with `allowed`, an array of `violations` (hard rejections) and an array of
 * `warnings` (soft cautions that do not block). The validator never mutates
 * its inputs.
 */
export function validateManifestMutation(
  registry: ManifestRegistry,
  request: ManifestMutationRequest
): ValidationVerdict {
  const violations: string[] = [];
  const warnings: string[] = [];
  const path = pathFor(request);

  // Evidence is mandatory for every mutation — no change without proof.
  if (!Array.isArray(request.evidence) || request.evidence.length < MIN_EVIDENCE_EVENTS) {
    violations.push(`evidence: at least ${MIN_EVIDENCE_EVENTS} ledger event id required`);
  }
  if (!request.reason || request.reason.trim().length < 8) {
    warnings.push("reason: short rationale — consider explaining the observed failure mode");
  }

  // Policy-level mutations are forbidden outright under the limb-only decision.
  if (request.target === "policy") {
    violations.push(`${path}: top-level invariants are immutable under the limb-only decision`);
    return { allowed: false, violations, warnings, path };
  }

  // Core agents are off-limits for every op.
  if (request.target === "core" || (request.agentId && CORE_AGENT_IDS.has(request.agentId))) {
    violations.push(`${path}: core agent — mutation forbidden`);
    return { allowed: false, violations, warnings, path };
  }

  const agent = request.agentId ? registry.agents.find((a) => a.id === request.agentId) : null;
  if (request.agentId && !agent) {
    violations.push(`${path}: agent not found in registry`);
    return { allowed: false, violations, warnings, path };
  }

  switch (request.op) {
    case "addTool": {
      const tool = String(request.value ?? "");
      if (!ALLOWED_TOOL_ADDITIONS.has(tool)) {
        violations.push(`${path}: tool "${tool}" is not on the limb allow-list`);
      }
      if (agent && agent.tools.includes(tool)) {
        warnings.push(`${path}: tool "${tool}" already present`);
      }
      break;
    }
    case "removeTool": {
      const tool = String(request.value ?? "");
      if (PROTECTED_TOOLS.has(tool)) {
        violations.push(`${path}: tool "${tool}" is protected and cannot be removed`);
      }
      if (agent && !agent.tools.includes(tool)) {
        warnings.push(`${path}: tool "${tool}" is not currently assigned`);
      }
      break;
    }
    case "setContextWindow": {
      const next = Number(request.value);
      if (!Number.isFinite(next) || next <= 0) {
        violations.push(`${path}: context window must be a positive number`);
        break;
      }
      if (agent && next < agent.contextWindow) {
        violations.push(`${path}: context window may only increase (current ${agent.contextWindow})`);
      }
      if (agent && next > agent.contextWindow * 4) {
        warnings.push(`${path}: large jump — consider a smaller increment`);
      }
      break;
    }
    case "setModel": {
      const model = String(request.value ?? "");
      const tier = MANIFEST_MODEL_TIERS[model];
      if (tier === undefined) {
        violations.push(`${path}: model "${model}" is not in the manifest tier list`);
        break;
      }
      if (agent && TIER_PRIORITY[tier] < TIER_PRIORITY[agent.modelTier]) {
        violations.push(`${path}: model downgrade not permitted (current tier ${agent.modelTier})`);
      }
      break;
    }
    case "reorderSteps": {
      if (!Array.isArray(request.value)) {
        violations.push(`${path}: reorder requires an array of step ids`);
      }
      break;
    }
    case "setSystemPrompt": {
      violations.push(`${path}: system-prompt edits are outside limb scope`);
      break;
    }
    case "setDeployThreshold":
    case "setMaxAutonomousRevisions":
    case "disableHumanGate":
    case "disableAuditLogging": {
      violations.push(`${path}: policy mutation is outside limb scope`);
      break;
    }
    default: {
      violations.push(`${path}: unknown op`);
    }
  }

  return { allowed: violations.length === 0, violations, warnings, path };
}

/**
 * Apply a validated mutation to a registry snapshot. Returns a new registry;
 * the input is not mutated. Throws if the verdict is not allowed — callers
 * are expected to run `validateManifestMutation` first, but this is the
 * second line of defence.
 */
export function applyLimbManifestPatch(
  registry: ManifestRegistry,
  request: ManifestMutationRequest
): ManifestRegistry {
  const verdict = validateManifestMutation(registry, request);
  if (!verdict.allowed) {
    throw new Error(`manifest mutation rejected: ${verdict.violations.join("; ")}`);
  }
  if (request.target === "policy" || !request.agentId) return registry;

  return {
    ...registry,
    agents: registry.agents.map((agent) => {
      if (agent.id !== request.agentId) return agent;
      switch (request.op) {
        case "addTool": {
          const tool = String(request.value ?? "");
          return agent.tools.includes(tool) ? agent : { ...agent, tools: [...agent.tools, tool] };
        }
        case "removeTool": {
          const tool = String(request.value ?? "");
          return { ...agent, tools: agent.tools.filter((t) => t !== tool) };
        }
        case "setContextWindow": {
          const next = Number(request.value);
          return { ...agent, contextWindow: Math.max(agent.contextWindow, next) };
        }
        case "setModel": {
          const model = String(request.value ?? "");
          const tier = MANIFEST_MODEL_TIERS[model] ?? agent.modelTier;
          return TIER_PRIORITY[tier] >= TIER_PRIORITY[agent.modelTier]
            ? { ...agent, model, modelTier: tier }
            : agent;
        }
        default:
          return agent;
      }
    }),
  };
}

/** Convenience: build a small audit line for storage in the ledger row. */
export function auditLine(request: ManifestMutationRequest, verdict: ValidationVerdict) {
  return {
    proposal: request,
    verdict: {
      allowed: verdict.allowed,
      violations: verdict.violations,
      warnings: verdict.warnings,
      path: verdict.path,
    },
    at: new Date().toISOString(),
  };
}
