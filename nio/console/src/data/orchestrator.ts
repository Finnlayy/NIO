export type WorkflowState =
  | "PLANNING"
  | "EXECUTING"
  | "REVIEWING"
  | "EVALUATING"
  | "REVISING"
  | "DEPLOYING"
  | "ESCALATED";

export interface OrchestratorAgent {
  id: string;
  role: string;
  mission: string;
  model: string;
  contextWindow: string;
  tools: string[];
  authority: "supervisor" | "worker" | "gatekeeper";
  color: string;
}

export const orchestratorAgents: OrchestratorAgent[] = [
  {
    id: "orchestrator-supervisor",
    role: "Supervisor Orchestrator",
    mission: "Erstellt den Ausführungsplan, delegiert Work Packs, validiert Gates und eskaliert Unsicherheit an einen Menschen.",
    model: "Frontier reasoning model",
    contextWindow: "128k",
    tools: ["LangGraph state", "Agent registry", "Memory retrieval", "Policy engine"],
    authority: "supervisor",
    color: "cyan",
  },
  {
    id: "repo-cartographer",
    role: "Repository Cartographer",
    mission: "Kartiert Ownership, Abhängigkeiten, Build-Targets und den kleinsten sicheren Änderungsbereich.",
    model: "Fast code model",
    contextWindow: "64k",
    tools: ["Git read-only", "Code search", "Dependency graph"],
    authority: "worker",
    color: "blue",
  },
  {
    id: "c-performance-reviewer",
    role: "C Performance Reviewer",
    mission: "Prüft Speicherfehler, Datenrennen, ABI-Risiken, Latenz und numerische Stabilität im C-Kern.",
    model: "Code reasoning model",
    contextWindow: "128k",
    tools: ["clang-tidy", "ASan/UBSan", "perf harness", "Compiler"],
    authority: "worker",
    color: "orange",
  },
  {
    id: "python-test-engineer",
    role: "Python Test Engineer",
    mission: "Validiert Bindings, Property Tests, Regressionssuiten und die semantische Parität zwischen C und Python.",
    model: "Code reasoning model",
    contextWindow: "128k",
    tools: ["pytest", "Hypothesis", "coverage", "Benchmark suite"],
    authority: "worker",
    color: "yellow",
  },
  {
    id: "quant-domain-auditor",
    role: "Quant Domain Auditor",
    mission: "Prüft fachliche Invarianten, Look-ahead Bias, Risiko-Limits und Reproduzierbarkeit von Trading-Logik.",
    model: "High-precision reasoning model",
    contextWindow: "96k",
    tools: ["Scenario fixtures", "Invariant checks", "Domain rulebook"],
    authority: "gatekeeper",
    color: "pink",
  },
  {
    id: "security-sandbox-guardian",
    role: "Security & Sandbox Guardian",
    mission: "Blockiert Secret-Leaks, nicht erlaubte Netzwerkzugriffe und unisolierte Code-Ausführung.",
    model: "Security review model",
    contextWindow: "64k",
    tools: ["gVisor policy", "Secret scanner", "SBOM", "Network policy"],
    authority: "gatekeeper",
    color: "red",
  },
  {
    id: "ui-systems-designer",
    role: "UI Systems Designer",
    mission: "Erstellt zugängliche, konsistente Interfaces und prüft visuelle Regressionen bei Produktänderungen.",
    model: "Multimodal UI model",
    contextWindow: "96k",
    tools: ["Storybook", "Playwright", "A11y scan", "Visual diff"],
    authority: "worker",
    color: "purple",
  },
  {
    id: "ci-evidence-runner",
    role: "CI Evidence Runner",
    mission: "Führt freigegebene Tests im isolierten Runner aus und normalisiert Compiler-, Test- und Coverage-Evidence.",
    model: "Tool-use model",
    contextWindow: "32k",
    tools: ["Docker runner", "CI logs", "JUnit", "Artifacts"],
    authority: "worker",
    color: "green",
  },
  {
    id: "pr-review-synthesizer",
    role: "PR Review Synthesizer",
    mission: "Verdichtet Findings zu priorisierten, nachvollziehbaren Review-Kommentaren mit Evidenzlinks.",
    model: "Review model",
    contextWindow: "96k",
    tools: ["GitHub PR read", "Diff parser", "Review template"],
    authority: "worker",
    color: "indigo",
  },
  {
    id: "memory-eval-curator",
    role: "Memory & Eval Curator",
    mission: "Bewertet Outputs, speichert erfolgreiche und fehlgeschlagene Strategien und aktualisiert Retrieval-Kontext.",
    model: "Evaluation model",
    contextWindow: "64k",
    tools: ["Vector store adapter", "PostgreSQL ledger", "Eval rubric", "LangSmith trace"],
    authority: "gatekeeper",
    color: "teal",
  },
];

export interface StateNode {
  id: WorkflowState;
  label: string;
  description: string;
  owner: string;
  gate: string;
  next: WorkflowState[];
}

export const workflowStates: StateNode[] = [
  {
    id: "PLANNING",
    label: "Planning",
    description: "Zerlegt das Ziel in Work Packs, ordnet Risiken zu und lädt relevante Memory-Evidence.",
    owner: "Supervisor Orchestrator",
    gate: "Scope und Sandbox-Profil vorhanden",
    next: ["EXECUTING", "ESCALATED"],
  },
  {
    id: "EXECUTING",
    label: "Executing",
    description: "Worker führen ausschließlich erlaubte Tools im ephemeren Sandbox-Container aus.",
    owner: "Domain Worker Agents",
    gate: "Keine Policy-Verletzung; Artefakte gespeichert",
    next: ["REVIEWING", "ESCALATED"],
  },
  {
    id: "REVIEWING",
    label: "Reviewing",
    description: "Unabhängige Agenten prüfen Diffs, Testergebnisse und fachliche Invarianten.",
    owner: "Review Synthesizer + Gatekeeper",
    gate: "Evidenz verlinkt und Findings klassifiziert",
    next: ["EVALUATING", "REVISING", "ESCALATED"],
  },
  {
    id: "EVALUATING",
    label: "Evaluating",
    description: "Die Rubrik bewertet harte Metriken und die Qualität der Agentenantworten.",
    owner: "Memory & Eval Curator",
    gate: "Composite score ≥ 85 für Deployment",
    next: ["DEPLOYING", "REVISING", "ESCALATED"],
  },
  {
    id: "REVISING",
    label: "Revising",
    description: "Die Ursache wird in Memory gespeichert; ein gezieltes Work Pack startet mit angepasstem Kontext erneut.",
    owner: "Supervisor Orchestrator",
    gate: "Revisionen ≤ 2, sonst Human Gate",
    next: ["EXECUTING", "ESCALATED"],
  },
  {
    id: "DEPLOYING",
    label: "Deploying",
    description: "Nur freigegebene Artefakte gehen über einen expliziten Release-Gate in die Zielumgebung.",
    owner: "CI Evidence Runner",
    gate: "Human release approval + green CI",
    next: [],
  },
  {
    id: "ESCALATED",
    label: "Human-in-the-Loop",
    description: "Stoppt autonome Ausführung und liefert Entscheidung, Evidenz und sichere Optionen an einen Menschen.",
    owner: "Human Owner",
    gate: "Explizite Freigabe, Ablehnung oder Scope-Anpassung",
    next: ["PLANNING", "REVISING"],
  },
];

export const sandboxPolicies = [
  {
    title: "Ephemeral by default",
    detail: "Jeder Run startet in einem kurzlebigen Docker-/gVisor-Container. Kein Container darf wiederverwendete Arbeitsdaten besitzen.",
    badge: "ISOLATION",
  },
  {
    title: "Deny network by default",
    detail: "Egress bleibt blockiert; nur explizit allow-gelistete Paketspiegel oder Git-Read-Zugriffe werden über kurzlebige Tokens freigegeben.",
    badge: "NETWORK",
  },
  {
    title: "Least-privilege credentials",
    detail: "Agents erhalten zeitlich begrenzte, auf Repository und Aktion eingeschränkte Credentials. Production Secrets bleiben unerreichbar.",
    badge: "SECRETS",
  },
  {
    title: "No direct production writes",
    detail: "Agenten erzeugen Pull Requests und Evidence, aber keine direkten Deployments. Release-Aktionen benötigen menschliche Freigabe.",
    badge: "HUMAN GATE",
  },
];

export const evalMetrics = [
  { key: "buildIntegrity", label: "Build & Syntax", weight: 25, threshold: 100, description: "Compiler, Linter und Imports ohne Fehler" },
  { key: "testEvidence", label: "Test Evidence", weight: 25, threshold: 90, description: "Bestehende und neue Tests grün; Coverage-Ziel erreicht" },
  { key: "domainCorrectness", label: "Fachliche Korrektheit", weight: 25, threshold: 85, description: "Invarianten, Risiko- und Datenregeln eingehalten" },
  { key: "securityPosture", label: "Sandbox & Security", weight: 15, threshold: 100, description: "Keine Policy-Verletzung, keine Secret-Exposition" },
  { key: "reviewQuality", label: "Review-Qualität", weight: 10, threshold: 80, description: "Findings sind präzise, priorisiert und evidenzbasiert" },
];

export const masterPromptManifest = {
  framework: "Visual Systemmasterprompt Framework v2",
  objective: "Build a safe, self-correcting autonomous orchestration backbone for hybrid C/Python code review and delivery.",
  principles: [
    "Plan before tool use; retrieve relevant prior evidence before planning.",
    "Execute only inside ephemeral least-privilege sandboxes.",
    "Treat CI logs, compiler output and tests as evidence, not optional commentary.",
    "Never deploy or write to production without a human release gate.",
    "When evaluation is below threshold, store the failure cause and revise the strategy before retrying.",
  ],
  states: workflowStates.map(({ id, next, owner, gate }) => ({ id, owner, gate, transitions: next })),
  agents: orchestratorAgents.map(({ id, role, model, contextWindow, tools, authority }) => ({
    agentId: id,
    role,
    llmModel: model,
    contextWindow,
    tools,
    authority,
  })),
  eval: {
    deployThreshold: 85,
    maxAutonomousRevisions: 2,
    metrics: evalMetrics.map(({ key, weight, threshold }) => ({ key, weight, threshold })),
    onFailure: "persist_memory -> revise_prompt_strategy -> replan; escalate if policy failure or revision limit reached",
  },
  sandbox: {
    runtime: ["Docker", "gVisor"],
    network: "deny-by-default",
    productionWrites: "human-approval-required",
    secrets: "short-lived scoped tokens only",
  },
};
