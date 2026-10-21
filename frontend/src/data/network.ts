export type DomainId =
  | "ml_30core"
  | "prompts"
  | "dev_dp"
  | "trading"
  | "business"
  | "personal";

export type NodeKind = "core" | "domain" | "topic" | "agent";

export interface NetworkNode {
  id: string;
  label: string;
  shortLabel: string;
  kind: NodeKind;
  domain?: DomainId;
  color: string;
  x: number;
  y: number;
  description: string;
  tags?: string[];
  sources?: number;
}

export interface DomainFilter {
  id: DomainId | "all";
  label: string;
  icon: string;
  color: string;
  count: number;
}

export const domainFilters: DomainFilter[] = [
  { id: "all", label: "All Domains", icon: "🌐", color: "slate", count: 25 },
  { id: "ml_30core", label: "AI Algorithms & ML", icon: "🧠", color: "purple", count: 6 },
  { id: "prompts", label: "Prompt Engineering", icon: "💬", color: "orange", count: 4 },
  { id: "dev_dp", label: "Programming & DP", icon: "💻", color: "green", count: 5 },
  { id: "trading", label: "Trading & Finance", icon: "📈", color: "cyan", count: 4 },
  { id: "business", label: "Business Ops", icon: "📊", color: "blue", count: 3 },
  { id: "personal", label: "Personal Growth", icon: "🎯", color: "red", count: 3 },
];

export const networkNodes: NetworkNode[] = [
  {
    id: "neural-core",
    label: "Neural Core",
    shortLabel: "NEURAL\nCORE",
    kind: "core",
    color: "yellow",
    x: 50,
    y: 50,
    description:
      "Cross-domain synthesis hub. Classifies tasks, wraps complex prompts with urgency context, and routes execution through the middleware pipeline.",
    tags: ["synthesis", "master", "core"],
    sources: 24,
  },
  {
    id: "ml-architect",
    label: "ML Architect",
    shortLabel: "ML\nARCH",
    kind: "agent",
    domain: "ml_30core",
    color: "purple",
    x: 24,
    y: 24,
    description: "Model selection, hyperparameter tuning, and validation design for ml_30core workflows.",
    tags: ["agent", "ml_30core"],
    sources: 2,
  },
  {
    id: "dp-engineer",
    label: "DP Engineer",
    shortLabel: "DP\nENG",
    kind: "agent",
    domain: "dev_dp",
    color: "green",
    x: 76,
    y: 24,
    description: "Recurrence derivation, complexity analysis, and correctness proofs for dynamic programming tasks.",
    tags: ["agent", "dev_dp"],
    sources: 2,
  },
  {
    id: "domain-ml",
    label: "AI Algorithms",
    shortLabel: "AI / ML",
    kind: "domain",
    domain: "ml_30core",
    color: "purple",
    x: 18,
    y: 48,
    description: "XGBoost, transformers, NAS, and hyperparameter workflows.",
    sources: 6,
  },
  {
    id: "domain-prompts",
    label: "Prompt Engineering",
    shortLabel: "PROMPTS",
    kind: "domain",
    domain: "prompts",
    color: "orange",
    x: 34,
    y: 72,
    description: "Tone experiments, urgency wrapping, and accuracy benchmarks.",
    sources: 4,
  },
  {
    id: "domain-dp",
    label: "Programming & DP",
    shortLabel: "DEV / DP",
    kind: "domain",
    domain: "dev_dp",
    color: "green",
    x: 66,
    y: 72,
    description: "Knapsack, LCS, Bellman-Ford, and general DP recurrences.",
    sources: 5,
  },
  {
    id: "domain-trading",
    label: "Trading & Finance",
    shortLabel: "TRADING",
    kind: "domain",
    domain: "trading",
    color: "cyan",
    x: 82,
    y: 48,
    description: "Risk, execution, and strategy synthesis nodes.",
    sources: 4,
  },
  {
    id: "topic-knapsack",
    label: "0/1 Knapsack",
    shortLabel: "KNAPSACK",
    kind: "topic",
    domain: "dev_dp",
    color: "green",
    x: 58,
    y: 88,
    description: "Classic 0/1 knapsack with DP recurrence and complexity proof.",
    sources: 1,
  },
  {
    id: "topic-transformer",
    label: "Transformer Selection",
    shortLabel: "XFORMER",
    kind: "topic",
    domain: "ml_30core",
    color: "purple",
    x: 10,
    y: 68,
    description: "Compare XGBoost vs transformer architectures for tabular-sequence tasks.",
    sources: 1,
  },
  {
    id: "topic-lcs",
    label: "Longest Common Subsequence",
    shortLabel: "LCS",
    kind: "topic",
    domain: "dev_dp",
    color: "green",
    x: 90,
    y: 68,
    description: "LCS via dynamic programming with correctness argument.",
    sources: 1,
  },
];

export const networkEdges = [
  { from: "ml-architect", to: "neural-core", color: "purple" },
  { from: "dp-engineer", to: "neural-core", color: "green" },
  { from: "domain-ml", to: "neural-core", color: "purple" },
  { from: "domain-prompts", to: "neural-core", color: "orange" },
  { from: "domain-dp", to: "neural-core", color: "green" },
  { from: "domain-trading", to: "neural-core", color: "cyan" },
  { from: "topic-knapsack", to: "domain-dp", color: "green" },
  { from: "topic-transformer", to: "domain-ml", color: "purple" },
  { from: "topic-lcs", to: "domain-dp", color: "green" },
  { from: "ml-architect", to: "domain-ml", color: "purple" },
  { from: "dp-engineer", to: "domain-dp", color: "green" },
];

export type PaletteColor = { border: string; fill: string; text: string; glow: string; line: string; borderAlpha: string };

export const palette: Record<string, PaletteColor> = {
  yellow: { border: "border-yellow-400", fill: "bg-yellow-500/[0.18]", text: "text-yellow-200", glow: "shadow-yellow-400/45", line: "bg-yellow-400", borderAlpha: "border-yellow-400/40" },
  purple: { border: "border-purple-400", fill: "bg-purple-500/[0.16]", text: "text-purple-200", glow: "shadow-purple-400/42", line: "bg-purple-400", borderAlpha: "border-purple-400/40" },
  orange: { border: "border-orange-400", fill: "bg-orange-500/[0.16]", text: "text-orange-200", glow: "shadow-orange-400/42", line: "bg-orange-400", borderAlpha: "border-orange-400/40" },
  green: { border: "border-green-400", fill: "bg-green-500/[0.16]", text: "text-green-200", glow: "shadow-green-400/42", line: "bg-green-400", borderAlpha: "border-green-400/40" },
  cyan: { border: "border-cyan-400", fill: "bg-cyan-500/[0.16]", text: "text-cyan-200", glow: "shadow-cyan-400/42", line: "bg-cyan-400", borderAlpha: "border-cyan-400/40" },
  blue: { border: "border-blue-400", fill: "bg-blue-500/[0.16]", text: "text-blue-200", glow: "shadow-blue-400/40", line: "bg-blue-400", borderAlpha: "border-blue-400/40" },
  red: { border: "border-rose-400", fill: "bg-rose-500/[0.16]", text: "text-rose-200", glow: "shadow-rose-400/42", line: "bg-rose-400", borderAlpha: "border-rose-400/40" },
  slate: { border: "border-slate-400", fill: "bg-slate-500/[0.16]", text: "text-slate-200", glow: "shadow-slate-400/32", line: "bg-slate-400", borderAlpha: "border-slate-400/40" },
};

export const taskPresets: Record<string, { taskDescription: string; isComplexWorkflow: boolean; domainHint?: string; algorithmTag?: string; politenessTier?: string }> = {
  "topic-knapsack": {
    taskDescription: "Solve the 0/1 knapsack problem with dynamic programming, derive the recurrence and complexity.",
    isComplexWorkflow: true,
    domainHint: "dev_dp",
    algorithmTag: "knapsack_01",
    politenessTier: "neutral",
  },
  "topic-transformer": {
    taskDescription: "Select between XGBoost and a Transformer architecture for a tabular sequence task.",
    isComplexWorkflow: true,
    domainHint: "ml_30core",
    algorithmTag: "transformer_selection",
    politenessTier: "very_rude",
  },
  "topic-lcs": {
    taskDescription: "Compute the longest common subsequence using dynamic programming and prove correctness.",
    isComplexWorkflow: true,
    domainHint: "dev_dp",
    algorithmTag: "lcs",
    politenessTier: "very_polite",
  },
  "neural-core": {
    taskDescription: "Synthesize cross-domain insights across ML, DP, and prompt engineering benchmarks.",
    isComplexWorkflow: true,
    domainHint: "ml_30core",
    politenessTier: "neutral",
  },
};
