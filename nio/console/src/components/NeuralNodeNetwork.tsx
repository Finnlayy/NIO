"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  CircleDot,
  Database,
  GitPullRequest,
  LockKeyhole,
  Network,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
  XCircle,
} from "lucide-react";
import {
  evalMetrics,
  orchestratorAgents,
  sandboxPolicies,
  workflowStates,
  type OrchestratorAgent,
  type WorkflowState,
} from "@/data/orchestrator";

type MemoryEvent = {
  id: number | string;
  agentId: string;
  workflowState: string;
  outcome: string;
  score: number;
  notes: string;
  createdAt: string;
};

type NetworkNode = {
  id: string;
  label: string;
  shortLabel: string;
  kind: "agent" | "system" | "state";
  color: string;
  x: number;
  y: number;
  description: string;
  agent?: OrchestratorAgent;
  workflowState?: WorkflowState;
};

type Edge = {
  from: string;
  to: string;
  label?: string;
  color: string;
  curved?: boolean;
};

const palette: Record<string, { border: string; fill: string; text: string; glow: string; line: string }> = {
  cyan: { border: "#22d3ee", fill: "rgba(6,182,212,0.16)", text: "#a5f3fc", glow: "rgba(34,211,238,0.42)", line: "#22d3ee" },
  blue: { border: "#60a5fa", fill: "rgba(59,130,246,0.16)", text: "#bfdbfe", glow: "rgba(96,165,250,0.4)", line: "#60a5fa" },
  orange: { border: "#fb923c", fill: "rgba(249,115,22,0.16)", text: "#fed7aa", glow: "rgba(251,146,60,0.42)", line: "#fb923c" },
  yellow: { border: "#facc15", fill: "rgba(234,179,8,0.16)", text: "#fef08a", glow: "rgba(250,204,21,0.4)", line: "#facc15" },
  pink: { border: "#f472b6", fill: "rgba(236,72,153,0.16)", text: "#fbcfe8", glow: "rgba(244,114,182,0.4)", line: "#f472b6" },
  red: { border: "#fb7185", fill: "rgba(239,68,68,0.16)", text: "#fecdd3", glow: "rgba(251,113,133,0.42)", line: "#fb7185" },
  purple: { border: "#c084fc", fill: "rgba(139,92,246,0.16)", text: "#e9d5ff", glow: "rgba(192,132,252,0.42)", line: "#c084fc" },
  green: { border: "#4ade80", fill: "rgba(34,197,94,0.16)", text: "#bbf7d0", glow: "rgba(74,222,128,0.42)", line: "#4ade80" },
  indigo: { border: "#818cf8", fill: "rgba(99,102,241,0.16)", text: "#c7d2fe", glow: "rgba(129,140,248,0.42)", line: "#818cf8" },
  teal: { border: "#2dd4bf", fill: "rgba(20,184,166,0.16)", text: "#99f6e4", glow: "rgba(45,212,191,0.42)", line: "#2dd4bf" },
  slate: { border: "#94a3b8", fill: "rgba(100,116,139,0.16)", text: "#e2e8f0", glow: "rgba(148,163,184,0.32)", line: "#94a3b8" },
};

const stateColor: Record<WorkflowState, string> = {
  PLANNING: "blue",
  EXECUTING: "cyan",
  REVIEWING: "purple",
  EVALUATING: "yellow",
  REVISING: "orange",
  DEPLOYING: "green",
  ESCALATED: "red",
};

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const getInitialScores = () => Object.fromEntries(evalMetrics.map((metric) => [metric.key, metric.threshold]));

function createNodes(): NetworkNode[] {
  const agentPositions = [
    [11, 19], [31, 10], [55, 10], [78, 18], [90, 38],
    [89, 68], [69, 88], [43, 90], [19, 76], [8, 52],
  ];
  const agents = orchestratorAgents.map((agent, index) => ({
    id: agent.id,
    label: agent.role,
    shortLabel: agent.role.replace(" Reviewer", "").replace(" Engineer", "").replace(" Orchestrator", ""),
    kind: "agent" as const,
    color: agent.color,
    x: agentPositions[index][0],
    y: agentPositions[index][1],
    description: agent.mission,
    agent,
  }));

  return [
    ...agents,
    {
      id: "neural-core",
      label: "Neural Core",
      shortLabel: "NEURAL\nCORE",
      kind: "system",
      color: "cyan",
      x: 50,
      y: 50,
      description: "Der Supervisor verbindet Agenten, Retrieval-Kontext, Evidence und die State Machine. Er plant, delegiert und erzwingt Gates statt Ergebnisse ungeprüft weiterzugeben.",
    },
    {
      id: "memory-ledger",
      label: "Eval / Memory Ledger",
      shortLabel: "EVAL /\nMEMORY",
      kind: "system",
      color: "teal",
      x: 29,
      y: 54,
      description: "PostgreSQL ist der unveränderliche Evidence Ledger. Ein optionaler Vector-Store-Adapter ruft ähnliche Fehlermuster und erfolgreiche Strategien vor der Planung ab.",
    },
    {
      id: "sandbox-gate",
      label: "Sandbox Policy Gate",
      shortLabel: "SANDBOX\nGATE",
      kind: "system",
      color: "red",
      x: 72,
      y: 54,
      description: "Ephemerer Docker-/gVisor-Runner, deny-by-default Netzwerkzugriff und kurzlebige Credentials. Direkte Produktionsschreibzugriffe sind ausgeschlossen.",
    },
    ...workflowStates.map((state, index) => ({
      id: `state-${state.id}`,
      label: state.label,
      shortLabel: state.label,
      kind: "state" as const,
      color: stateColor[state.id],
      x: 12 + index * 12.7,
      y: 97,
      description: `${state.description} Gate: ${state.gate}`,
      workflowState: state.id,
    })),
  ];
}

const nodes = createNodes();
const nodeById = Object.fromEntries(nodes.map((node) => [node.id, node]));

const agentEdges: Edge[] = orchestratorAgents.map((agent) => ({
  from: agent.id,
  to: "neural-core",
  color: agent.color,
  curved: true,
}));

const flowEdges: Edge[] = [
  { from: "memory-ledger", to: "neural-core", label: "retrieve", color: "teal" },
  { from: "neural-core", to: "sandbox-gate", label: "policy", color: "red" },
  { from: "neural-core", to: "state-PLANNING", color: "blue", curved: true },
  { from: "state-PLANNING", to: "state-EXECUTING", color: "cyan" },
  { from: "state-EXECUTING", to: "state-REVIEWING", color: "purple" },
  { from: "state-REVIEWING", to: "state-EVALUATING", color: "yellow" },
  { from: "state-EVALUATING", to: "state-REVISING", color: "orange" },
  { from: "state-EVALUATING", to: "state-DEPLOYING", color: "green", curved: true },
  { from: "state-REVISING", to: "state-EXECUTING", color: "orange", curved: true },
  { from: "state-EVALUATING", to: "state-ESCALATED", color: "red", curved: true },
  { from: "state-ESCALATED", to: "state-PLANNING", color: "red", curved: true },
  { from: "state-EVALUATING", to: "memory-ledger", label: "learn", color: "teal", curved: true },
];

export default function NeuralNodeNetwork() {
  const [selectedNodeId, setSelectedNodeId] = useState("neural-core");
  const [activeNodeIds, setActiveNodeIds] = useState<string[]>(["neural-core"]);
  const [activeEdgeKeys, setActiveEdgeKeys] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [scores, setScores] = useState<Record<string, number>>(getInitialScores);
  const [result, setResult] = useState<string>("Bereit für eine Evidence-gesteuerte Ausführung.");
  const [events, setEvents] = useState<MemoryEvent[]>([]);
  const [memoryConnected, setMemoryConnected] = useState<"loading" | "connected" | "fallback">("loading");
  const [activePanel, setActivePanel] = useState<"node" | "gates">("node");

  const selectedNode = nodeById[selectedNodeId] ?? nodeById["neural-core"];
  const compositeScore = useMemo(
    () => Math.round(evalMetrics.reduce((sum, metric) => sum + (scores[metric.key] * metric.weight) / 100, 0)),
    [scores],
  );
  const hardGateBlocked = scores.buildIntegrity < 100 || scores.securityPosture < 100;

  useEffect(() => {
    async function getEvents() {
      try {
        const response = await fetch("/api/orchestrator/memory", { cache: "no-store" });
        const data = (await response.json()) as { events?: MemoryEvent[] };
        setEvents(data.events ?? []);
        setMemoryConnected(response.ok ? "connected" : "fallback");
      } catch {
        setMemoryConnected("fallback");
      }
    }
    void getEvents();
  }, []);

  function edgeKey(edge: Edge) {
    return `${edge.from}-${edge.to}`;
  }

  function selectNode(nodeId: string) {
    if (isRunning) return;
    setSelectedNodeId(nodeId);
    setActiveNodeIds(["neural-core", nodeId]);
    setActiveEdgeKeys(
      [...agentEdges, ...flowEdges]
        .filter((edge) => edge.from === nodeId || edge.to === nodeId)
        .map(edgeKey),
    );
    setActivePanel("node");
  }

  async function persistEvent(event: Omit<MemoryEvent, "id" | "createdAt">) {
    try {
      const response = await fetch("/api/orchestrator/memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
      });
      const data = (await response.json()) as { event?: MemoryEvent };
      if (data.event) {
        setEvents((current) => [data.event!, ...current].slice(0, 4));
        setMemoryConnected("connected");
        return;
      }
    } catch {
      // Local fallback preserves the network's feedback behavior during temporary database downtime.
    }
    setEvents((current) => [{ ...event, id: `local-${Date.now()}`, createdAt: new Date().toISOString() }, ...current].slice(0, 4));
    setMemoryConnected("fallback");
  }

  async function runNetwork() {
    if (isRunning) return;
    setIsRunning(true);
    setActivePanel("node");
    setResult("Memory wird abgerufen und ein sicherer Ausführungsplan wird erstellt …");

    const activationPath = [
      "memory-ledger",
      "neural-core",
      "sandbox-gate",
      "state-PLANNING",
      "orchestrator-supervisor",
      "repo-cartographer",
      "state-EXECUTING",
      "c-performance-reviewer",
      "python-test-engineer",
      "quant-domain-auditor",
      "security-sandbox-guardian",
      "ui-systems-designer",
      "ci-evidence-runner",
      "pr-review-synthesizer",
      "state-REVIEWING",
      "memory-eval-curator",
      "state-EVALUATING",
    ];

    for (const nodeId of activationPath) {
      setSelectedNodeId(nodeId);
      setActiveNodeIds((current) => Array.from(new Set([...current.slice(-6), nodeId])));
      setActiveEdgeKeys((current) => {
        const related = [...agentEdges, ...flowEdges]
          .filter((edge) => edge.from === nodeId || edge.to === nodeId)
          .map(edgeKey);
        return Array.from(new Set([...current.slice(-8), ...related]));
      });
      await sleep(260);
    }

    const finalState: WorkflowState = hardGateBlocked ? "ESCALATED" : compositeScore >= 85 ? "DEPLOYING" : "REVISING";
    const finalNode = `state-${finalState}`;
    setSelectedNodeId(finalNode);
    setActiveNodeIds((current) => Array.from(new Set([...current, finalNode, "memory-ledger"])).slice(-8));
    setActiveEdgeKeys((current) => Array.from(new Set([...current, ...flowEdges.filter((edge) => edge.to === finalNode || edge.to === "memory-ledger").map(edgeKey)])).slice(-12));

    const outcome = finalState === "DEPLOYING" ? "passed" : finalState === "REVISING" ? "revised" : "escalated";
    const notes = hardGateBlocked
      ? "Autonomer Lauf gestoppt: Build & Syntax oder Sandbox & Security erfüllt das zwingende 100%-Hard-Gate nicht. Entscheidung an Human Owner eskaliert."
      : finalState === "DEPLOYING"
        ? `Composite Eval Score ${compositeScore}/100. Evidence-Gate bestanden; der CI Runner darf erst nach expliziter menschlicher Release-Freigabe fortfahren.`
        : `Composite Eval Score ${compositeScore}/100 liegt unter 85. Failure Context gespeichert; Supervisor erzeugt ein fokussiertes Revision Work Pack.`;

    await persistEvent({
      agentId: "memory-eval-curator",
      workflowState: finalState,
      outcome,
      score: compositeScore,
      notes,
    });
    setResult(notes);
    setIsRunning(false);
  }

  function renderEdge(edge: Edge) {
    const start = nodeById[edge.from];
    const end = nodeById[edge.to];
    const key = edgeKey(edge);
    const isActive = activeEdgeKeys.includes(key);
    const color = palette[edge.color] ?? palette.slate;
    const x1 = start.x;
    const y1 = start.y;
    const x2 = end.x;
    const y2 = end.y;
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    const curve = edge.curved ? `Q ${midX + (y1 - y2) * 0.12} ${midY + (x2 - x1) * 0.12} ${x2} ${y2}` : `L ${x2} ${y2}`;

    return (
      <g key={key}>
        <path
          d={`M ${x1} ${y1} ${curve}`}
          fill="none"
          stroke={color.line}
          strokeWidth={isActive ? 0.65 : 0.24}
          strokeLinecap="round"
          opacity={isActive ? 0.95 : 0.25}
          className="transition-all duration-500"
        />
        {isActive && (
          <motion.circle
            r="0.9"
            fill={color.line}
            filter="url(#node-glow)"
            initial={{ cx: x1, cy: y1, opacity: 0 }}
            animate={{ cx: [x1, midX, x2], cy: [y1, midY, y2], opacity: [0, 1, 1, 0] }}
            transition={{ duration: 1.25, repeat: Infinity, ease: "linear" }}
          />
        )}
        {edge.label && <text x={midX} y={midY - 1.2} textAnchor="middle" fill={color.text} fontSize="2.2" className="font-mono uppercase tracking-wide">{edge.label}</text>}
      </g>
    );
  }

  return (
    <section className="glass-card rounded-3xl border border-cyan-500/20 overflow-hidden glow-cyan">
      <div className="px-5 sm:px-7 py-6 border-b border-white/8 flex flex-col xl:flex-row justify-between gap-5 xl:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold tracking-[0.16em] text-cyan-300 uppercase">
            <Network className="w-4 h-4" />
            Unified Autonomous Agent Network
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white mt-2">One neural system. Ten specialists. Closed feedback loop.</h2>
          <p className="text-sm text-slate-400 mt-2 max-w-3xl">Wähle einen Knoten für seine Funktion oder starte einen animierten Evidence-Run. Die Lichtimpulse zeigen Delegation, Review, Bewertung und Lern-Feedback als einen zusammenhängenden Graphen.</p>
        </div>
        <button
          onClick={() => void runNetwork()}
          disabled={isRunning}
          className="inline-flex flex-shrink-0 justify-center items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-cyan-500 via-blue-500 to-violet-600 text-white font-semibold hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed transition-all shadow-lg shadow-cyan-950/30"
        >
          {isRunning ? <Activity className="w-5 h-5 animate-pulse" /> : <Play className="w-5 h-5" />}
          {isRunning ? "Neural Flow aktiv …" : "Neural Flow starten"}
        </button>
      </div>

      <div className="grid xl:grid-cols-[1.55fr_0.8fr] min-h-[720px]">
        <div className="relative p-3 sm:p-5 min-h-[600px] bg-[radial-gradient(circle_at_center,rgba(8,145,178,0.15),transparent_28%),radial-gradient(circle_at_52%_52%,rgba(139,92,246,0.1),transparent_50%)]">
          <div className="absolute inset-0 opacity-40 grid-pattern pointer-events-none" />
          <div className="relative w-full h-full min-h-[590px] overflow-hidden rounded-2xl border border-white/6 bg-[#06070b]/50">
            <svg viewBox="0 0 100 102" preserveAspectRatio="xMidYMid meet" className="absolute inset-0 w-full h-full" aria-label="Interactive neural node map">
              <defs>
                <filter id="node-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="1.2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
                <radialGradient id="core-gradient"><stop offset="0%" stopColor="#a5f3fc" stopOpacity="0.75"/><stop offset="45%" stopColor="#0891b2" stopOpacity="0.45"/><stop offset="100%" stopColor="#1e1b4b" stopOpacity="0"/></radialGradient>
              </defs>
              <circle cx="50" cy="50" r="20" fill="url(#core-gradient)" className="animate-pulse" opacity="0.6" />
              {[...agentEdges, ...flowEdges].map(renderEdge)}
            </svg>

            {nodes.map((node) => {
              const isSelected = node.id === selectedNodeId;
              const isActive = activeNodeIds.includes(node.id);
              const color = palette[node.color] ?? palette.slate;
              const isCore = node.id === "neural-core";
              const isState = node.kind === "state";
              return (
                <motion.button
                  key={node.id}
                  onClick={() => selectNode(node.id)}
                  aria-label={`Open ${node.label}`}
                  animate={isActive ? { scale: [1, 1.08, 1], y: [0, -2, 0] } : { scale: 1, y: 0 }}
                  transition={isActive ? { duration: 1.25, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
                  className="absolute -translate-x-1/2 -translate-y-1/2 z-10 group text-center focus:outline-none"
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                >
                  <span
                    className={`relative block rounded-full border transition-all duration-300 ${isCore ? "w-28 h-28 sm:w-36 sm:h-36" : isState ? "min-w-[60px] px-2 h-10" : "w-[72px] h-[72px] sm:w-[86px] sm:h-[86px]"} ${isSelected ? "shadow-[0_0_35px_var(--node-glow)]" : "group-hover:brightness-125"}`}
                    style={{
                      borderColor: color.border,
                      backgroundColor: color.fill,
                      boxShadow: isSelected || isActive ? `0 0 ${isCore ? "42" : "24"}px ${color.glow}` : undefined,
                      // CSS custom property lets the static shadow shorthand above retain the node-specific glow.
                      ["--node-glow" as string]: color.glow,
                    }}
                  >
                    <span className={`absolute inset-1 rounded-full border opacity-30 ${isCore ? "border-cyan-200 animate-ping" : "border-white"}`} />
                    <span className="absolute inset-0 flex flex-col items-center justify-center px-2">
                      {node.kind === "agent" && <BrainCircuit className="w-4 h-4 sm:w-5 sm:h-5 mb-1" style={{ color: color.text }} />}
                      {node.id === "memory-ledger" && <Database className="w-4 h-4 sm:w-5 sm:h-5 mb-1" style={{ color: color.text }} />}
                      {node.id === "sandbox-gate" && <LockKeyhole className="w-4 h-4 sm:w-5 sm:h-5 mb-1" style={{ color: color.text }} />}
                      {node.id === "neural-core" && <Sparkles className="w-6 h-6 sm:w-8 sm:h-8 mb-1 text-cyan-100" />}
                      {node.kind === "state" && <CircleDot className="w-3.5 h-3.5 mb-0.5 mx-auto" style={{ color: color.text }} />}
                      <span className={`${isCore ? "text-[10px] sm:text-xs" : isState ? "text-[8px] sm:text-[9px]" : "text-[8px] sm:text-[10px]"} leading-tight font-bold whitespace-pre-line`} style={{ color: color.text }}>{node.shortLabel}</span>
                    </span>
                    {isActive && <span className="absolute -right-0.5 top-1 w-2.5 h-2.5 rounded-full bg-white pulse-dot" style={{ boxShadow: `0 0 12px ${color.line}` }} />}
                  </span>
                </motion.button>
              );
            })}
          </div>

          <div className="relative mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 px-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-full bg-cyan-400" /> Supervisor & routing</span>
            <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-full bg-purple-400" /> Independent review</span>
            <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-full bg-teal-400" /> Memory & retrieval</span>
            <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-full bg-red-400" /> Safety & escalation</span>
          </div>
        </div>

        <aside className="border-t xl:border-t-0 xl:border-l border-white/8 bg-black/20 p-5 sm:p-6 flex flex-col">
          <div className="flex rounded-lg bg-white/5 p-1 gap-1 mb-5">
            <button onClick={() => setActivePanel("node")} className={`flex-1 px-3 py-2 rounded-md text-xs font-medium ${activePanel === "node" ? "bg-white/10 text-white" : "text-slate-500 hover:text-white"}`}>Node Inspector</button>
            <button onClick={() => setActivePanel("gates")} className={`flex-1 px-3 py-2 rounded-md text-xs font-medium ${activePanel === "gates" ? "bg-white/10 text-white" : "text-slate-500 hover:text-white"}`}>Eval Gates</button>
          </div>

          <AnimatePresence mode="wait">
            {activePanel === "node" ? (
              <motion.div key={selectedNode.id} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} className="flex flex-col flex-1">
                <div className="flex items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-[0.15em]" style={{ color: (palette[selectedNode.color] ?? palette.slate).text }}>{selectedNode.kind} node</p><h3 className="text-xl font-bold text-white mt-1">{selectedNode.label}</h3></div><span className="w-3 h-3 rounded-full mt-1.5 pulse-dot" style={{ backgroundColor: (palette[selectedNode.color] ?? palette.slate).line }} /></div>
                <p className="text-sm leading-relaxed text-slate-400 mt-5">{selectedNode.description}</p>

                {selectedNode.agent && <div className="mt-6 space-y-3"><div className="rounded-xl bg-white/5 p-3"><p className="text-[10px] uppercase tracking-wider text-slate-500">Model / Context</p><p className="text-sm text-white mt-1">{selectedNode.agent.model} · {selectedNode.agent.contextWindow}</p></div><div><p className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Allow-listed Tools</p><div className="flex flex-wrap gap-2">{selectedNode.agent.tools.map((tool) => <span key={tool} className="px-2 py-1 rounded-md bg-white/5 border border-white/8 text-xs text-slate-300">{tool}</span>)}</div></div></div>}

                {selectedNode.workflowState && <div className="mt-6 rounded-xl p-4 bg-white/5 border border-white/8"><p className="text-[10px] uppercase tracking-wider text-slate-500">State Owner</p><p className="text-sm text-white mt-1">{workflowStates.find((state) => state.id === selectedNode.workflowState)?.owner}</p><p className="text-[10px] uppercase tracking-wider text-slate-500 mt-4">Transition Gate</p><p className="text-sm text-cyan-100 mt-1">{workflowStates.find((state) => state.id === selectedNode.workflowState)?.gate}</p></div>}

                <div className="mt-auto pt-6"><button onClick={() => void runNetwork()} disabled={isRunning} className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/8 hover:bg-white/12 text-sm font-semibold text-white disabled:opacity-50"><RefreshCw className={`w-4 h-4 ${isRunning ? "animate-spin" : ""}`} />Run this network</button></div>
              </motion.div>
            ) : (
              <motion.div key="gates" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} className="flex flex-col flex-1">
                <p className="text-xs uppercase tracking-[0.15em] text-yellow-300">Reflection contract</p><h3 className="text-xl font-bold text-white mt-1">Eval() decides the next edge</h3><p className="text-sm text-slate-400 mt-3">Verändere die Scores. Unter 85 führt der Graph zurück zu REVISING; fehlende Build- oder Security-Evidence eskaliert an einen Menschen.</p>
                <div className="space-y-4 mt-6">{evalMetrics.map((metric) => <div key={metric.key}><div className="flex justify-between text-xs mb-1.5"><span className="text-slate-300">{metric.label} <span className="text-slate-600">({metric.weight}%)</span></span><span className={scores[metric.key] >= metric.threshold ? "text-green-300" : "text-red-300"}>{scores[metric.key]}/{metric.threshold}</span></div><input aria-label={`${metric.label} evaluation score`} className="w-full accent-cyan-400" type="range" min="0" max="100" value={scores[metric.key]} onChange={(event) => setScores((current) => ({ ...current, [metric.key]: Number(event.target.value) }))} /></div>)}</div>
                <div className={`mt-6 p-4 rounded-xl border ${hardGateBlocked ? "bg-red-500/10 border-red-500/25" : compositeScore >= 85 ? "bg-green-500/10 border-green-500/25" : "bg-yellow-500/10 border-yellow-500/25"}`}><div className="flex items-center gap-3">{hardGateBlocked ? <AlertTriangle className="w-5 h-5 text-red-300" /> : compositeScore >= 85 ? <CheckCircle2 className="w-5 h-5 text-green-300" /> : <RefreshCw className="w-5 h-5 text-yellow-300" />}<div><p className="font-bold text-white">{compositeScore}/100</p><p className="text-xs text-slate-400">{hardGateBlocked ? "ESCALATED · hard gate" : compositeScore >= 85 ? "DEPLOYING · evidence passed" : "REVISING · feedback required"}</p></div></div></div>
              </motion.div>
            )}
          </AnimatePresence>
        </aside>
      </div>

      <div className="border-t border-white/8 px-5 sm:px-7 py-5 grid lg:grid-cols-[1fr_auto] gap-5 items-center">
        <div className="flex items-start gap-3"><div className={`mt-0.5 w-2.5 h-2.5 rounded-full ${memoryConnected === "connected" ? "bg-teal-400 pulse-dot" : memoryConnected === "loading" ? "bg-yellow-400 pulse-dot" : "bg-slate-400"}`} /><div><p className="text-sm font-medium text-white">Feedback ledger: {memoryConnected === "connected" ? "PostgreSQL connected" : memoryConnected === "loading" ? "connecting" : "local fallback"}</p><p className="text-xs text-slate-500 mt-1">{result}</p></div></div>
        <div className="flex items-center gap-2 text-xs text-slate-400"><ShieldCheck className="w-4 h-4 text-green-300" />Docker/gVisor isolation <span className="text-slate-700">•</span><UserRoundCheck className="w-4 h-4 text-cyan-300" />Human release gate</div>
      </div>

      {events.length > 0 && <div className="border-t border-white/8 px-5 sm:px-7 py-5"><div className="flex items-center gap-2 text-xs uppercase tracking-wider text-teal-300 mb-3"><Database className="w-4 h-4" />Latest neural evidence</div><div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">{events.map((event) => <div key={event.id} className="rounded-xl bg-black/25 border border-white/7 p-3"><div className="flex justify-between gap-2"><p className="font-mono text-[10px] text-slate-500 truncate">{event.agentId}</p><span className={`text-[10px] font-bold uppercase ${event.outcome === "passed" ? "text-green-300" : event.outcome === "escalated" ? "text-red-300" : "text-yellow-300"}`}>{event.outcome}</span></div><p className="text-sm font-semibold text-white mt-2">{event.workflowState} · {event.score}/100</p><p className="text-xs leading-relaxed text-slate-500 mt-2 line-clamp-3">{event.notes}</p></div>)}</div></div>}

      <div className="border-t border-white/8 px-5 sm:px-7 py-5 grid sm:grid-cols-2 xl:grid-cols-4 gap-3 bg-white/[0.015]">
        {sandboxPolicies.map((policy) => <div key={policy.title} className="flex items-start gap-3"><ShieldCheck className="w-4 h-4 text-red-300 mt-0.5 flex-shrink-0" /><div><p className="text-xs font-semibold text-slate-300">{policy.badge}</p><p className="text-[11px] text-slate-500 mt-0.5">{policy.title}</p></div></div>)}
      </div>
    </section>
  );
}
