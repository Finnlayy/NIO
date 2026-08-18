"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  Circle,
  CircleDot,
  Clock3,
  Container,
  Database,
  FileCode2,
  Filter,
  GitPullRequest,
  KeyRound,
  LayoutDashboard,
  LockKeyhole,
  MessageCircle,
  Menu,
  MoreHorizontal,
  Network,
  PanelLeft,
  Play,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Terminal,
  UserRoundCheck,
  UsersRound,
  Workflow,
  X,
} from "lucide-react";
import {
  mockMemory,
  googleCloudControlPlane,
  type AgentStatus,
  type MockAgent,
  type MockRun,
  type RunStatus,
} from "@/data/mock-orchestrator";
import ActivityFeed from "@/components/ActivityFeed";
import CodyStatsBoard from "@/components/CodyStatsBoard";
import CommsAuditPage from "@/components/CommsAuditPage";
import NotificationPanel from "@/components/NotificationPanel";
import NodeAdminReportModal from "@/components/NodeAdminReportModal";
import GenkitPanel from "@/components/GenkitPanel";
import BoundaryPanel from "@/components/BoundaryPanel";
import NetworkDashboard from "@/components/NetworkDashboard";
import { useOrchestratorLive } from "@/hooks/useOrchestratorLive";
import { COMMS_OPEN_EVENT } from "@/hooks/useCommsAudit";
import type { LimbInstance, LimbTemplate } from "@/lib/manifest-types";
import type { GoogleCloudAgentRegistryEntry } from "@/data/mock-orchestrator";

type ConsoleView = "overview" | "agents" | "library" | "workflows" | "memory" | "policies" | "genkit" | "boundary" | "network" | "comms";

type AgentNode = { id: string; x: number; y: number };

const coreNodes: AgentNode[] = [
  { id: "orchestrator", x: 50, y: 48 },
  { id: "sandbox", x: 84, y: 68 },
  { id: "memory", x: 15, y: 42 },
  { id: "cody", x: 50, y: 88 },
];

function layoutLimbNodes(limbIds: string[]): AgentNode[] {
  const count = limbIds.length;
  if (count === 0) return [];
  const radius = 32;
  const centerX = 50;
  const centerY = 46;
  return limbIds.map((id, index) => {
    const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
    return {
      id,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });
}

const agentColors: Record<MockAgent["color"], { solid: string; pale: string; border: string; text: string; line: string }> = {
  cyan: { solid: "#22d3ee", pale: "rgba(6,182,212,0.15)", border: "border-cyan-400/35", text: "text-cyan-200", line: "#22d3ee" },
  violet: { solid: "#a78bfa", pale: "rgba(139,92,246,0.16)", border: "border-violet-400/35", text: "text-violet-200", line: "#a78bfa" },
  orange: { solid: "#fb923c", pale: "rgba(249,115,22,0.16)", border: "border-orange-400/35", text: "text-orange-200", line: "#fb923c" },
  blue: { solid: "#60a5fa", pale: "rgba(59,130,246,0.16)", border: "border-blue-400/35", text: "text-blue-200", line: "#60a5fa" },
  green: { solid: "#4ade80", pale: "rgba(34,197,94,0.16)", border: "border-green-400/35", text: "text-green-200", line: "#4ade80" },
  pink: { solid: "#f472b6", pale: "rgba(236,72,153,0.16)", border: "border-pink-400/35", text: "text-pink-200", line: "#f472b6" },
  amber: { solid: "#fbbf24", pale: "rgba(245,158,11,0.16)", border: "border-amber-400/35", text: "text-amber-200", line: "#fbbf24" },
  red: { solid: "#fb7185", pale: "rgba(239,68,68,0.16)", border: "border-rose-400/35", text: "text-rose-200", line: "#fb7185" },
};

const statusStyles: Record<AgentStatus, { label: string; dot: string; text: string }> = {
  idle: { label: "Idle", dot: "bg-slate-500", text: "text-slate-400" },
  working: { label: "Working", dot: "bg-cyan-400", text: "text-cyan-300" },
  reviewing: { label: "Reviewing", dot: "bg-violet-400", text: "text-violet-300" },
  blocked: { label: "Blocked", dot: "bg-rose-400", text: "text-rose-300" },
  ready: { label: "Ready", dot: "bg-emerald-400", text: "text-emerald-300" },
};

const runStyles: Record<RunStatus, { label: string; className: string }> = {
  running: { label: "Running", className: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20" },
  review: { label: "In review", className: "bg-violet-500/10 text-violet-300 border-violet-500/20" },
  queued: { label: "Queued", className: "bg-slate-500/10 text-slate-300 border-slate-500/20" },
  passed: { label: "Passed", className: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" },
  "needs-input": { label: "Needs input", className: "bg-amber-500/10 text-amber-300 border-amber-500/20" },
};

function getPath(from: AgentNode, to: AgentNode) {
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2;
  const bend = (from.y - to.y) * 0.12;
  return `M ${from.x} ${from.y} Q ${midX + bend} ${midY + bend} ${to.x} ${to.y}`;
}

export default function OrchestratorConsole() {
  const {
    apiLive,
    agents,
    canvasAgents,
    coreAgents,
    activeLimbs,
    libraryTemplates,
    libraryArchive,
    templateRows,
    setAgents,
    registryEntries,
    metrics,
    policies,
    activities,
    memoryItems,
    runs,
    isRunning,
    runWorkflow,
    codyStats,
    refresh,
  } = useOrchestratorLive();

  const [view, setView] = useState<ConsoleView>("overview");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("orchestrator");
  const [adminReportAgentId, setAdminReportAgentId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [memorySearch, setMemorySearch] = useState("");
  const [policyEnabled, setPolicyEnabled] = useState<Record<string, boolean>>({});

  const policyList = policies.length ? policies : [];
  const effectivePolicyEnabled = Object.keys(policyEnabled).length
    ? policyEnabled
    : Object.fromEntries(policyList.map((policy) => [policy.id, policy.enabled]));

  const selectedAgent = [...canvasAgents, ...coreAgents, ...agents].find((agent) => agent.id === selectedAgentId) ?? canvasAgents[0] ?? agents[0];
  if (!selectedAgent) {
    return <main className="min-h-screen bg-[#090b12] text-slate-200 grid place-items-center"><p className="text-slate-500">Loading agents…</p></main>;
  }
  const selectedAgentColor = agentColors[selectedAgent.color];
  const filteredAgents = agents.filter((agent) => `${agent.name} ${agent.role} ${agent.domain}`.toLowerCase().includes(search.toLowerCase()));
  const displayAgents = apiLive ? [...coreAgents, ...canvasAgents.filter((a) => a.id !== "orchestrator" && a.id !== "cody")] : agents;
  const filteredDisplayAgents = displayAgents.filter((agent) => `${agent.name} ${agent.role} ${agent.domain}`.toLowerCase().includes(search.toLowerCase()));
  const filteredMemory = memoryItems.filter((memory) => `${memory.title} ${memory.summary} ${memory.tags.join(" ")}`.toLowerCase().includes(memorySearch.toLowerCase()));
  const activeAgentCount = apiLive ? activeLimbs.length + (codyStats?.online ? 1 : 0) : agents.filter((agent) => agent.status === "working" || agent.status === "reviewing").length;
  const workingRun = runs.find((run) => run.status === "running");

  const adminReportAgent = useMemo(() => {
    if (!adminReportAgentId) return null;
    return [...canvasAgents, ...coreAgents, ...agents].find((agent) => agent.id === adminReportAgentId) ?? null;
  }, [adminReportAgentId, canvasAgents, coreAgents, agents]);

  const adminLimb = useMemo((): LimbInstance | null => {
    if (!adminReportAgentId?.startsWith("limb-")) return null;
    return activeLimbs.find((limb) => limb.limb_instance_id === adminReportAgentId) ?? null;
  }, [adminReportAgentId, activeLimbs]);

  const adminTemplate = useMemo((): LimbTemplate | null => {
    const templateId = adminLimb?.template_id;
    if (!templateId) return null;
    return libraryTemplates.find((template) => template.template_id === templateId) ?? null;
  }, [adminLimb, libraryTemplates]);

  const adminRegistryEntry = useMemo((): GoogleCloudAgentRegistryEntry | undefined => {
    if (!adminReportAgentId) return undefined;
    return registryEntries.find((entry) => entry.agentId === adminReportAgentId);
  }, [adminReportAgentId, registryEntries]);

  const openAdminReport = (agentId: string) => {
    setSelectedAgentId(agentId);
    setAdminReportAgentId(agentId);
  };

  const workflowStages = useMemo(() => [
    { label: "Plan", value: "04", color: "bg-blue-400" },
    { label: "Execute", value: "03", color: "bg-cyan-400" },
    { label: "Review", value: "02", color: "bg-violet-400" },
    { label: "Human gate", value: "02", color: "bg-amber-400" },
    { label: "Archived", value: "18", color: "bg-emerald-400" },
  ], []);

  const runMockWorkflow = () => {
    void runWorkflow();
  };

  const navigation = [
    { id: "overview" as const, label: "Overview", icon: LayoutDashboard },
    { id: "agents" as const, label: "Agents", icon: Bot, count: activeAgentCount },
    { id: "library" as const, label: "Agent Library", icon: FileCode2, count: libraryTemplates.length || undefined },
    { id: "workflows" as const, label: "Workflows", icon: Workflow },
    { id: "comms" as const, label: "Comms", icon: MessageCircle },
    { id: "memory" as const, label: "Memory", icon: Database },
    { id: "network" as const, label: "Network", icon: Network },
    { id: "policies" as const, label: "Policies", icon: ShieldCheck },
    { id: "genkit" as const, label: "GenKit", icon: Sparkles },
    { id: "boundary" as const, label: "Boundary", icon: LockKeyhole },
  ];

  const selectView = (nextView: ConsoleView) => {
    setView(nextView);
    setMobileMenuOpen(false);
  };

  useEffect(() => {
    const handler = () => selectView("comms");
    window.addEventListener(COMMS_OPEN_EVENT, handler);
    return () => window.removeEventListener(COMMS_OPEN_EVENT, handler);
  }, []);

  return (
    <main className="min-h-screen bg-[#090b12] text-slate-200">
      <div className="min-h-screen lg:grid lg:grid-cols-[246px_1fr]">
        <aside className="hidden lg:flex fixed inset-y-0 left-0 w-[246px] flex-col border-r border-white/[0.07] bg-[#0c0f18] px-4 py-5 z-30">
          <Brand />
          <SidebarNavigation navigation={navigation} activeView={view} onChange={selectView} />
          <SidebarFooter />
        </aside>

        <div className="lg:col-start-2 min-w-0">
          <header className="sticky top-0 z-20 h-[70px] border-b border-white/[0.07] bg-[#090b12]/88 backdrop-blur-xl px-4 sm:px-6 xl:px-8 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <button onClick={() => setMobileMenuOpen(true)} className="lg:hidden p-2 rounded-lg hover:bg-white/5 text-slate-300"><Menu className="w-5 h-5" /></button>
              <div className="min-w-0"><p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">NIO / Neural Intelligence Orchestrator</p><h1 className="text-sm sm:text-base font-semibold text-white truncate">Control Room <span className="hidden sm:inline text-slate-500 font-normal">· twin/model-manifest.json</span></h1></div>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-medium ${apiLive ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-200" : "bg-amber-500/10 border border-amber-500/20 text-amber-200"}`}><CircleDot className="w-3.5 h-3.5" />{apiLive ? "Live · NIO API" : "Degraded · API offline"}</div>
              <NotificationPanel />
              <button className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 to-violet-500 text-slate-950 text-xs font-bold">JL</button>
            </div>
          </header>

          <AnimatePresence>
            {mobileMenuOpen && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 lg:hidden bg-black/60 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)}>
                <motion.aside initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }} transition={{ type: "spring", stiffness: 340, damping: 32 }} className="w-[270px] h-full bg-[#0c0f18] border-r border-white/10 px-4 py-5" onClick={(event) => event.stopPropagation()}>
                  <div className="flex justify-between items-center"><Brand /><button onClick={() => setMobileMenuOpen(false)} className="p-2 text-slate-400"><X className="w-5 h-5" /></button></div>
                  <SidebarNavigation navigation={navigation} activeView={view} onChange={selectView} />
                  <SidebarFooter />
                </motion.aside>
              </motion.div>
            )}
          </AnimatePresence>

          <section className="px-4 sm:px-6 xl:px-8 py-6 xl:py-8 max-w-[1700px] mx-auto">
            <AnimatePresence mode="wait">
              {view === "overview" && (
                <motion.div key="overview" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <DashboardHeading onCreateRun={runMockWorkflow} isRunning={isRunning} apiLive={apiLive} />
                  <MetricRow metrics={metrics} />
                  <div className="mt-5">
                    <CodyStatsBoard stats={codyStats} />
                  </div>
                  <GoogleCloudPlane />
                  <div className="grid 2xl:grid-cols-[minmax(0,1.45fr)_380px] gap-5 mt-5">
                    <NeuralCanvas
                      agents={canvasAgents}
                      selectedAgentId={selectedAgentId}
                      onSelect={setSelectedAgentId}
                      onAdminOpen={openAdminReport}
                      isRunning={isRunning}
                    />
                    <div className="space-y-5">
                      <CoreAgentsPanel agents={coreAgents.filter((a) => a.id !== "orchestrator")} />
                      <AgentInspector agent={selectedAgent} registryEntries={registryEntries} onOpenAgents={() => setView("agents")} />
                    </div>
                  </div>
                  <div className="grid xl:grid-cols-[minmax(0,1.18fr)_minmax(390px,0.82fr)] gap-5 mt-5">
                    <RunQueue runs={runs} onOpenWorkflows={() => setView("workflows")} />
                    <ActivityFeed activities={activities} orchestratorLive={apiLive} />
                  </div>
                </motion.div>
              )}

              {view === "agents" && (
                <motion.div key="agents" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <PageHeading eyebrow="Atlas runtime" title="Core + active limbs" description="Persistent core agents (Atlas, Aegis, Echo) and 0–N ephemeral limb instances deployed for tasks. Cody remains the human interface limb." action={<button onClick={runMockWorkflow} className="primary-button"><Play className="w-4 h-4" />Run task</button>} />
                  <div className="mt-6 grid 2xl:grid-cols-[minmax(0,1fr)_365px] gap-5">
                    <div className="console-card overflow-hidden">
                      <div className="p-4 sm:p-5 border-b border-white/[0.07] flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div className="relative w-full sm:max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search core and active limbs" className="console-input pl-10" /></div><span className="text-xs text-slate-500">{filteredDisplayAgents.length} agents · {activeLimbs.length} active limbs</span></div>
                      <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm"><thead className="bg-white/[0.025] text-left text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-3 font-medium">Agent</th><th className="px-5 py-3 font-medium">Domain</th><th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Capacity</th><th className="px-5 py-3 font-medium">Last action</th><th className="px-5 py-3" /></tr></thead><tbody>{filteredDisplayAgents.map((agent) => <AgentTableRow key={agent.id} agent={agent} selected={agent.id === selectedAgentId} onClick={() => setSelectedAgentId(agent.id)} />)}</tbody></table></div>
                    </div>
                    <AgentInspector agent={selectedAgent} registryEntries={registryEntries} onOpenAgents={() => undefined} />
                  </div>
                </motion.div>
              )}

              {view === "library" && (
                <motion.div key="library" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <PageHeading eyebrow="Agent Library" title="Templates + archived runs" description="Reusable limb templates Atlas queries during PLAN, plus post-mortem archive entries from retired instances." action={<button onClick={() => setView("overview")} className="primary-button"><BrainCircuit className="w-4 h-4" />Back to canvas</button>} />
                  <AgentLibraryView templates={templateRows} archive={libraryArchive} />
                </motion.div>
              )}

              {view === "workflows" && (
                <motion.div key="workflows" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <PageHeading eyebrow="Workflow queue" title="Work moves through NIO gates" description="Kanban view of orchestration state. Run task calls POST /api/task on the NIO middleware with manifest tier routing." action={<button onClick={runMockWorkflow} disabled={isRunning} className="primary-button"><Play className="w-4 h-4" />{isRunning ? "Running…" : "Run workflow"}</button>} />
                  <div className="mt-6 grid sm:grid-cols-2 xl:grid-cols-5 gap-4">{workflowStages.map((stage, index) => <div key={stage.label} className="console-card p-4 min-h-[250px]"><div className="flex items-center justify-between"><div className="flex items-center gap-2"><span className={`w-2 h-2 rounded-full ${stage.color}`} /><h3 className="font-semibold text-sm text-white">{stage.label}</h3></div><span className="text-xs text-slate-500">{stage.value}</span></div><div className="mt-4 space-y-3">{runs.filter((run) => (index === 0 && run.status === "queued") || (index === 1 && run.status === "running") || (index === 2 && run.status === "review") || (index === 3 && run.status === "needs-input") || (index === 4 && run.status === "passed")).map((run) => <WorkflowRunCard key={run.id} run={run} />)}{!runs.some((run) => (index === 0 && run.status === "queued") || (index === 1 && run.status === "running") || (index === 2 && run.status === "review") || (index === 3 && run.status === "needs-input") || (index === 4 && run.status === "passed")) && <div className="rounded-lg border border-dashed border-white/10 p-4 text-xs text-slate-600">No mock work items</div>}</div></div>)}</div>
                  <section className="mt-5 console-card p-5"><div className="flex items-center gap-2"><Workflow className="w-5 h-5 text-cyan-300" /><h2 className="font-semibold text-white">Prototype transition logic</h2></div><div className="mt-5 flex flex-wrap items-center gap-2 text-sm">{["Plan", "Execute", "Review", "Evaluate", "Revise", "Human gate", "Archive"].map((state, index, all) => <div key={state} className="flex items-center gap-2"><span className="px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.07] text-slate-300">{state}</span>{index < all.length - 1 && <ArrowRight className="w-4 h-4 text-slate-600" />}</div>)}</div></section>
                </motion.div>
              )}

              {view === "memory" && (
                <motion.div key="memory" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <PageHeading eyebrow="Eval / memory" title="Retrieve context before planning" description="Behavioral ledger from PostgreSQL when available; falls back to bundled seed entries when the database is offline." action={<div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-400/10 border border-teal-400/20 text-xs text-teal-200"><Database className="w-4 h-4" />Ledger + telemetry</div>} />
                  <div className="mt-6 console-card p-5"><div className="relative max-w-2xl"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" /><input value={memorySearch} onChange={(event) => setMemorySearch(event.target.value)} placeholder="Search simulated past reviews, incidents or policies" className="console-input pl-10" /></div><div className="mt-6 grid lg:grid-cols-3 gap-4">{filteredMemory.map((memory) => <article key={memory.id} className="rounded-xl bg-white/[0.035] border border-white/[0.07] p-5 hover:border-teal-400/25 transition-colors"><div className="flex justify-between gap-3"><span className="text-[10px] uppercase tracking-wider text-teal-300">Similarity {Math.round(memory.score * 100)}%</span><span className="text-xs text-slate-600">{memory.age}</span></div><h2 className="font-semibold text-white mt-3">{memory.title}</h2><p className="text-sm leading-relaxed text-slate-400 mt-3">{memory.summary}</p><div className="flex flex-wrap gap-1.5 mt-4">{memory.tags.map((tag) => <span key={tag} className="px-2 py-1 rounded-md bg-white/[0.05] text-[11px] text-slate-400">{tag}</span>)}</div><div className="mt-4 pt-3 border-t border-white/[0.07] flex justify-between text-xs"><span className="text-slate-600">Source</span><span className="text-slate-300">{memory.source}</span></div></article>)}</div>{filteredMemory.length === 0 && <p className="py-12 text-center text-sm text-slate-500">No mock memory matches this search.</p>}</div>
                </motion.div>
              )}

              {view === "network" && (
                <motion.div key="network" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <NetworkDashboard />
                </motion.div>
              )}

              {view === "comms" && (
                <motion.div key="comms" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <CommsAuditPage />
                </motion.div>
              )}

              {view === "genkit" && (
                <motion.div key="genkit" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <GenkitPanel />
                </motion.div>
              )}

              {view === "boundary" && (
                <motion.div key="boundary" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <BoundaryPanel />
                </motion.div>
              )}

              {view === "policies" && (
                <motion.div key="policies" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                  <PageHeading eyebrow="Manifest security policies" title="Guardrails are server-enforced" description="Budget and tier policies from twin/model-manifest.json. Toggles are informational; the NIO backend enforces cost budgets at runtime." action={<div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-rose-400/10 border border-rose-400/20 text-xs text-rose-200"><LockKeyhole className="w-4 h-4" />Server invariants</div>} />
                  <div className="mt-6 grid lg:grid-cols-[minmax(0,1fr)_360px] gap-5"><div className="space-y-3">{policyList.map((policy) => <PolicyRow key={policy.id} policy={policy} enabled={effectivePolicyEnabled[policy.id] ?? policy.enabled} onToggle={() => setPolicyEnabled((current) => ({ ...current, [policy.id]: !(current[policy.id] ?? policy.enabled) }))} />)}</div><section className="console-card p-6"><ShieldCheck className="w-7 h-7 text-rose-300" /><h2 className="text-xl font-semibold text-white mt-4">Release safety summary</h2><p className="text-sm leading-relaxed text-slate-400 mt-3">A real service must treat these controls as server-side invariants. This design prototype communicates the intended gates without exposing operational credentials or invoking any external tool.</p><div className="mt-6 space-y-3">{["No direct production writes", "Scoped mock credentials", "Evidence required for state transition", "Owner approval before release"].map((item) => <div key={item} className="flex gap-3 text-sm text-slate-300"><CheckCircle2 className="w-4 h-4 text-emerald-300 mt-0.5" />{item}</div>)}</div></section></div>
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        </div>
      </div>
      <NodeAdminReportModal
        open={adminReportAgentId !== null}
        agent={adminReportAgent}
        limb={adminLimb}
        template={adminTemplate}
        registryEntry={adminRegistryEntry}
        templates={libraryTemplates}
        apiLive={apiLive}
        onClose={() => setAdminReportAgentId(null)}
        onActionComplete={() => void refresh()}
      />
    </main>
  );
}

function Brand() {
  return <div className="flex items-center gap-3"><div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-400 via-blue-500 to-violet-500 grid place-items-center shadow-lg shadow-cyan-950/30"><Network className="w-5 h-5 text-white" /></div><div><p className="font-semibold text-white text-sm tracking-tight">NIO</p><p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Neural Intelligence Orchestrator</p></div></div>;
}

function SidebarNavigation({ navigation, activeView, onChange }: { navigation: { id: ConsoleView; label: string; icon: typeof LayoutDashboard; count?: number }[]; activeView: ConsoleView; onChange: (view: ConsoleView) => void }) {
  return <nav className="mt-9 space-y-1">{navigation.map((item) => { const Icon = item.icon; const active = item.id === activeView; return <button key={item.id} onClick={() => onChange(item.id)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${active ? "bg-white/[0.09] text-white shadow-sm" : "text-slate-500 hover:text-slate-200 hover:bg-white/[0.04]"}`}><Icon className={`w-4.5 h-4.5 ${active ? "text-cyan-300" : ""}`} /><span className="flex-1 text-left">{item.label}</span>{item.count !== undefined && <span className={`min-w-5 h-5 rounded-full text-[10px] leading-5 text-center ${active ? "bg-cyan-400 text-slate-950" : "bg-white/[0.08] text-slate-400"}`}>{item.count}</span>}</button>; })}</nav>;
}

function SidebarFooter() {
  return <div className="mt-auto space-y-3"><div className="rounded-xl border border-cyan-400/15 bg-cyan-400/[0.045] p-3"><div className="flex gap-2"><Sparkles className="w-4 h-4 text-cyan-300 mt-0.5" /><div><p className="text-xs font-medium text-cyan-100">NIO middleware</p><p className="text-[11px] leading-relaxed text-slate-500 mt-1">Model tiers from twin/model-manifest.json via :4000 API.</p></div></div></div><button className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-500 hover:text-white"><Settings className="w-4 h-4" />NIO settings</button></div>;
}

function DashboardHeading({ onCreateRun, isRunning, apiLive }: { onCreateRun: () => void; isRunning: boolean; apiLive: boolean }) {
  return <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-5"><div><p className="text-xs uppercase tracking-[0.18em] text-cyan-300">NIO control plane · {apiLive ? "live" : "degraded"}</p><h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white mt-2">Neural Intelligence Orchestrator</h2><p className="text-sm text-slate-500 mt-2">Agents resolve models from manifest role_overrides; tasks route through NIO middleware on port 4000.</p></div><div className="flex gap-2"><button onClick={onCreateRun} disabled={isRunning} className="primary-button"><Play className="w-4 h-4" />{isRunning ? "Running…" : "Run workflow"}</button><button className="p-2.5 rounded-xl border border-white/[0.08] hover:bg-white/[0.05] text-slate-300"><MoreHorizontal className="w-5 h-5" /></button></div></div>;
}

function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4"><div><p className="text-xs uppercase tracking-[0.18em] text-cyan-300">{eyebrow}</p><h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white mt-2">{title}</h2><p className="text-sm text-slate-500 mt-2 max-w-3xl">{description}</p></div>{action}</div>;
}

function MetricRow({ metrics }: { metrics: Array<{ label: string; value: string; delta: string; direction: "up" | "down" | "neutral"; caption: string }> }) {
  return <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mt-6">{metrics.map((metric, index) => <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }} key={metric.label} className="console-card p-4 sm:p-5"><div className="flex justify-between gap-3"><p className="text-xs text-slate-500">{metric.label}</p><span className={`text-[11px] ${metric.direction === "up" ? "text-emerald-300" : "text-slate-400"}`}>{metric.delta}</span></div><p className="text-2xl font-semibold tracking-tight text-white mt-2">{metric.value}</p><p className="text-[11px] text-slate-600 mt-1">{metric.caption}</p></motion.div>)}</div>;
}

function GoogleCloudPlane() {
  return <section className="console-card mt-5 overflow-hidden"><div className="px-5 py-4 border-b border-white/[0.07] flex flex-col sm:flex-row sm:items-center justify-between gap-2"><div className="flex items-center gap-2"><Network className="w-4 h-4 text-cyan-300" /><p className="text-sm font-medium text-white">Option A · Google Cloud control-plane registry</p></div><span className="text-[11px] text-slate-500">Google Cloud Console services only</span></div><div className="grid sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7 divide-y sm:divide-y-0 sm:divide-x divide-white/[0.07]">{googleCloudControlPlane.map((entry) => <div key={entry.category} className="p-4"><p className="text-[10px] uppercase tracking-wider text-cyan-300">{entry.category}</p><p className="text-xs font-medium text-white mt-2 leading-snug">{entry.service}</p><p className="text-[11px] leading-relaxed text-slate-600 mt-1.5">{entry.purpose}</p></div>)}</div></section>;
}

function NeuralCanvas({ agents, selectedAgentId, onSelect, onAdminOpen, isRunning }: { agents: MockAgent[]; selectedAgentId: string; onSelect: (id: string) => void; onAdminOpen: (id: string) => void; isRunning: boolean }) {
  const limbIds = agents.filter((a) => a.id !== "orchestrator" && a.id !== "cody").map((a) => a.id);
  const agentNodes = [
    ...coreNodes.filter((n) => n.id === "orchestrator" || n.id === "cody"),
    ...layoutLimbNodes(limbIds),
  ];
  const nodeLookup = Object.fromEntries(agentNodes.map((node) => [node.id, node]));
  const coreNode = nodeLookup.orchestrator;
  const edgeAgents = agents.filter((a) => a.id !== "orchestrator" && nodeLookup[a.id]);
  return <section className="console-card overflow-hidden min-h-[540px]"><div className="p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.07]"><div><div className="flex items-center gap-2"><Network className="w-4 h-4 text-cyan-300" /><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Atlas + active limbs</p></div><h2 className="text-lg font-semibold text-white mt-1">Neural agent fabric</h2></div><div className="flex items-center gap-3 text-xs text-slate-500"><span className="flex items-center gap-1.5"><i className="w-1.5 h-1.5 rounded-full bg-cyan-400" />Atlas core</span><span className="flex items-center gap-1.5"><i className="w-1.5 h-1.5 rounded-full bg-violet-400" />Active limb</span><span className="flex items-center gap-1.5"><i className="w-1.5 h-1.5 rounded-full bg-amber-400" />Cody</span><span className="hidden sm:inline text-slate-600">· double-click node for admin report</span></div></div><div className="relative min-h-[470px] overflow-hidden bg-[radial-gradient(circle_at_50%_45%,rgba(8,145,178,0.18),transparent_20%),radial-gradient(circle_at_70%_60%,rgba(139,92,246,0.10),transparent_30%)]"><div className="absolute inset-0 opacity-50 grid-pattern" />{!coreNode && <p className="absolute inset-0 grid place-items-center text-sm text-slate-500">Atlas core offline</p>}<svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" preserveAspectRatio="none"><defs><filter id="canvas-glow"><feGaussianBlur stdDeviation="1" result="coloredBlur"/><feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>{coreNode && edgeAgents.map((agent) => { const node = nodeLookup[agent.id]!; const from = agent.id === "cody" ? node : coreNode; const to = agent.id === "cody" ? coreNode : node; const selected = selectedAgentId === agent.id; const active = agent.status === "working" || agent.status === "reviewing"; const color = agentColors[agent.color]; return <g key={agent.id}><path d={getPath(from, to)} fill="none" stroke={color.line} strokeWidth={selected || active ? 0.45 : 0.16} opacity={selected || active ? 0.82 : 0.2} /><AnimatePresence>{(selected || (isRunning && active)) && <motion.circle initial={{ cx: from.x, cy: from.y, opacity: 0 }} animate={{ cx: [from.x, (from.x + to.x) / 2, to.x], cy: [from.y, (from.y + to.y) / 2, to.y], opacity: [0, 1, 1, 0] }} transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }} r="0.95" fill={color.line} filter="url(#canvas-glow)" />}</AnimatePresence></g>; })}</svg>{agents.filter((agent) => nodeLookup[agent.id]).map((agent) => { const node = nodeLookup[agent.id]!; const selected = selectedAgentId === agent.id; const active = agent.status === "working" || agent.status === "reviewing"; const color = agentColors[agent.color]; const isCore = agent.id === "orchestrator"; const isCody = agent.id === "cody"; return <motion.button key={agent.id} onClick={() => onSelect(agent.id)} onDoubleClick={() => onAdminOpen(agent.id)} title="Double-click for admin report" animate={active || selected ? { scale: [1, 1.045, 1] } : { scale: 1 }} transition={active || selected ? { duration: 2.4, repeat: Infinity } : {}} className="absolute -translate-x-1/2 -translate-y-1/2 text-center group z-10" style={{ left: `${node.x}%`, top: `${node.y}%` }}><span className={`relative grid place-items-center ${isCore ? "w-24 h-24 sm:w-28 sm:h-28" : "w-[68px] h-[68px] sm:w-[76px] sm:h-[76px]"} rounded-full border transition-all ${selected ? "ring-2 ring-white/30" : "group-hover:brightness-125"}`} style={{ background: color.pale, borderColor: color.solid, boxShadow: selected || active ? `0 0 ${isCore ? 38 : 20}px ${color.pale}` : undefined }}><span className="absolute inset-1 rounded-full border border-white/10" />{isCore ? <BrainCircuit className="w-6 h-6 text-cyan-100" /> : isCody ? <span className="text-lg">⚡</span> : <span className="text-xs font-bold" style={{ color: color.solid }}>{agent.initials}</span>}{active && <span className="absolute top-0 right-0 w-2.5 h-2.5 rounded-full bg-cyan-300 pulse-dot shadow-[0_0_12px_rgba(34,211,238,0.9)]" />}</span><span className={`block mt-2 max-w-[90px] text-[10px] leading-tight font-medium ${selected ? "text-white" : "text-slate-400"}`}>{isCore ? "Atlas · Core" : isCody ? "Cody · Telegram" : agent.name}</span></motion.button>; })}{agents.length <= 2 && <p className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[11px] text-slate-500">No active limbs — run a task to deploy one</p>}</div></section>;
}

function AgentInspector({ agent, registryEntries, onOpenAgents }: { agent: MockAgent; registryEntries: Array<{ agentId: string; llmModel: string; contextWindow: string; runtime: string; serviceAccount: string; allowedGoogleCloudServices: string[] }>; onOpenAgents: () => void }) {
  const colors = agentColors[agent.color];
  const status = statusStyles[agent.status];
  const registryEntry = registryEntries.find((entry) => entry.agentId === agent.id);
  return <section className={`console-card p-5 sm:p-6 border ${colors.border} flex flex-col`}><div className="flex items-start justify-between"><div className="flex items-center gap-3"><div className="w-11 h-11 rounded-xl grid place-items-center font-bold text-sm" style={{ background: colors.pale, color: colors.solid }}>{agent.initials}</div><div><p className="font-semibold text-white">{agent.name}</p><p className="text-xs text-slate-500 mt-0.5">{agent.role}</p></div></div><button onClick={onOpenAgents} className="p-1.5 text-slate-500 hover:text-white"><ArrowUpRight className="w-4 h-4" /></button></div><div className="mt-6 grid grid-cols-2 gap-3"><div className="rounded-lg bg-white/[0.035] p-3"><p className="text-[10px] uppercase tracking-wider text-slate-600">Status</p><p className={`flex items-center gap-1.5 text-sm font-medium mt-1 ${status.text}`}><i className={`w-1.5 h-1.5 rounded-full ${status.dot} ${agent.status === "working" ? "pulse-dot" : ""}`} />{status.label}</p></div><div className="rounded-lg bg-white/[0.035] p-3"><p className="text-[10px] uppercase tracking-wider text-slate-600">Reliability</p><p className="text-sm font-medium text-white mt-1">{agent.reliability}%</p></div></div><div className="mt-5"><div className="flex justify-between text-xs text-slate-500"><span>Capacity</span><span>{agent.load}%</span></div><div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden mt-2"><motion.div animate={{ width: `${agent.load}%` }} className="h-full rounded-full" style={{ background: colors.solid }} /></div></div><div className="mt-5"><p className="text-[10px] uppercase tracking-wider text-slate-600">Last action</p><p className="text-sm leading-relaxed text-slate-300 mt-2">{agent.lastAction}</p></div><div className="mt-5 grid gap-3"><div className="grid grid-cols-2 gap-3"><div className="rounded-lg bg-white/[0.035] p-3"><p className="text-[10px] uppercase tracking-wider text-slate-600">Manifest model</p><p className="text-xs text-cyan-100 mt-1 leading-relaxed">{registryEntry?.llmModel ?? agent.model}</p></div><div className="rounded-lg bg-white/[0.035] p-3"><p className="text-[10px] uppercase tracking-wider text-slate-600">Context window</p><p className="text-xs text-cyan-100 mt-1">{registryEntry?.contextWindow ?? "—"}</p></div></div><div className="rounded-lg bg-white/[0.035] p-3"><p className="text-[10px] uppercase tracking-wider text-slate-600">Runtime</p><p className="text-xs text-cyan-100 mt-1">{registryEntry?.runtime ?? agent.runtime}</p></div></div><div className="mt-5"><p className="text-[10px] uppercase tracking-wider text-slate-600 mb-2">Providers / tools</p><div className="flex flex-wrap gap-1.5">{(registryEntry?.allowedGoogleCloudServices ?? agent.tools).map((tool) => <span key={tool} className="px-2 py-1 rounded-md bg-white/[0.045] border border-white/[0.06] text-[11px] text-slate-400">{tool}</span>)}</div></div><div className="mt-auto pt-5 flex items-center gap-2 text-xs text-slate-600"><Circle className="w-3 h-3" />Resolved from twin/model-manifest.json</div></section>;
}

function RunQueue({ runs, onOpenWorkflows }: { runs: MockRun[]; onOpenWorkflows: () => void }) {
  return <section className="console-card overflow-hidden"><div className="p-5 sm:p-6 flex items-center justify-between border-b border-white/[0.07]"><div><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Execution queue</p><h2 className="text-lg font-semibold text-white mt-1">Current workstreams</h2></div><button onClick={onOpenWorkflows} className="text-xs text-cyan-300 hover:text-cyan-100 flex items-center gap-1">Open workflows <ChevronRight className="w-3.5 h-3.5" /></button></div><div className="divide-y divide-white/[0.06]">{runs.map((run) => <div key={run.id} className="p-4 sm:px-6 hover:bg-white/[0.018] transition-colors"><div className="flex items-start gap-3"><div className="w-8 h-8 rounded-lg bg-white/[0.045] grid place-items-center text-slate-400"><GitPullRequest className="w-4 h-4" /></div><div className="flex-1 min-w-0"><div className="flex flex-col sm:flex-row sm:items-center gap-2 justify-between"><div className="min-w-0"><p className="text-sm font-medium text-white truncate">{run.title}</p><p className="text-[11px] text-slate-500 mt-1 truncate">{run.repository} · {run.branch}</p></div><span className={`shrink-0 text-[10px] px-2 py-1 border rounded-full ${runStyles[run.status].className}`}>{runStyles[run.status].label}</span></div><div className="flex items-center gap-3 mt-3"><div className="h-1.5 flex-1 max-w-[240px] bg-white/[0.06] rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-cyan-400 to-violet-400 rounded-full" style={{ width: `${run.progress}%` }} /></div><span className="text-[11px] text-slate-500">{run.progress}% · {run.currentStage}</span></div></div></div></div>)}</div></section>;
}

function AgentTableRow({ agent, selected, onClick }: { agent: MockAgent; selected: boolean; onClick: () => void }) {
  const color = agentColors[agent.color];
  const status = statusStyles[agent.status];
  return <tr onClick={onClick} className={`cursor-pointer border-t border-white/[0.06] transition-colors ${selected ? "bg-cyan-400/[0.05]" : "hover:bg-white/[0.025]"}`}><td className="px-5 py-4"><div className="flex items-center gap-3"><span className="w-8 h-8 rounded-lg grid place-items-center font-bold text-[10px]" style={{ background: color.pale, color: color.solid }}>{agent.initials}</span><div><p className="font-medium text-white">{agent.name}</p><p className="text-xs text-slate-500 mt-0.5">{agent.role}</p></div></div></td><td className="px-5 py-4 text-slate-400">{agent.domain}</td><td className="px-5 py-4"><span className={`inline-flex gap-1.5 items-center ${status.text}`}><i className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />{status.label}</span></td><td className="px-5 py-4"><div className="flex items-center gap-2"><div className="w-16 h-1 rounded-full bg-white/[0.06] overflow-hidden"><div className="h-full rounded-full" style={{ width: `${agent.load}%`, background: color.solid }} /></div><span className="text-xs text-slate-500">{agent.load}%</span></div></td><td className="px-5 py-4 text-slate-500 max-w-[220px] truncate">{agent.lastAction}</td><td className="px-5 py-4"><ChevronRight className="w-4 h-4 text-slate-600" /></td></tr>;
}

function WorkflowRunCard({ run }: { run: MockRun }) {
  return <article className="rounded-xl p-3.5 bg-white/[0.035] border border-white/[0.07]"><span className={`inline-flex text-[10px] px-2 py-1 border rounded-full ${runStyles[run.status].className}`}>{runStyles[run.status].label}</span><h4 className="text-sm font-medium text-white mt-3 leading-snug">{run.title}</h4><p className="text-[11px] text-slate-600 mt-2">{run.repository}</p><div className="mt-4 flex justify-between text-[11px] text-slate-500"><span>{run.owner}</span><span>{run.progress}%</span></div></article>;
}

function PolicyRow({ policy, enabled, onToggle }: { policy: { id: string; label: string; description: string; enabled: boolean; icon: string }; enabled: boolean; onToggle: () => void }) {
  const icons = { container: Container, network: Network, key: KeyRound, user: UserRoundCheck };
  const Icon = icons[policy.icon as keyof typeof icons] ?? ShieldCheck;
  return <article className="console-card p-5 flex items-center gap-4"><div className="w-10 h-10 rounded-xl bg-rose-400/[0.09] grid place-items-center"><Icon className="w-5 h-5 text-rose-300" /></div><div className="flex-1"><h2 className="font-medium text-white">{policy.label}</h2><p className="text-sm text-slate-500 mt-1">{policy.description}</p></div><button onClick={onToggle} role="switch" aria-checked={enabled} className={`relative w-11 h-6 rounded-full transition-colors ${enabled ? "bg-cyan-400" : "bg-slate-700"}`}><span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`} /></button></article>;
}

function CoreAgentsPanel({ agents }: { agents: MockAgent[] }) {
  return (
    <section className="console-card p-4">
      <div className="flex items-center gap-2 text-sm text-slate-200">
        <LockKeyhole className="w-4 h-4 text-rose-300" />
        <span className="font-medium">Locked core</span>
      </div>
      <p className="text-[11px] text-slate-500 mt-1">Aegis and Echo are always present; mutations require cross-review.</p>
      <div className="mt-3 space-y-2">
        {agents.map((agent) => {
          const color = agentColors[agent.color];
          return (
            <div key={agent.id} className="flex items-center gap-3 rounded-lg bg-white/[0.03] border border-white/[0.06] px-3 py-2">
              <span className="w-8 h-8 rounded-lg grid place-items-center text-[10px] font-bold" style={{ background: color.pale, color: color.solid }}>{agent.initials}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-white truncate">{agent.name}</p>
                <p className="text-[11px] text-slate-500 truncate">{agent.role}</p>
              </div>
              <span className="text-[10px] uppercase tracking-wider text-rose-300">locked</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AgentLibraryView({
  templates,
  archive,
}: {
  templates: MockAgent[];
  archive: Array<{ archive_id: string; template_id: string; task_id: string; archived_at: string; post_mortem: { whatWorked: string[]; whatFailed: string[]; learningDelta: number } }>;
}) {
  return (
    <div className="mt-6 grid xl:grid-cols-2 gap-5">
      <section className="console-card p-5">
        <h3 className="font-semibold text-white">Templates ({templates.length})</h3>
        <p className="text-sm text-slate-500 mt-1">Reusable limb archetypes seeded from mock personas.</p>
        <div className="mt-4 space-y-2 max-h-[520px] overflow-y-auto">
          {templates.map((t) => (
            <article key={t.id} className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
              <div className="flex justify-between gap-2">
                <p className="text-sm font-medium text-white">{t.name}</p>
                <span className="text-[10px] text-slate-500 font-mono">{t.id}</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">{t.role}</p>
              <p className="text-[11px] text-slate-600 mt-2">{t.lastAction}</p>
            </article>
          ))}
          {templates.length === 0 && <p className="text-sm text-slate-500 py-8 text-center">No templates — start NIO API on :4000</p>}
        </div>
      </section>
      <section className="console-card p-5">
        <h3 className="font-semibold text-white">Archived runs ({archive.length})</h3>
        <p className="text-sm text-slate-500 mt-1">Post-mortem bundles from retired limb instances.</p>
        <div className="mt-4 space-y-2 max-h-[520px] overflow-y-auto">
          {archive.map((entry) => (
            <article key={entry.archive_id} className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
              <div className="flex justify-between gap-2">
                <p className="text-sm font-medium text-white">{entry.template_id}</p>
                <span className="text-[10px] text-slate-500">{new Date(entry.archived_at).toLocaleString("en-GB")}</span>
              </div>
              <p className="text-xs text-slate-500 mt-1 font-mono">{entry.task_id}</p>
              <p className="text-[11px] text-emerald-300 mt-2">Δ {entry.post_mortem.learningDelta} · {entry.post_mortem.whatWorked[0] ?? "No learnings"}</p>
            </article>
          ))}
          {archive.length === 0 && <p className="text-sm text-slate-500 py-8 text-center">No archived runs yet — complete a task to populate.</p>}
        </div>
      </section>
    </div>
  );
}
