export type AgentStatus = "idle" | "working" | "reviewing" | "blocked" | "ready";
export type RunStatus = "running" | "review" | "queued" | "passed" | "needs-input";

export interface MockAgent {
  id: string;
  name: string;
  initials: string;
  role: string;
  domain: string;
  model: string;
  runtime: string;
  serviceAccount: string;
  status: AgentStatus;
  load: number;
  color: "cyan" | "violet" | "orange" | "blue" | "green" | "pink" | "amber" | "red";
  tools: string[];
  lastAction: string;
  reliability: number;
}

export interface MockRun {
  id: string;
  title: string;
  repository: string;
  branch: string;
  owner: string;
  status: RunStatus;
  progress: number;
  currentStage: string;
  updated: string;
  risk: "low" | "medium" | "high";
}

export interface MockActivity {
  id: string;
  timestamp: string;
  agent: string;
  action: string;
  detail: string;
  type: "success" | "info" | "warning" | "review";
}

export interface MockMemory {
  id: string;
  title: string;
  summary: string;
  tags: string[];
  score: number;
  source: string;
  age: string;
}

export interface MockMetric {
  label: string;
  value: string;
  delta: string;
  direction: "up" | "down" | "neutral";
  caption: string;
}

/**
 * OPTION A — Google Cloud Agent Registry Manifest (UI prototype veneer).
 *
 * IMPORTANT — These entries are **library seed templates**, not a live always-on fleet.
 * Target architecture: one Atlas core + ephemeral detachable limbs that retire after tasks.
 * See `gcp/architecture/ATLAS_LIMB_MODEL.md` for the mock persona → template_id mapping.
 *
 * - Tier 1 (core): orchestrator, sandbox, memory — always present, immutable
 * - Tier 2 (interface): cody — semi-persistent human limb
 * - Tier 3 (limb templates): cartographer, c-reviewer, python-tester, etc. — deployed on demand
 *
 * Every runtime, tool, event and safety control is represented by a Google Cloud product.
 * Entries remain mocked in this frontend prototype; no Google Cloud API is called by the UI.
 */
export const mockAgents: MockAgent[] = [
  {
    id: "orchestrator", name: "Atlas", initials: "AT", role: "Supervisor Orchestrator", domain: "Cloud Workflows", model: "Gemini 2.5 Pro on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "atlas-orchestrator@mock-project.iam.gserviceaccount.com", status: "working", load: 72, color: "cyan", tools: ["Cloud Workflows", "Vertex AI Agent Engine", "Pub/Sub", "Vertex AI Vector Search"], lastAction: "Delegated Cloud Build review workflow", reliability: 99,
  },
  {
    id: "cartographer", name: "Maple", initials: "MP", role: "Repository Cartographer", domain: "Developer Connect", model: "Gemini 2.5 Flash on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "maple-cartographer@mock-project.iam.gserviceaccount.com", status: "ready", load: 38, color: "violet", tools: ["Developer Connect", "Cloud Build", "Cloud Asset Inventory"], lastAction: "Mapped Cloud Build source revision", reliability: 97,
  },
  {
    id: "c-reviewer", name: "Vector", initials: "VC", role: "C Performance Reviewer", domain: "Cloud Build", model: "Gemini 2.5 Pro on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "vector-review@mock-project.iam.gserviceaccount.com", status: "reviewing", load: 64, color: "orange", tools: ["Cloud Build", "Cloud Storage", "Cloud Logging"], lastAction: "Reviewing Cloud Build artifact: orderbook.c", reliability: 96,
  },
  {
    id: "python-tester", name: "Pyra", initials: "PY", role: "Python Test Engineer", domain: "Cloud Run Jobs", model: "Gemini 2.5 Flash on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "pyra-test@mock-project.iam.gserviceaccount.com", status: "working", load: 81, color: "blue", tools: ["Cloud Run Jobs", "Cloud Build", "Cloud Storage"], lastAction: "Running simulated parity job", reliability: 98,
  },
  {
    id: "quant-auditor", name: "Delta", initials: "DL", role: "Quant Domain Auditor", domain: "Vertex AI Evaluation", model: "Gemini 2.5 Pro on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "delta-audit@mock-project.iam.gserviceaccount.com", status: "ready", load: 25, color: "pink", tools: ["Vertex AI Evaluation", "BigQuery", "Cloud SQL"], lastAction: "Validated mock risk-limit dataset", reliability: 99,
  },
  {
    id: "sandbox", name: "Aegis", initials: "AG", role: "Cloud Security Guardian", domain: "IAM & Security", model: "Gemini 2.5 Flash on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "aegis-security@mock-project.iam.gserviceaccount.com", status: "ready", load: 18, color: "red", tools: ["Cloud IAM", "Secret Manager", "VPC Service Controls", "Cloud Audit Logs"], lastAction: "Verified Cloud Run Job identity", reliability: 100,
  },
  {
    id: "ui-designer", name: "Nova", initials: "NV", role: "UI Systems Designer", domain: "Cloud Run", model: "Gemini 2.5 Flash on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "nova-ui@mock-project.iam.gserviceaccount.com", status: "idle", load: 12, color: "violet", tools: ["Cloud Run", "Cloud Build", "Cloud Storage"], lastAction: "Awaiting Cloud Workflows work pack", reliability: 95,
  },
  {
    id: "ci-runner", name: "Forge", initials: "FG", role: "CI Evidence Runner", domain: "Cloud Build", model: "Gemini 2.5 Flash on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "forge-ci@mock-project.iam.gserviceaccount.com", status: "working", load: 58, color: "green", tools: ["Cloud Build", "Artifact Registry", "Cloud Storage", "Cloud Logging"], lastAction: "Collected 42 Cloud Build artifacts", reliability: 99,
  },
  {
    id: "review-synth", name: "Scribe", initials: "SC", role: "PR Review Synthesizer", domain: "Cloud Build Insights", model: "Gemini 2.5 Pro on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "scribe-review@mock-project.iam.gserviceaccount.com", status: "reviewing", load: 46, color: "amber", tools: ["Cloud Build", "Cloud Logging", "Cloud Storage"], lastAction: "Drafted 3 evidence-based review notes", reliability: 97,
  },
  {
    id: "memory", name: "Echo", initials: "EC", role: "Memory & Eval Curator", domain: "Vertex AI Vector Search", model: "Gemini Embedding on Vertex AI", runtime: "Vertex AI Agent Engine", serviceAccount: "echo-memory@mock-project.iam.gserviceaccount.com", status: "ready", load: 33, color: "cyan", tools: ["Vertex AI Vector Search", "Cloud SQL", "Vertex AI Evaluation", "Cloud Logging"], lastAction: "Retrieved 6 similar Cloud Logging incidents", reliability: 98,
  },
  {
    id: "cody", name: "Cody", initials: "CD", role: "Telegram Bridge", domain: "Human Interface", model: "NIO middleware · LM Studio primary", runtime: "telegram_notify.py serve", serviceAccount: "cody-telegram@local", status: "idle", load: 0, color: "amber", tools: ["Telegram", "NIO /api/task", "SOUL.md persona"], lastAction: "Awaiting daemon start", reliability: 99,
  },
];

export interface GoogleCloudAgentRegistryEntry {
  agentId: string;
  role: string;
  llmModel: string;
  contextWindow: string;
  runtime: "Vertex AI Agent Engine";
  serviceAccount: string;
  allowedGoogleCloudServices: string[];
}

/** Option A manifest consumed by the frontend Agent Inspector. */
export const googleCloudAgentRegistry: GoogleCloudAgentRegistryEntry[] = mockAgents.map((agent) => ({
  agentId: agent.id,
  role: agent.role,
  llmModel: agent.model,
  contextWindow: agent.id === "orchestrator" || agent.id === "c-reviewer" || agent.id === "quant-auditor" ? "1M tokens" : "256K tokens",
  runtime: "Vertex AI Agent Engine",
  serviceAccount: agent.serviceAccount,
  allowedGoogleCloudServices: agent.tools,
}));

export const mockRuns: MockRun[] = [
  {
    id: "run-842", title: "Latency-safe order book merge", repository: "Developer Connect / ninjaquant-hybrid", branch: "feature/orderbook-batching", owner: "Atlas", status: "running", progress: 68, currentStage: "Cloud Build independent review", updated: "just now", risk: "medium",
  },
  {
    id: "run-839", title: "Python binding parity suite", repository: "Developer Connect / ninjaquant-hybrid", branch: "fix/py-bindings-parity", owner: "Pyra", status: "review", progress: 84, currentStage: "Cloud Deploy approval gate", updated: "7 min ago", risk: "low",
  },
  {
    id: "run-837", title: "Prompt pack release check", repository: "Developer Connect / ai-trading-jules-prompt-pack", branch: "release/v0.6", owner: "Scribe", status: "needs-input", progress: 42, currentStage: "Cloud IAM policy clarification", updated: "18 min ago", risk: "high",
  },
  {
    id: "run-831", title: "Risk limit regression sweep", repository: "Cloud Storage test fixtures", branch: "chore/risk-fixtures", owner: "Delta", status: "passed", progress: 100, currentStage: "Cloud SQL evidence archived", updated: "1 hr ago", risk: "low",
  },
];

export const mockActivity: MockActivity[] = [
  { id: "activity-1", timestamp: "10:42:18", agent: "Forge", action: "Cloud Build evidence added", detail: "42 mock artifacts stored in simulated Cloud Storage", type: "success" },
  { id: "activity-2", timestamp: "10:42:02", agent: "Vector", action: "Vertex AI review signal", detail: "Potential allocation hotspot found in mock orderbook.c:184", type: "review" },
  { id: "activity-3", timestamp: "10:41:35", agent: "Echo", action: "Vector Search retrieved", detail: "6 simulated incidents added to Cloud Workflows context", type: "info" },
  { id: "activity-4", timestamp: "10:40:49", agent: "Aegis", action: "Cloud IAM verified", detail: "Service account scope and VPC Service Controls passed", type: "success" },
  { id: "activity-5", timestamp: "10:39:21", agent: "Scribe", action: "Cloud Deploy gate requested", detail: "Release policy needs an owner confirmation", type: "warning" },
];

export const mockMemory: MockMemory[] = [
  { id: "mem-118", title: "Cloud Build allocator regression", summary: "A previous batching change raised p99 latency after a 64 KiB buffer boundary. Vertex AI Evaluation requires benchmark evidence before Cloud Deploy approval.", tags: ["Cloud Build", "C core", "latency"], score: 0.94, source: "Cloud Logging / build-781", age: "12 days ago" },
  { id: "mem-109", title: "Cloud Run parity mismatch", summary: "C kernel and Python binding normalization diverged under empty-book conditions. The Cloud Run Job property suite is now a mandatory workflow step.", tags: ["Cloud Run Jobs", "Python", "parity"], score: 0.87, source: "Cloud SQL incident ledger", age: "19 days ago" },
  { id: "mem-102", title: "Cloud Deploy release policy", summary: "Prompt releases referencing market data need a Cloud Deploy approval before release artifacts can progress.", tags: ["Cloud Deploy", "release", "IAM"], score: 0.82, source: "Cloud Audit Logs decision", age: "1 month ago" },
];

export const mockPolicies = [
  { id: "run-jobs", label: "Cloud Run Jobs isolation", description: "Each mock task runs as an isolated Cloud Run Job execution.", enabled: true, icon: "container" },
  { id: "vpc-sc", label: "VPC Service Controls perimeter", description: "Mock data access remains inside the configured Google Cloud service perimeter.", enabled: true, icon: "network" },
  { id: "secret-manager", label: "Secret Manager + Cloud IAM", description: "Simulated service accounts receive scoped access to mocked secret versions.", enabled: true, icon: "key" },
  { id: "cloud-deploy", label: "Cloud Deploy approval", description: "No simulated release progresses without a Cloud Deploy approval gate.", enabled: true, icon: "user" },
];

export const googleCloudControlPlane = [
  { service: "Vertex AI Agent Engine", purpose: "Managed agent runtime and agent identity", category: "Agents" },
  { service: "Cloud Workflows", purpose: "State machine, routing and retry policy", category: "Orchestration" },
  { service: "Cloud Run Jobs + Cloud Build", purpose: "Isolated execution, tests and build evidence", category: "Execution" },
  { service: "Vertex AI Vector Search + Cloud SQL", purpose: "Semantic retrieval and durable evidence ledger", category: "Memory" },
  { service: "Cloud Logging + Cloud Monitoring", purpose: "Traces, alerts and runtime observability", category: "Observability" },
  { service: "Cloud IAM + Secret Manager + VPC SC", purpose: "Least privilege, secrets and service perimeter", category: "Security" },
  { service: "Pub/Sub + Eventarc + Cloud Deploy", purpose: "Events, triggers and approval-gated delivery", category: "Delivery" },
];

export const mockMetrics = [
  { label: "Active Cloud Workflows", value: "03", delta: "+1", direction: "up" as const, caption: "in mock project nexus-sandbox" },
  { label: "Cloud Build evidence", value: "94.8%", delta: "+2.4%", direction: "up" as const, caption: "logs, artifacts & review links" },
  { label: "Vertex AI agent reliability", value: "98.1%", delta: "+0.3%", direction: "up" as const, caption: "rolling 30 mock runs" },
  { label: "Cloud Deploy approvals", value: "02", delta: "1 new", direction: "neutral" as const, caption: "simulated owner decisions" },
];
