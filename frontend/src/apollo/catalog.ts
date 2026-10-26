import type {
  FreeLLMModelCandidate,
  FreeLLMProviderKey,
  NodeCategory,
  NodeState,
  OrbState,
} from "./types";

/* ==================================================================== */
/* Palette — one place, so the canvas, the CSS and the shader agree.     */
/* ==================================================================== */
export const PALETTE = {
  obsidian: "#0a0f1d",
  cyan: "#00e5ff",
  violet: "#a855f7",
  amber: "#f59e0b",
  emerald: "#10b981",
  magenta: "#d946ef",
  crimson: "#ef4444",
  ink: "#050810",
} as const;

export const ORB_STATE_STYLE: Record<OrbState, { label: string; color: string; note: string }> = {
  IDLE: { label: "Harmonic idle", color: PALETTE.cyan, note: "breathing at 0.11 Hz" },
  LISTENING: { label: "Listening", color: "#38bdf8", note: "input channel open" },
  THINKING: { label: "Thinking", color: PALETTE.violet, note: "turbulence · plasma rotation" },
  FAILOVER_SWITCH: { label: "Failover switch", color: PALETTE.amber, note: "quota exhausted · hot swap" },
  DISPATCHING: { label: "Dispatching", color: "#22d3ee", note: "outbound axon flare" },
  SYNTHESIZING: { label: "Synthesizing", color: PALETTE.emerald, note: "absorbing node results" },
  ERROR: { label: "Halt", color: PALETTE.crimson, note: "damped crimson pulse" },
};

export const NODE_CATEGORY_STYLE: Record<
  NodeCategory,
  { label: string; short: string; color: string; glyph: string }
> = {
  ORCHESTRATOR: { label: "Orchestrator", short: "ORCH", color: "#60a5fa", glyph: "⌘" },
  FREELLM_ROUTER: { label: "FreeLLM Router", short: "ROUTER", color: PALETTE.amber, glyph: "⇄" },
  SANDBOX: { label: "Execution Sandbox", short: "SANDBOX", color: "#fb7185", glyph: "▤" },
  MCP_WORKER: { label: "MCP Worker", short: "MCP", color: "#34d399", glyph: "⌗" },
  DATA_STREAM: { label: "Data Stream", short: "STREAM", color: "#38bdf8", glyph: "≈" },
  INFERENCE: { label: "Inference Engine", short: "INFER", color: "#c084fc", glyph: "✦" },
  MEMORY: { label: "Memory Bank", short: "MEMORY", color: "#fbbf24", glyph: "◈" },
};

export const NODE_STATE_STYLE: Record<NodeState, { label: string; color: string }> = {
  LYMP_SPAWNING: { label: "Mitosis", color: "#22d3ee" },
  IDLE: { label: "Idle", color: "#64748b" },
  PROCESSING: { label: "Processing", color: "#a855f7" },
  STREAMING: { label: "Streaming", color: "#38bdf8" },
  COMPLETED: { label: "Complete", color: "#10b981" },
  FAULT: { label: "Fault", color: "#ef4444" },
};

/* ==================================================================== */
/* Free-tier provider catalogue                                          */
/*                                                                       */
/* DEMO CATALOGUE. These are the provider *slots* the vault knows about  */
/* and realistic endpoint counts, not a live registry probe. Real keys   */
/* stay in the encrypted vault; nothing here is a credential.            */
/* ==================================================================== */
export interface ProviderMeta {
  id: string;
  name: string;
  endpoints: number;
  region: string;
  freeTier: string;
}

export const PROVIDERS: ProviderMeta[] = [
  { id: "google", name: "Google Gemini", endpoints: 48, region: "global", freeTier: "AI Studio · 15 RPM" },
  { id: "groq", name: "Groq", endpoints: 26, region: "us-east", freeTier: "LPU · 30 RPM" },
  { id: "mistral", name: "Mistral", endpoints: 32, region: "eu-west", freeTier: "La Plateforme · 1 RPS" },
  { id: "cerebras", name: "Cerebras", endpoints: 18, region: "us-west", freeTier: "Inference Cloud" },
  { id: "openrouter", name: "OpenRouter", endpoints: 62, region: "global", freeTier: "aggregator · 20 RPM" },
  { id: "nvidia", name: "NVIDIA NIM", endpoints: 40, region: "us-east", freeTier: "build.nvidia.com · 40 RPM" },
  { id: "cohere", name: "Cohere", endpoints: 24, region: "us-east", freeTier: "trial key · 20 RPM" },
  { id: "huggingface", name: "HuggingFace", endpoints: 36, region: "global", freeTier: "Inference API" },
  { id: "together", name: "Together", endpoints: 34, region: "us-west", freeTier: "$1 credit" },
  { id: "fireworks", name: "Fireworks", endpoints: 29, region: "us-west", freeTier: "starter" },
  { id: "deepinfra", name: "DeepInfra", endpoints: 26, region: "us-east", freeTier: "pay-per-token" },
  { id: "hyperbolic", name: "Hyperbolic", endpoints: 17, region: "us-west", freeTier: "credits" },
  { id: "sambanova", name: "SambaNova", endpoints: 14, region: "us-east", freeTier: "free tier" },
  { id: "perplexity", name: "Perplexity", endpoints: 9, region: "global", freeTier: "sonar · 5 RPM" },
  { id: "cloudflare", name: "Cloudflare Workers AI", endpoints: 21, region: "edge", freeTier: "10k neurons/day" },
  { id: "github-models", name: "GitHub Models", endpoints: 20, region: "global", freeTier: "rate-limited" },
  { id: "ollama", name: "Ollama (local)", endpoints: 12, region: "localhost", freeTier: "self-hosted" },
  { id: "llamacpp", name: "llama.cpp (local)", endpoints: 8, region: "localhost", freeTier: "self-hosted" },
  { id: "vllm", name: "vLLM (local)", endpoints: 11, region: "localhost", freeTier: "self-hosted" },
  { id: "lmstudio", name: "LM Studio (local)", endpoints: 6, region: "localhost", freeTier: "self-hosted" },
  { id: "novita", name: "Novita", endpoints: 15, region: "global", freeTier: "credits" },
  { id: "glhf", name: "GLHF", endpoints: 9, region: "global", freeTier: "free" },
  { id: "kluster", name: "Kluster", endpoints: 8, region: "global", freeTier: "credits" },
  { id: "lambda", name: "Lambda Labs", endpoints: 9, region: "us-west", freeTier: "credits" },
  { id: "octoai", name: "OctoAI", endpoints: 6, region: "us-west", freeTier: "trial" },
  { id: "inferless", name: "Inferless", endpoints: 5, region: "global", freeTier: "serverless" },
  { id: "anyscale", name: "Anyscale", endpoints: 8, region: "us-east", freeTier: "trial" },
  { id: "replicate", name: "Replicate", endpoints: 11, region: "global", freeTier: "credits" },
  { id: "gemini-proxy", name: "Gemini Proxy", endpoints: 5, region: "edge", freeTier: "community" },
  { id: "qwen", name: "Alibaba Qwen", endpoints: 12, region: "ap-south", freeTier: "dashscope trial" },
  { id: "deepseek", name: "DeepSeek", endpoints: 9, region: "ap-east", freeTier: "credits" },
  { id: "moonshot", name: "Moonshot", endpoints: 8, region: "ap-east", freeTier: "trial" },
  { id: "zhipu", name: "Zhipu GLM", endpoints: 9, region: "ap-east", freeTier: "free tier" },
  { id: "baidu", name: "Baidu ERNIE", endpoints: 6, region: "ap-east", freeTier: "trial" },
  { id: "alibaba", name: "Alibaba ModelStudio", endpoints: 11, region: "ap-south", freeTier: "quota" },
  { id: "xai", name: "xAI", endpoints: 11, region: "us-east", freeTier: "credits" },
];

/** 635 endpoints over 36 providers — asserted in the unit tests. */
export const POOL_ENDPOINTS = PROVIDERS.reduce((sum, p) => sum + p.endpoints, 0);
export const POOL_PROVIDERS = PROVIDERS.length;

/* ==================================================================== */
/* Vault seed — masked placeholders, no secrets in the bundle            */
/* ==================================================================== */
export const SEED_KEYS: FreeLLMProviderKey[] = [
  { providerId: "google", name: "Google Gemini", keyMasked: "AIza••••••••7f21", status: "ACTIVE" },
  { providerId: "groq", name: "Groq", keyMasked: "gsk_••••••••c4e9", status: "ACTIVE" },
  { providerId: "mistral", name: "Mistral", keyMasked: "mis_••••••••01ab", status: "ACTIVE" },
  { providerId: "cerebras", name: "Cerebras", keyMasked: "csk_••••••••9d30", status: "STANDBY" },
  { providerId: "openrouter", name: "OpenRouter", keyMasked: "sk-or-••••••••5b7c", status: "ACTIVE" },
  { providerId: "nvidia", name: "NVIDIA", keyMasked: "nvapi-••••••••22f0", status: "STANDBY" },
  { providerId: "cohere", name: "Cohere", keyMasked: "co-••••••••8a11", status: "LIMIT_REACHED" },
  { providerId: "huggingface", name: "HuggingFace", keyMasked: "hf_••••••••d7b2", status: "STANDBY" },
];

/* ==================================================================== */
/* Candidate models (demo scores)                                        */
/* ==================================================================== */
const candidate = (
  id: string,
  name: string,
  provider: string,
  reliability: number,
  speed: number,
  intelligence: number,
  status: FreeLLMModelCandidate["status"] = "READY",
): FreeLLMModelCandidate => ({
  id,
  name,
  provider,
  reliability,
  speed,
  intelligence,
  compositeScore: 0, // computed by rankCandidates()
  status,
});

export const SEED_CANDIDATES: FreeLLMModelCandidate[] = [
  candidate("gemini-2.5-flash", "Gemini 2.5 Flash", "Google Gemini", 95, 94, 82, "ACTIVE"),
  candidate("gpt-oss-120b", "GPT-OSS 120B", "Groq", 90, 98, 84),
  candidate("deepseek-v4-flash", "DeepSeek V4 Flash", "DeepSeek", 86, 89, 88),
  candidate("mistral-large-3", "Mistral Large 3", "Mistral", 89, 80, 87),
  candidate("grok-4.1-fast", "Grok 4.1 Fast", "xAI", 82, 92, 85),
  candidate("llama-4-maverick", "Llama 4 Maverick", "Groq", 87, 95, 76),
  candidate("qwen3-235b", "Qwen3 235B", "Alibaba Qwen", 84, 78, 86),
  candidate("kimi-k2", "Kimi K2", "Moonshot", 80, 74, 88),
  candidate("glm-4.6", "GLM-4.6", "Zhipu GLM", 83, 81, 82),
  candidate("command-r-plus", "Command R+", "Cohere", 79, 76, 74, "LIMIT_REACHED"),
  candidate("nemotron-ultra", "Nemotron Ultra", "NVIDIA NIM", 85, 83, 80),
  candidate("phi-4-reasoning", "Phi-4 Reasoning", "OpenRouter", 78, 88, 79),
  candidate("gemma-3-27b", "Gemma 3 27B", "Google Gemini", 88, 90, 71),
  candidate("cerebras-llama-70b", "Llama 3.3 70B", "Cerebras", 81, 99, 69),
  candidate("sonar-pro", "Sonar Pro", "Perplexity", 76, 85, 78),
  candidate("hf-zephyr-141b", "Zephyr 141B", "HuggingFace", 72, 70, 68),
];

/* ==================================================================== */
/* The graph as it boots                                                 */
/* ==================================================================== */
export interface NodeSeed {
  id: string;
  label: string;
  category: NodeCategory;
  angle: number; // radians, 0 = right, clockwise
  latencyMs: number;
  load: number;
  provider?: string;
}

/**
 * Eight limbs, one per 45° slice. Store angles, not x/y: the canvas maps them
 * onto the ring at whatever size the viewport happens to be. The seed angles
 * are deliberately uneven by a few degrees so the ring reads as grown rather
 * than generated, but every pair stays ≥ 0.70 rad apart so cards never collide.
 */
const SEED_ARC = [-Math.PI / 2, -0.80, -0.06, 0.74, 1.50, 2.30, 3.10, 3.92];

export const SEED_NODES: NodeSeed[] = [
  { id: "node-router", label: "FreeLLM Router", category: "FREELLM_ROUTER", angle: SEED_ARC[0], latencyMs: 42, load: 0.36, provider: "Gemini 2.5 Flash" },
  { id: "node-mcp", label: "MCP Bridge", category: "MCP_WORKER", angle: SEED_ARC[1], latencyMs: 61, load: 0.28, provider: "GPT-OSS 120B" },
  { id: "node-sandbox", label: "Execution Sandbox", category: "SANDBOX", angle: SEED_ARC[2], latencyMs: 118, load: 0.12 },
  { id: "node-tasks", label: "Task Router", category: "ORCHESTRATOR", angle: SEED_ARC[3], latencyMs: 37, load: 0.31 },
  { id: "node-news", label: "News Stream", category: "DATA_STREAM", angle: SEED_ARC[4], latencyMs: 88, load: 0.19 },
  { id: "node-market", label: "Market Stream", category: "DATA_STREAM", angle: SEED_ARC[5], latencyMs: 31, load: 0.66 },
  { id: "node-memory", label: "Memory Bank", category: "MEMORY", angle: SEED_ARC[6], latencyMs: 23, load: 0.44 },
  { id: "node-inference", label: "Inference Engine", category: "INFERENCE", angle: SEED_ARC[7], latencyMs: 74, load: 0.58, provider: "Mistral Large 3" },
];

export const PRIMARY_ENGINES = [
  { id: "claude-sonnet", label: "Claude Code / Sonnet", detail: "primary endpoint · subscription" },
  { id: "apollo-local", label: "Apollo-Hermes-Local", detail: "local weights · no network" },
  { id: "ollama", label: "Ollama / GGUF", detail: "llama.cpp backend" },
  { id: "custom-onnx", label: "Custom ONNX", detail: "bring your own runtime" },
] as const;

export const MCP_SERVERS = [
  { id: "tvremix", label: "tvremix", detail: "market data · 12 tools", on: true },
  { id: "filesystem", label: "filesystem", detail: "read-only workspace jail", on: true },
  { id: "playwright", label: "playwright", detail: "browser automation", on: false },
  { id: "neu-limb", label: "neu-limb-bridge", detail: "orchestrator limbs", on: true },
] as const;
