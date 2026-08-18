import type { AgentRegistryEntry, ModelManifest } from "@/lib/manifest-types";
import {
  mockAgents,
  mockMetrics,
  mockPolicies,
  googleCloudAgentRegistry,
  type MockAgent,
  type MockMetric,
} from "@/data/mock-orchestrator";

const agentColorMap: Record<string, MockAgent["color"]> = {
  orchestrator: "cyan",
  cartographer: "violet",
  "c-reviewer": "orange",
  "python-tester": "blue",
  "quant-auditor": "pink",
  sandbox: "red",
  "ui-designer": "violet",
  "ci-runner": "green",
  "review-synth": "amber",
  memory: "cyan",
  cody: "amber",
};

const agentInitials: Record<string, string> = {
  orchestrator: "AT",
  cartographer: "MP",
  "c-reviewer": "VC",
  "python-tester": "PY",
  "quant-auditor": "DL",
  sandbox: "AG",
  "ui-designer": "NV",
  "ci-runner": "FG",
  "review-synth": "SC",
  memory: "EC",
  cody: "CD",
};

const agentShortNames: Record<string, string> = {
  orchestrator: "Atlas",
  cartographer: "Maple",
  "c-reviewer": "Vector",
  "python-tester": "Pyra",
  "quant-auditor": "Delta",
  sandbox: "Aegis",
  "ui-designer": "Nova",
  "ci-runner": "Forge",
  "review-synth": "Scribe",
  memory: "Echo",
  cody: "Cody",
};

export function applyCodyLiveStatus(agents: MockAgent[], codyStats: import("@/lib/manifest-types").CodyStats | null): MockAgent[] {
  if (!codyStats) return agents;
  return agents.map((agent) => {
    if (agent.id !== "cody") return agent;
    const load = Math.min(100, Math.max(8, Math.round(codyStats.nioTasksTotal % 100)));
    return {
      ...agent,
      status: codyStats.online ? "working" : "idle",
      load: codyStats.online ? load : 0,
      lastAction: codyStats.online
        ? `Telegram live · ${codyStats.messagesTotal} msgs · ${codyStats.nioTasksSuccess} NIO ok`
        : "Offline — run python telegram_notify.py serve",
      model: codyStats.online ? "NIO · Telegram bridge" : agent.model,
    };
  });
}

function formatModelLabel(resolved: AgentRegistryEntry["resolvedModel"]): string {
  return `${resolved.model_id} (${resolved.tier} · ${resolved.provider})`;
}

export function mapRegistryToAgents(registry: AgentRegistryEntry[]): MockAgent[] {
  const fallback = Object.fromEntries(mockAgents.map((a) => [a.id, a]));

  return registry.map((entry) => {
    const base = fallback[entry.agentId];
    const color = base?.color ?? "cyan";
    return {
      id: entry.agentId,
      name: agentShortNames[entry.agentId] ?? entry.displayName.split(" - ")[0] ?? entry.agentId,
      initials: agentInitials[entry.agentId] ?? entry.agentId.slice(0, 2).toUpperCase(),
      role: entry.displayName.includes(" - ") ? entry.displayName.split(" - ")[1]! : entry.role,
      domain: base?.domain ?? "NIO Middleware",
      model: formatModelLabel(entry.resolvedModel),
      runtime: `NIO · ${entry.modelTier} tier`,
      serviceAccount: base?.serviceAccount ?? `nio-${entry.agentId}@local`,
      status: base?.status ?? "ready",
      load: base?.load ?? 20,
      color,
      tools: base?.tools ?? [entry.resolvedModel.provider],
      lastAction: base?.lastAction ?? `Resolved via manifest (${entry.role})`,
      reliability: base?.reliability ?? 97,
    };
  });
}

export function mapRegistryToGoogleCloudEntries(registry: AgentRegistryEntry[]) {
  return registry.map((entry) => ({
    agentId: entry.agentId,
    role: entry.displayName,
    llmModel: formatModelLabel(entry.resolvedModel),
    contextWindow: entry.modelTier === "frontier" ? "128k+" : "64k",
    runtime: "Vertex AI Agent Engine" as const,
    serviceAccount: `nio-${entry.agentId}@local.iam.gserviceaccount.com`,
    allowedGoogleCloudServices: ["NIO Middleware", entry.resolvedModel.provider],
  }));
}

export function buildMetricsFromTelemetry(
  events: Array<{ latencyMs?: number; isComplex: boolean }>,
  budget?: { dailySpendUsd: number; dailyBudgetUsd: number },
): MockMetric[] {
  const latencies = events.map((e) => e.latencyMs ?? 0).filter((n) => n > 0);
  const avgLatency = latencies.length ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : 0;
  const complexRate = events.length
    ? Math.round((events.filter((e) => e.isComplex).length / events.length) * 100)
    : 0;

  return [
    {
      label: "Active workstreams",
      value: String(Math.min(events.length, 9)),
      delta: events.length > 0 ? "+live" : "—",
      direction: "up" as const,
      caption: "From NIO telemetry stream",
    },
    {
      label: "Mean latency",
      value: avgLatency ? `${avgLatency}ms` : "—",
      delta: latencies.length ? "telemetry" : "—",
      direction: "up" as const,
      caption: "Last 20 task events",
    },
    {
      label: "Complex workflows",
      value: `${complexRate}%`,
      delta: events.length ? "classified" : "—",
      direction: "up" as const,
      caption: "Urgency-wrapped share",
    },
    {
      label: "Daily model spend",
      value: budget ? `$${budget.dailySpendUsd.toFixed(4)}` : "—",
      delta: budget ? `/ $${budget.dailyBudgetUsd}` : "—",
      direction: "up" as const,
      caption: "Manifest budget tracker",
    },
  ];
}

export function buildPoliciesFromManifest(manifest: ModelManifest) {
  return [
    {
      id: "daily-budget",
      label: "Daily model budget",
      description: `Clamp to free tier when daily spend exceeds $${manifest.defaults.cost_budget_usd_per_day} (${manifest.defaults.on_daily_budget_exceeded}).`,
      enabled: true,
      icon: "key" as const,
    },
    {
      id: "swarm-budget",
      label: "Swarm cost ceiling",
      description: `Each swarm wave is capped at $${manifest.defaults.cost_budget_usd_per_swarm} estimated input cost.`,
      enabled: true,
      icon: "container" as const,
    },
    ...mockPolicies.filter((p) => !p.id.startsWith("gcp-")),
  ];
}

export { mockAgents as fallbackAgents };
