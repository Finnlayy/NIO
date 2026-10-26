"use client";

import { create } from "zustand";
import {
  NODE_CATEGORY_STYLE,
  POOL_ENDPOINTS,
  POOL_PROVIDERS,
  SEED_CANDIDATES,
  SEED_KEYS,
  SEED_NODES,
} from "./catalog";
import { runSandboxCommand, requestSynthesis } from "./client";
import {
  COMMANDS,
  coerceConfigValue,
  parseCommand,
  type ParsedCommand,
} from "./commands";
import {
  activeModelOf,
  consumeQuota,
  failover,
  initialRouterState,
  restorePrimary,
  setQuota as setRouterQuota,
  shouldFailover,
  type RouterState,
} from "./engine";
import {
  angleOf,
  hexToRgba,
  mulberry32,
  radialPoint,
  shortId,
  widestGapAngle,
} from "./graph";
import {
  DEFAULT_WEIGHTS,
  formatRouterTable,
  rankCandidates,
  routerSnapshot,
  type Weights,
} from "./routing";
import type {
  ActiveTask,
  ApolloConfiguration,
  CommandResult,
  Impulse,
  NioNode,
  NodeCategory,
  NodeState,
  OrbState,
  RouterSnapshot,
  TaskStep,
  TerminalLogEntry,
  TerminalMode,
  Vesicle,
} from "./types";

/* ==================================================================== */
/* Types                                                                 */
/* ==================================================================== */

export type LogEntry = TerminalLogEntry & {
  simulated?: boolean;
  detail?: string;
  data?: Record<string, unknown>;
};

const MAX_ENTRIES = 400;

export interface ApolloStore {
  config: ApolloConfiguration;
  router: RouterState;
  nodes: NioNode[];
  vesicles: Vesicle[];
  impulses: Impulse[];
  orbState: OrbState;
  orbSince: number;
  flare: { angle: number; startedAt: number } | null;
  task: ActiveTask | null;
  entries: LogEntry[];
  deckOpen: boolean;
  terminalOpen: boolean;
  terminalMode: TerminalMode;
  busy: boolean;
  bootAt: number;

  /* log */
  log: (entry: Omit<LogEntry, "id" | "timestamp">) => LogEntry;

  /* graph */
  spawnNode: (type: NodeCategory, name: string, options?: { announce?: boolean }) => NioNode | null;
  dispatch: (nodeId: string, payload: Record<string, unknown>) => boolean;
  simulateFailover: (reason?: string) => boolean;
  restorePrimary: () => void;

  /* routing / config */
  setWeights: (weights: Partial<Weights>) => void;
  setQuota: (percent: number) => void;
  applyConfig: (next: ApolloConfiguration) => boolean;
  toggleProvider: (providerId: string) => void;

  /* terminal */
  prompt: (text: string) => Promise<void>;
  runCommand: (text: string) => Promise<CommandResult>;
  setDeckOpen: (open: boolean) => void;
  setTerminalOpen: (open: boolean) => void;
  setTerminalMode: (mode: TerminalMode) => void;
  clearTerminal: () => void;
  snapshot: () => RouterSnapshot;
}

/* ==================================================================== */
/* Helpers                                                               */
/* ==================================================================== */

const timers = new Set<ReturnType<typeof setTimeout>>();

function later(ms: number, fn: () => void): void {
  const id = setTimeout(() => {
    timers.delete(id);
    try {
      fn();
    } catch (error) {
      console.error("[apollo] timer failed", error);
    }
  }, ms);
  timers.add(id);
  if (timers.size > 400) {
    const oldest = timers.values().next().value;
    if (oldest !== undefined) {
      clearTimeout(oldest);
      timers.delete(oldest);
    }
  }
}

const stamp = () => new Date().toISOString().slice(11, 23);
let counter = 0;
const id = (prefix: string) => `${prefix}-${(++counter).toString(36)}${shortId()}`;

export const DEFAULT_CONFIG: ApolloConfiguration = {
  primaryModel: "Claude Sonnet 4.5",
  primaryQuotaPercent: 82,
  failoverThresholdPercent: 0,
  temperature: 0.4,
  maxTokens: 32_000,
  executionPolicy: "AUTONOMOUS",
  allowDynamicNodeSpawn: true,
  allowAppMutation: true,
  allowSandboxShell: true,
  freeLLMRouting: {
    enabled: true,
    endpointUrl: "",
    weights: { ...DEFAULT_WEIGHTS },
    enableContextHandoffNote: true,
    providers: SEED_KEYS.map((key) => ({ ...key })),
    fallbackChain: SEED_CANDIDATES.map((candidate) => ({ ...candidate })),
  },
  activeMcpServers: ["tvremix", "filesystem", "neu-limb"],
  systemDirective:
    "Operate as NIO's Apollo core: decompose the objective, dispatch only to nodes that can produce evidence, keep the context handoff note under 900 characters, and synthesise results instead of opinions.",
};

const INITIAL_NODES: NioNode[] = SEED_NODES.map((seed) => ({
  id: seed.id,
  label: seed.label,
  category: seed.category,
  state: "IDLE",
  position: radialPoint(seed.angle),
  metrics: { latencyMs: seed.latencyMs, load: seed.load, activeProvider: seed.provider },
  lastOutput: undefined,
}));

/* -- prompt heuristics ------------------------------------------------- */
const ROUTES: Array<{ category: NodeCategory; pattern: RegExp }> = [
  { category: "MEMORY", pattern: /memory|recall|remember|context|history|handoff/i },
  { category: "SANDBOX", pattern: /sandbox|exec|build|compile|test|run\b|shell/i },
  { category: "DATA_STREAM", pattern: /market|news|stream|fetch|http|price|feed|data/i },
  { category: "FREELLM_ROUTER", pattern: /router|provider|quota|model|failover|token|llm/i },
  { category: "MCP_WORKER", pattern: /mcp|tool|browser|playwright|scrape|search/i },
];

export function routeFor(prompt: string): NodeCategory {
  for (const route of ROUTES) if (route.pattern.test(prompt)) return route.category;
  return "INFERENCE";
}

function pickNode(nodes: readonly NioNode[], category: NodeCategory): NioNode | null {
  const candidates = nodes.filter((n) => n.state !== "LYMP_SPAWNING");
  return candidates.find((n) => n.category === category) ?? candidates.find((n) => n.category === "INFERENCE") ?? candidates[0] ?? null;
}

/** Deterministic-ish simulated answer; labelled SIM in the terminal. */
export function simulatedSynthesis(input: {
  prompt: string;
  node: string;
  model: string;
  latencyMs: number;
  failovers: number;
}): string {
  const subject = input.prompt.replace(/\s+/g, " ").trim().slice(0, 140);
  const lines = [
    `Routed "${subject}" through ${input.node} on ${input.model} (${input.latencyMs} ms).`,
    `Result: one action plan, three checks, no side effects committed — the node returned evidence, not a promise.`,
    input.failovers > 0
      ? `This answer survived ${input.failovers} provider handoff${input.failovers === 1 ? "" : "s"}; the context note travelled with it.`
      : `Primary quota is holding; the FreeLLMAPI pool stayed on standby.`,
    `Next: dispatch \`/dispatch\` with a narrower payload, or open the deck to change the routing weights.`,
  ];
  return lines.join(" ");
}

function preview(value: unknown, max = 220): string {
  let text: string;
  try {
    text = typeof value === "string" ? value : JSON.stringify(value);
  } catch {
    text = String(value);
  }
  text = text ?? "";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

/* ==================================================================== */
/* Store                                                                 */
/* ==================================================================== */

export const useApolloStore = create<ApolloStore>()((set, get) => {
  const push = (draft: Omit<LogEntry, "id" | "timestamp">): LogEntry => {
    const entry: LogEntry = { ...draft, id: id("log"), timestamp: stamp() };
    set((state) => ({ entries: [...state.entries.slice(-(MAX_ENTRIES - 1)), entry] }));
    return entry;
  };

  const setOrb = (state: OrbState, holdMs = 0) => {
    const since = Date.now();
    set({ orbState: state, orbSince: since });
    if (holdMs > 0) {
      later(holdMs, () => {
        if (get().orbSince === since) set({ orbState: "IDLE" });
      });
    }
  };

  const impulse = (
    nodeId: string,
    kind: Impulse["kind"],
    direction: Impulse["direction"],
    durationMs: number,
    label?: string,
    payload?: Record<string, unknown>,
  ) => {
    const packet: Impulse = {
      id: id("imp"),
      nodeId,
      kind,
      direction,
      startedAt: Date.now(),
      durationMs,
      label,
      payload,
    };
    set((state) => ({ impulses: [...state.impulses.slice(-24), packet] }));
    later(durationMs + 120, () => {
      set((state) => ({ impulses: state.impulses.filter((p) => p.id !== packet.id) }));
    });
    return packet;
  };

  const setNode = (nodeId: string, patch: Partial<NioNode>) => {
    set((state) => ({
      nodes: state.nodes.map((node) => (node.id === nodeId ? { ...node, ...patch } : node)),
    }));
  };

  const setNodeState = (nodeId: string, nodeState: NodeState) => setNode(nodeId, { state: nodeState });

  /** Position of a node in unit-ellipse space, for flare angles. */
  const angleTo = (nodeId: string) => {
    const node = get().nodes.find((n) => n.id === nodeId);
    if (!node) return 0;
    return angleOf({ x: 0, y: 0 }, node.position);
  };

  const runFailover = (reason?: string): boolean => {
    const state = get();
    if (!state.config.freeLLMRouting.enabled) {
      push({
        origin: "FREELLM_ROUTER",
        level: "WARN",
        message: "Failover requested but FreeLLMAPI routing is disabled in the deck.",
      });
      return false;
    }
    const outcome = failover(state.router, {
      weights: state.config.freeLLMRouting.weights,
      task: state.task,
      reason,
      directive: state.config.systemDirective,
      handoffNote: state.config.freeLLMRouting.enableContextHandoffNote,
    });
    if (!outcome.switched || !outcome.to) {
      set({ router: outcome.state });
      push({
        origin: "FREELLM_ROUTER",
        level: "ERROR",
        message: `Failover failed: ${outcome.reason}. No free candidate left — the pool is exhausted.`,
      });
      setOrb("ERROR", 2600);
      return false;
    }

    set({ router: outcome.state });
    setOrb("FAILOVER_SWITCH", 2000);
    push({
      origin: "FREELLM_ROUTER",
      level: "FAILOVER",
      message: `Primary quota exhausted (0% · 429). Hot-swapping ${outcome.from.name} → ${outcome.to.name} (${outcome.to.provider}).`,
      activeModel: outcome.to.name,
      data: {
        from: outcome.from,
        to: outcome.to,
        reason: outcome.reason,
        failoverCount: outcome.state.failoverCount,
      },
    });
    if (outcome.note) {
      push({
        origin: "FREELLM_ROUTER",
        level: "FAILOVER",
        message: `Context handoff note attached (${outcome.note.length} chars).`,
        activeModel: outcome.to.name,
        handoffNote: outcome.note,
      });
    }

    const routerNode = get().nodes.find((n) => n.category === "FREELLM_ROUTER");
    if (routerNode) {
      impulse(routerNode.id, "failover", "orbit-to-node", 1500, "context handoff");
      setNodeState(routerNode.id, "PROCESSING");
      later(700, () => {
        setNode(routerNode.id, {
          state: "COMPLETED",
          metrics: { ...(routerNode.metrics ?? { latencyMs: 0, load: 0 }), activeProvider: outcome.to?.name },
          lastOutput: { mode: "FAILOVER", candidate: outcome.to?.id },
        });
      });
      later(2200, () => setNodeState(routerNode.id, "IDLE"));
    }
    later(2000, () => setOrb("IDLE"));
    return true;
  };

  return {
    config: DEFAULT_CONFIG,
    router: initialRouterState(DEFAULT_CONFIG.primaryModel, DEFAULT_CONFIG.freeLLMRouting.fallbackChain, 82),
    nodes: INITIAL_NODES,
    vesicles: [],
    impulses: [],
    orbState: "IDLE",
    orbSince: Date.now(),
    flare: null,
    task: null,
    entries: [],
    deckOpen: false,
    terminalOpen: false,
    terminalMode: "unified",
    busy: false,
    bootAt: Date.now(),

    log: push,

    spawnNode: (type, name, options) => {
      const state = get();
      if (!state.config.allowDynamicNodeSpawn) {
        push({
          origin: "NIO_CORE",
          level: "WARN",
          message: "Spawn blocked: 'Allow dynamic Lymp node spawning' is off in the deck.",
        });
        return null;
      }
      const angle = widestGapAngle(state.nodes.map((node) => angleOf({ x: 0, y: 0 }, node.position)));
      const position = radialPoint(angle);
      const node: NioNode = {
        id: id(`node-${type.slice(0, 5).toLowerCase()}`),
        label: name,
        category: type,
        state: "LYMP_SPAWNING",
        position,
        metrics: { latencyMs: 0, load: 0 },
      };
      const duration = 1250;
      const vesicle: Vesicle = {
        id: id("ves"),
        nodeId: node.id,
        from: { x: 0, y: 0 },
        to: position,
        startedAt: Date.now(),
        durationMs: duration,
        hue: NODE_CATEGORY_STYLE[type].color,
      };

      set({
        nodes: [...state.nodes, node],
        vesicles: [...state.vesicles, vesicle],
      });
      if (options?.announce !== false) {
        push({
          origin: "NIO_CORE",
          level: "DISPATCH",
          message: `LYMP mitosis · ${NODE_CATEGORY_STYLE[type].label} "${name}" budding from the Apollo membrane.`,
          data: { nodeId: node.id, category: type, angle: Number(angle.toFixed(3)) },
        });
      }
      setOrb("DISPATCHING", 900);
      set({ flare: { angle, startedAt: Date.now() } });

      later(duration, () => {
        set((s) => ({ vesicles: s.vesicles.filter((v) => v.id !== vesicle.id) }));
        const latency = 24 + Math.round(mulberry32(counter + 7)() * 90);
        setNode(node.id, {
          state: "IDLE",
          metrics: { latencyMs: latency, load: 0.04 + mulberry32(counter + 11)() * 0.2 },
        });
        impulse(node.id, "handshake", "node-to-orbit", 900, "handshake");
        push({
          origin: "NIO_CORE",
          level: "INFO",
          message: `Crystallised "${name}" · axon locked · handshake ${latency} ms.`,
          data: { nodeId: node.id },
        });
      });
      return node;
    },

    dispatch: (nodeId, payload) => {
      const node = get().nodes.find((n) => n.id === nodeId);
      if (!node) {
        push({ origin: "NIO_CORE", level: "ERROR", message: `Dispatch failed: no node '${nodeId}'.` });
        setOrb("ERROR", 1600);
        return false;
      }
      if (node.state === "LYMP_SPAWNING") {
        push({
          origin: "NIO_CORE",
          level: "WARN",
          message: `Node "${node.label}" is still crystallising; dispatch queued after mitosis.`,
        });
      }
      const angle = angleTo(nodeId);
      set({ flare: { angle, startedAt: Date.now() } });
      setOrb("DISPATCHING", 1200);
      impulse(nodeId, "outbound", "orbit-to-node", 950, "tool call", payload);
      setNodeState(nodeId, "PROCESSING");
      push({
        origin: "MCP_SANDBOX",
        level: "DISPATCH",
        message: `[MCP_TOOL_CALL] Apollo → ${node.label}`,
        activeModel: activeModelOf(get().router).name,
        data: { nodeId, category: node.category, payload },
      });

      later(950, () => {
        if (!get().nodes.some((n) => n.id === nodeId)) return;
        setNodeState(nodeId, "STREAMING");
        push({
          origin: "NIO_CORE",
          level: "INFO",
          message: `[NODE_DISPATCH] ${node.label} streaming partial output…`,
          data: { nodeId },
        });
      });
      later(1750, () => {
        if (!get().nodes.some((n) => n.id === nodeId)) return;
        const latency = 40 + Math.round(mulberry32(counter + 3)() * 160);
        setNode(nodeId, {
          state: "COMPLETED",
          lastOutput: { ok: true, payload, latencyMs: latency },
          metrics: {
            latencyMs: latency,
            load: 0.2 + mulberry32(counter + 5)() * 0.6,
            activeProvider: activeModelOf(get().router).name,
          },
        });
        impulse(nodeId, "inbound", "node-to-orbit", 900, "result", payload);
        setOrb("SYNTHESIZING", 1600);
        push({
          origin: "MCP_SANDBOX",
          level: "INFO",
          message: `${node.label} returned ${preview(payload, 80)} · ${latency} ms`,
          data: { nodeId, latencyMs: latency },
        });
      });
      later(3200, () => {
        const current = get().nodes.find((n) => n.id === nodeId);
        if (current?.state === "COMPLETED") setNodeState(nodeId, "IDLE");
      });
      return true;
    },

    simulateFailover: (reason) => runFailover(reason),

    restorePrimary: () => {
      const state = get();
      const next = restorePrimary(state.router, 100);
      set({
        router: next,
        config: { ...state.config, primaryQuotaPercent: 100 },
      });
      push({
        origin: "FREELLM_ROUTER",
        level: "INFO",
        message: `Primary quota reset to 100% · ${next.primaryModel} is back in front of the pool.`,
      });
    },

    setWeights: (patch) => {
      const state = get();
      const weights = { ...state.config.freeLLMRouting.weights, ...patch };
      const chain = rankCandidates(state.config.freeLLMRouting.fallbackChain, weights);
      set({
        config: {
          ...state.config,
          freeLLMRouting: { ...state.config.freeLLMRouting, weights, fallbackChain: chain },
        },
      });
    },

    setQuota: (percent) => {
      const state = get();
      set({
        router: setRouterQuota(state.router, percent),
        config: { ...state.config, primaryQuotaPercent: percent },
      });
    },

    applyConfig: (next) => {
      const state = get();
      if (!state.config.allowAppMutation) {
        push({
          origin: "NIO_CORE",
          level: "WARN",
          message: "Hot-reload refused: 'Allow Apollo to mutate NIO UI state' is off.",
        });
        return false;
      }
      const chain = rankCandidates(next.freeLLMRouting.fallbackChain, next.freeLLMRouting.weights);
      const router: RouterState = {
        ...state.router,
        primaryModel: next.primaryModel,
        primaryQuotaPercent: next.primaryQuotaPercent,
        chain,
        mode: state.router.mode === "PRIMARY" ? "PRIMARY" : state.router.mode,
      };
      set({
        config: { ...next, freeLLMRouting: { ...next.freeLLMRouting, fallbackChain: chain } },
        router,
      });
      setOrb("SYNTHESIZING", 1400);
      push({
        origin: "APOLLO",
        level: "INFO",
        message: `Configuration applied · primary ${next.primaryModel} · temperature ${next.temperature.toFixed(2)} · policy ${next.executionPolicy} · routing ${next.freeLLMRouting.enabled ? "on" : "off"}.`,
        activeModel: activeModelOf(router).name,
        data: { weights: next.freeLLMRouting.weights, threshold: next.failoverThresholdPercent },
      });
      return true;
    },

    toggleProvider: (providerId) => {
      const state = get();
      const providers = state.config.freeLLMRouting.providers.map((provider) =>
        provider.providerId === providerId
          ? {
              ...provider,
              status:
                provider.status === "ACTIVE"
                  ? ("STANDBY" as const)
                  : provider.status === "LIMIT_REACHED"
                    ? ("ACTIVE" as const)
                    : ("ACTIVE" as const),
            }
          : provider,
      );
      set({
        config: {
          ...state.config,
          freeLLMRouting: { ...state.config.freeLLMRouting, providers },
        },
      });
      const changed = providers.find((p) => p.providerId === providerId);
      push({
        origin: "FREELLM_ROUTER",
        level: "INFO",
        message: `Vault: ${changed?.name ?? providerId} → ${changed?.status ?? "unknown"}.`,
      });
    },

    prompt: async (text) => {
      const promptText = text.trim();
      if (!promptText || get().busy) return;
      const state = get();
      set({ busy: true });
      push({ origin: "USER", level: "CHAT", message: promptText, activeModel: activeModelOf(state.router).name });

      const category = routeFor(promptText);
      const target = pickNode(get().nodes, category);
      const steps: TaskStep[] = [
        { id: "parse", label: "Parse intent & load directive", status: "RUNNING" },
        { id: "route", label: `Route to ${target ? target.label : "inference engine"}`, status: "PENDING", nodeId: target?.id },
        { id: "execute", label: "Execute on node", status: "PENDING", nodeId: target?.id },
        { id: "handoff", label: "Failover check (FreeLLMAPI)", status: "PENDING" },
        { id: "synthesise", label: "Synthesise answer", status: "PENDING" },
      ];
      const task: ActiveTask = {
        id: id("task"),
        label: promptText.slice(0, 72),
        prompt: promptText,
        startedAt: Date.now(),
        steps,
        completed: [],
        pending: steps.slice(1).map((step) => step.label),
      };
      set({ task });
      setOrb("THINKING");

      const advance = (stepId: string, status: TaskStep["status"], done?: string) => {
        set((s) => {
          if (!s.task) return {};
          const nextSteps = s.task.steps.map((step) => (step.id === stepId ? { ...step, status } : step));
          const completed = done ? [...s.task.completed, done] : s.task.completed;
          const pending = nextSteps.filter((step) => step.status === "PENDING").map((step) => step.label);
          return { task: { ...s.task, steps: nextSteps, completed, pending } };
        });
      };

      later(160, () => advance("parse", "DONE", steps[0].label));
      later(380, () => {
        advance("route", "DONE", steps[1].label);
        advance("execute", "RUNNING");
        if (target) get().dispatch(target.id, { task: task.id, prompt: promptText, category });
      });

      later(1180, () => {
        const q = get().config;
        const cost = 3.2 + (promptText.length % 7) * 0.4;
        get().setQuota(Math.max(0, get().router.primaryQuotaPercent - cost));
        if (get().router.mode === "PRIMARY" && shouldFailover(get().router, q.failoverThresholdPercent)) {
          advance("handoff", "DONE", steps[3].label);
          runFailover("primary quota exhausted mid-task (HTTP 429)");
        } else {
          advance("handoff", "DONE", steps[3].label);
        }
      });

      later(1500, () => advance("execute", "DONE", steps[2].label));
      later(1900, async () => {
        advance("synthesise", "RUNNING");
        const live = get();
        const model = activeModelOf(live.router);
        const node = target?.label ?? "Inference Engine";
        const latency = 40 + Math.round(mulberry32(counter + 13)() * 180);

        if (live.config.freeLLMRouting.endpointUrl.trim()) {
          const result = await requestSynthesis({
            endpointUrl: live.config.freeLLMRouting.endpointUrl,
            model: model.name,
            messages: [
              { role: "system", content: live.config.systemDirective },
              {
                role: "user",
                content: `${promptText}\n\n[NIO] You are answering through ${node}. Answer in at most 120 words.`,
              },
            ],
            temperature: live.config.temperature,
            maxTokens: Math.min(2000, live.config.maxTokens),
          });
          if (result.ok && result.text.trim()) {
            push({
              origin: "APOLLO",
              level: "CHAT",
              message: result.text.trim(),
              activeModel: model.name,
              data: { provider: result.provider, latencyMs: result.latencyMs, node },
            });
            advance("synthesise", "DONE", steps[4].label);
            finish(live.router.failoverCount);
            return;
          }
          push({
            origin: "NIO_CORE",
            level: "WARN",
            message: `Live endpoint unavailable (${result.error ?? "empty response"}) — falling back to local synthesis.`,
          });
        }

        push({
          origin: "APOLLO",
          level: "CHAT",
          message: simulatedSynthesis({
            prompt: promptText,
            node,
            model: model.name,
            latencyMs: latency,
            failovers: get().router.failoverCount,
          }),
          activeModel: model.name,
          simulated: true,
          data: { node, latencyMs: latency, provider: model.provider },
        });
        advance("synthesise", "DONE", steps[4].label);
        finish(get().router.failoverCount);
      });

      function finish(failovers: number) {
        setOrb("SYNTHESIZING", 1100);
        later(1200, () => {
          set({ busy: false });
          set((s) => (s.task ? { task: { ...s.task, pending: [] } } : {}));
          if (failovers > 0) {
            push({
              origin: "NIO_CORE",
              level: "INFO",
              message: `Task complete · ${failovers} provider handoff${failovers === 1 ? "" : "s"} · context preserved.`,
            });
          }
        });
      }
    },

    runCommand: async (text) => {
      const parsed: ParsedCommand = parseCommand(text);
      const state = get();
      const entries: CommandResult["entries"] = [];
      const emit = (origin: LogEntry["origin"], level: LogEntry["level"], message: string, extra: Partial<LogEntry> = {}) => {
        const entry = push({ origin, level, message, ...extra });
        entries.push({
          origin: entry.origin,
          level: entry.level,
          message: entry.message,
          activeModel: entry.activeModel,
          handoffNote: entry.handoffNote,
        });
      };

      switch (parsed.kind) {
        case "spawn": {
          const node = get().spawnNode(parsed.type, parsed.name);
          return { ok: node !== null, entries, data: node ? { nodeId: node.id } : undefined };
        }
        case "dispatch": {
          const ok = get().dispatch(parsed.nodeId, parsed.payload);
          return { ok, entries, data: { nodeId: parsed.nodeId } };
        }
        case "failover-simulate": {
          const before = get().router;
          const ok = runFailover("operator simulated 429 on the primary endpoint");
          return {
            ok,
            entries,
            data: {
              switched: ok,
              from: activeModelOf(before).name,
              to: activeModelOf(get().router).name,
            },
          };
        }
        case "router-status": {
          const live = get();
          const ranked = rankCandidates(live.config.freeLLMRouting.fallbackChain, live.config.freeLLMRouting.weights);
          emit("FREELLM_ROUTER", "INFO", formatRouterTable(live.config.freeLLMRouting.providers, ranked, live.config.freeLLMRouting.weights), {
            data: { ranked: ranked.slice(0, 8).map((c) => ({ id: c.id, score: c.compositeScore, status: c.status })) },
          });
          return { ok: true, entries, data: { snapshot: get().snapshot() } };
        }
        case "config-set": {
          const key = parsed.key;
          const value = parsed.value;
          const next: ApolloConfiguration = structuredClone(state.config);
          if (key === "temperature") next.temperature = Number(value);
          else if (key === "maxTokens") next.maxTokens = Number(value);
          else if (key === "primaryQuotaPercent") next.primaryQuotaPercent = Number(value);
          else if (key === "primaryModel") next.primaryModel = String(value);
          else if (key === "executionPolicy") next.executionPolicy = String(value) as ApolloConfiguration["executionPolicy"];
          else if (key === "allowDynamicNodeSpawn") next.allowDynamicNodeSpawn = Boolean(value);
          else if (key === "allowAppMutation") next.allowAppMutation = Boolean(value);
          else if (key === "systemDirective") next.systemDirective = String(value);
          const applied = get().applyConfig(next);
          if (key === "primaryQuotaPercent") get().setQuota(Number(value));
          emit(
            applied ? "APOLLO" : "NIO_CORE",
            applied ? "INFO" : "WARN",
            applied ? `config · ${key} = ${parsed.raw || String(value)}` : "config rejected by UI-mutation permission",
            { data: { key, value } },
          );
          return { ok: applied, entries, data: { key, value } };
        }
        case "sandbox-exec": {
          if (!state.config.allowSandboxShell) {
            emit("MCP_SANDBOX", "WARN", "Sandbox shell is disabled in the deck (Permissions → Allow Sandbox Shell execution).");
            return { ok: false, entries };
          }
          emit("MCP_SANDBOX", "DISPATCH", `[MCP_TOOL_CALL] sandbox.exec · ${parsed.command}`);
          const result = await runSandboxCommand(parsed.command);
          const body = result.stdout.trim();
          emit(
            "MCP_SANDBOX",
            result.ok ? "INFO" : "ERROR",
            result.ok
              ? `[${result.mode ?? "jail"}] exit ${result.code}\n${body || "(no output)"}`
              : `sandbox refused: ${result.error ?? "unknown error"}`,
            { data: { command: parsed.command, code: result.code } },
          );
          return { ok: result.ok, entries, data: { code: result.code } };
        }
        case "clear": {
          set({ entries: [] });
          return { ok: true, entries };
        }
        case "help": {
          emit(
            "NIO_CORE",
            "INFO",
            ["Hybrid CLI — deterministic commands", ...COMMANDS.map((c) => `${c.command.padEnd(11)} ${c.detail}`)].join("\n"),
            { data: { commands: COMMANDS.map((c) => c.command) } },
          );
          return { ok: true, entries };
        }
        case "unknown": {
          get()
            .prompt(parsed.input)
            .catch((error: unknown) => {
              push({
                origin: "NIO_CORE",
                level: "ERROR",
                message: `Prompt failed: ${error instanceof Error ? error.message : String(error)}`,
              });
            });
          return { ok: true, entries, data: { routed: "apollo" } };
        }
        case "error": {
          push({
            origin: "NIO_CORE",
            level: "ERROR",
            message: parsed.message,
            detail: parsed.hint,
          });
          entries.push({
            origin: "NIO_CORE",
            level: "ERROR",
            message: parsed.message,
            detail: parsed.hint,
          });
          return { ok: false, entries };
        }
        default: {
          return { ok: false, entries };
        }
      }
    },

    setDeckOpen: (open) => {
      set({ deckOpen: open });
      if (open) setOrb("LISTENING", 0);
      else if (get().orbState === "LISTENING") setOrb("IDLE");
    },

    setTerminalOpen: (open) => {
      set({ terminalOpen: open });
      if (open && get().entries.length === 0) {
        push({
          origin: "NIO_CORE",
          level: "INFO",
          message: `NIO terminal attached · ${POOL_PROVIDERS} providers · ${POOL_ENDPOINTS} endpoints in the FreeLLMAPI pool. Type /help.`,
        });
      }
    },

    setTerminalMode: (mode) => set({ terminalMode: mode }),
    clearTerminal: () => set({ entries: [] }),

    snapshot: () => {
      const live = get();
      const model = activeModelOf(live.router);
      return routerSnapshot({
        primaryModel: live.router.primaryModel,
        primaryQuotaPercent: live.router.primaryQuotaPercent,
        activeModel: model.name,
        activeProvider: model.provider,
        mode: live.router.mode,
        failoverCount: live.router.failoverCount,
        latencyMs: live.nodes.find((n) => n.category === "FREELLM_ROUTER")?.metrics?.latencyMs ?? 42,
        lastHandoffNote: live.router.lastHandoffNote,
      });
    },
  };
});

/* -------------------------------------------------------------------- */
/* Selectors                                                             */
/* -------------------------------------------------------------------- */

export const selectRanked = (state: ApolloStore) =>
  rankCandidates(state.config.freeLLMRouting.fallbackChain, state.config.freeLLMRouting.weights);

export const selectActiveModel = (state: ApolloStore) => activeModelOf(state.router);

export { coerceConfigValue, parseCommand };
