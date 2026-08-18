import { mockAgents, type MockAgent } from "@/data/mock-orchestrator";
import type { AgentRegistryEntry, LimbInstance, LimbTemplate } from "@/lib/manifest-types";

const CORE_MOCK_IDS = new Set(["orchestrator", "sandbox", "memory"]);
const INTERFACE_MOCK_IDS = new Set(["cody"]);

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

const fallbackById = Object.fromEntries(mockAgents.map((a) => [a.id, a]));

function limbStateToStatus(state: LimbInstance["state"]): MockAgent["status"] {
  if (state === "active" || state === "deployed") return "working";
  if (state === "completing" || state === "post-mortem") return "reviewing";
  return "ready";
}

export function mapLimbInstanceToAgent(instance: LimbInstance, template?: LimbTemplate): MockAgent {
  const mockId = instance.mock_id;
  const base = fallbackById[mockId];
  const color = base?.color ?? agentColorMap[mockId] ?? "cyan";
  const shortName = agentShortNames[mockId] ?? instance.display_name.split(" - ")[0] ?? mockId;

  return {
    id: instance.limb_instance_id,
    name: shortName,
    initials: agentInitials[mockId] ?? shortName.slice(0, 2).toUpperCase(),
    role: template?.role ?? base?.role ?? "Task Limb",
    domain: base?.domain ?? "Detachable Limb",
    model: template ? `${template.model_tier} tier · ${template.limb_runtime}` : base?.model ?? "NIO",
    runtime: template?.limb_runtime ?? "cursor_task",
    serviceAccount: base?.serviceAccount ?? `limb-${instance.limb_instance_id}@local`,
    status: limbStateToStatus(instance.state),
    load: instance.state === "active" ? 72 : 35,
    color,
    tools: template?.tools ?? base?.tools ?? [],
    lastAction: `${instance.state} · ${instance.task_id}`,
    reliability: base?.reliability ?? 96,
  };
}

export function buildCanvasAgents(params: {
  registry: AgentRegistryEntry[];
  activeLimbs: LimbInstance[];
  templates: LimbTemplate[];
  codyStats: import("@/lib/manifest-types").CodyStats | null;
}): { canvasAgents: MockAgent[]; coreAgents: MockAgent[]; interfaceAgent: MockAgent | null } {
  const templateById = Object.fromEntries(params.templates.map((t) => [t.template_id, t]));
  const registryById = Object.fromEntries(params.registry.map((e) => [e.agentId, e]));

  const coreAgents = ["orchestrator", "sandbox", "memory"]
    .map((id) => {
      const entry = registryById[id];
      const base = fallbackById[id];
      if (!base) return null;
      return {
        ...base,
        model: entry ? `${entry.resolvedModel.model_id} (${entry.modelTier})` : base.model,
        status: id === "orchestrator" ? ("working" as const) : base.status,
      };
    })
    .filter((a): a is MockAgent => a !== null);

  const limbAgents = params.activeLimbs.map((limb) =>
    mapLimbInstanceToAgent(limb, templateById[limb.template_id]),
  );

  let interfaceAgent: MockAgent | null = fallbackById.cody ?? null;
  if (interfaceAgent && params.codyStats) {
    interfaceAgent = {
      ...interfaceAgent,
      status: params.codyStats.online ? "working" : "idle",
      load: params.codyStats.online ? Math.min(100, params.codyStats.nioTasksTotal % 100) : 0,
      lastAction: params.codyStats.online
        ? `Telegram live · ${params.codyStats.messagesTotal} msgs`
        : interfaceAgent.lastAction,
    };
  }

  const atlas = coreAgents.find((a) => a.id === "orchestrator");
  const canvasAgents = [
    ...(atlas ? [atlas] : []),
    ...limbAgents,
    ...(interfaceAgent ? [interfaceAgent] : []),
  ];

  return { canvasAgents, coreAgents, interfaceAgent };
}

export function isCoreMockId(id: string): boolean {
  return CORE_MOCK_IDS.has(id);
}

export function isInterfaceMockId(id: string): boolean {
  return INTERFACE_MOCK_IDS.has(id);
}

export function mapTemplateToLibraryRow(template: LimbTemplate): MockAgent {
  const base = fallbackById[template.mock_id];
  return {
    id: template.template_id,
    name: agentShortNames[template.mock_id] ?? template.display_name.split(" - ")[0] ?? template.template_id,
    initials: agentInitials[template.mock_id] ?? "LB",
    role: template.role,
    domain: base?.domain ?? "Agent Library",
    model: `${template.model_tier} · ${template.limb_runtime}`,
    runtime: template.limb_runtime,
    serviceAccount: base?.serviceAccount ?? `${template.template_id}@library`,
    status: "idle",
    load: Math.round((template.routing_weight ?? 0.5) * 100),
    color: base?.color ?? "violet",
    tools: template.tools,
    lastAction: template.description ?? "Library template",
    reliability: base?.reliability ?? 95,
  };
}
