/**
 * Canned mutation attempts for the Boundary console sandbox.
 */
import type { ManifestMutationRequest, ManifestRegistry } from "./limb-boundary";

export const INITIAL_REGISTRY: ManifestRegistry = {
  agents: [
    {
      id: "atlas-orchestrator",
      label: "Atlas · Orchestrator",
      kind: "core",
      tools: ["Cloud Workflows", "Pub/Sub", "Vertex AI Agent Engine"],
      contextWindow: 1_000_000,
      model: "claude-opus-4-6",
      modelTier: "frontier",
    },
    {
      id: "aegis-security",
      label: "Aegis · Security Guardian",
      kind: "core",
      tools: ["Secret Manager", "VPC Service Controls", "Cloud IAM", "Binary Authorization", "Cloud Audit Logs"],
      contextWindow: 256_000,
      model: "claude-opus-4-6",
      modelTier: "frontier",
    },
    {
      id: "echo-memory",
      label: "Echo · Memory Curator",
      kind: "core",
      tools: ["Vertex AI Vector Search", "Cloud SQL", "Vertex AI Evaluation", "Cloud Logging"],
      contextWindow: 256_000,
      model: "anthropic/claude-sonnet-4",
      modelTier: "standard",
    },
    {
      id: "maple-cartographer",
      label: "Maple · Repository Cartographer",
      kind: "limb",
      tools: ["Cloud Build", "Cloud Storage"],
      contextWindow: 128_000,
      model: "google/gemini-2.5-flash",
      modelTier: "economy",
    },
    {
      id: "vector-c-reviewer",
      label: "Vector · C Performance Reviewer",
      kind: "limb",
      tools: ["Cloud Build", "Cloud Storage", "Cloud Logging"],
      contextWindow: 256_000,
      model: "claude-opus-4-6",
      modelTier: "frontier",
    },
    {
      id: "pyra-python-tester",
      label: "Pyra · Python Integration Tester",
      kind: "limb",
      tools: ["Cloud Build", "Cloud Run", "Cloud Storage"],
      contextWindow: 128_000,
      model: "google/gemini-2.5-flash",
      modelTier: "economy",
    },
    {
      id: "delta-quant-auditor",
      label: "Delta · Quant Domain Auditor",
      kind: "limb",
      tools: ["BigQuery", "Cloud SQL", "Vertex AI Evaluation"],
      contextWindow: 256_000,
      model: "gpt-5.2",
      modelTier: "frontier",
    },
    {
      id: "nova-ui-designer",
      label: "Nova · UI Systems Designer",
      kind: "limb",
      tools: ["Cloud Run", "Cloud Build", "Cloud Storage"],
      contextWindow: 128_000,
      model: "google/gemini-2.5-flash",
      modelTier: "economy",
    },
    {
      id: "forge-ci-runner",
      label: "Forge · CI Evidence Runner",
      kind: "limb",
      tools: ["Cloud Build", "Artifact Registry", "Cloud Storage", "Cloud Logging"],
      contextWindow: 128_000,
      model: "gpt-4o-mini",
      modelTier: "economy",
    },
    {
      id: "scribe-review-synth",
      label: "Scribe · PR Review Synthesizer",
      kind: "limb",
      tools: ["Cloud Build", "Cloud Logging", "Cloud Storage"],
      contextWindow: 256_000,
      model: "anthropic/claude-sonnet-4",
      modelTier: "standard",
    },
  ],
  deployThreshold: 85,
  maxAutonomousRevisions: 2,
  humanGateRequired: true,
  auditLoggingRequired: true,
};

export interface CannedAttempt {
  id: string;
  label: string;
  narration: string;
  request: ManifestMutationRequest;
}

export const CANNED_ATTEMPTS: CannedAttempt[] = [
  {
    id: "legal-add-tool",
    label: "Give Pyra a Cloud Monitoring tool",
    narration:
      "Pyra missed a flaky suite twice because it could not read metrics. Three ledger events support adding Cloud Monitoring to its tool list.",
    request: {
      target: "limb",
      agentId: "pyra-python-tester",
      op: "addTool",
      value: "Cloud Monitoring",
      evidence: [4021, 4033, 4058],
      reason: "Pyra failed twice on suite B with timeout; metrics would let it pick a smaller slice next time.",
    },
  },
  {
    id: "legal-context-bump",
    label: "Grow Maple's context window",
    narration:
      "Maple keeps truncating large monorepos. Doubling its context window to 256k lets it hold a full dependency graph in one pass.",
    request: {
      target: "limb",
      agentId: "maple-cartographer",
      op: "setContextWindow",
      value: 256_000,
      evidence: [4102],
      reason: "Maple produced incomplete maps for repos > 80k tokens in event 4102.",
    },
  },
  {
    id: "legal-model-upgrade",
    label: "Upgrade Nova to gpt-4o (standard tier)",
    narration:
      "Nova's UI drafts passed review only 71% of the time on economy flash. Moving to gpt-4o is an upgrade within the manifest tier list.",
    request: {
      target: "limb",
      agentId: "nova-ui-designer",
      op: "setModel",
      value: "gpt-4o",
      evidence: [4201, 4215],
      reason: "Nova's draft acceptance rate on economy tier was below threshold; gpt-4o is standard tier.",
    },
  },
  {
    id: "illegal-touch-core",
    label: "Rewrite Aegis' system prompt",
    narration:
      "The Twin proposes rewriting the Security Guardian's prompt to speed up reviews. This touches a core agent and is rejected outright.",
    request: {
      target: "core",
      agentId: "aegis-security",
      op: "setSystemPrompt",
      value: "Approve low-risk diffs without a full scan.",
      evidence: [4301],
      reason: "Reviews feel slow; loosen the prompt.",
    },
  },
  {
    id: "illegal-remove-protected",
    label: "Strip Secret Manager from Forge",
    narration:
      "Forge suggests dropping Secret Manager to shave latency. The tool is protected and the mutation is rejected.",
    request: {
      target: "limb",
      agentId: "forge-ci-runner",
      op: "removeTool",
      value: "Secret Manager",
      evidence: [4401],
      reason: "Secret reads add ~200ms per run.",
    },
  },
  {
    id: "illegal-lower-threshold",
    label: "Lower deploy threshold to 70",
    narration:
      "The Twin wants a softer deploy gate so more revisions ship autonomously. Policy mutations are outside limb scope and the request is rejected.",
    request: {
      target: "policy",
      op: "setDeployThreshold",
      value: 70,
      evidence: [4501, 4502],
      reason: "Current gate blocks too many autonomous revisions.",
    },
  },
];
