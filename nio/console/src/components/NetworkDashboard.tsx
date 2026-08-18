"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  BrainCircuit,
  CircleDot,
  Filter,
  Network,
  Play,
  Search,
  Sparkles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  domainFilters,
  networkEdges,
  networkNodes,
  palette,
  taskPresets,
  type DomainId,
  type NetworkNode,
} from "@/data/network";

const API_URL = "/nio-api";

type TaskResponse = {
  coreNodeId: string;
  output: string;
  latencyMs: number;
  metadata: Record<string, unknown>;
};

function getPath(from: NetworkNode, to: NetworkNode, curved = false) {
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2;
  if (!curved) return `M ${from.x} ${from.y} L ${to.x} ${to.y}`;
  return `M ${from.x} ${from.y} Q ${midX + (from.y - to.y) * 0.1} ${midY + (to.x - from.x) * 0.1} ${to.x} ${to.y}`;
}

export default function NetworkDashboard() {
  const [selectedId, setSelectedId] = useState("neural-core");
  const [activeFilter, setActiveFilter] = useState<DomainId | "all">("all");
  const [search, setSearch] = useState("");
  const [zoom, setZoom] = useState(1);
  const [taskText, setTaskText] = useState("");
  const [isComplex, setIsComplex] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<string>("Select a node or run a task through the Neural Core.");
  const [lastResponse, setLastResponse] = useState<TaskResponse | null>(null);
  const [activeEdges, setActiveEdges] = useState<string[]>([]);

  const nodeById = useMemo(() => Object.fromEntries(networkNodes.map((node) => [node.id, node])), []);
  const selectedNode = nodeById[selectedId] ?? nodeById["neural-core"];

  const visibleNodes = useMemo(() => {
    const query = search.trim().toLowerCase();
    return networkNodes.filter((node) => {
      const matchesFilter = activeFilter === "all" || node.domain === activeFilter || node.kind === "core";
      const matchesSearch =
        query.length === 0 ||
        node.label.toLowerCase().includes(query) ||
        node.description.toLowerCase().includes(query);
      return matchesFilter && matchesSearch;
    });
  }, [activeFilter, search]);

  const visibleIds = new Set(visibleNodes.map((node) => node.id));

  function selectNode(nodeId: string) {
    setSelectedId(nodeId);
    const preset = taskPresets[nodeId];
    if (preset) {
      setTaskText(preset.taskDescription);
      setIsComplex(preset.isComplexWorkflow);
    }
    setActiveEdges(
      networkEdges
        .filter((edge) => edge.from === nodeId || edge.to === nodeId)
        .map((edge) => `${edge.from}-${edge.to}`),
    );
  }

  async function runTask() {
    if (!taskText.trim() || isRunning) return;
    setIsRunning(true);
    setResult("Routing task through middleware …");

    const preset = taskPresets[selectedId];
    const body = {
      taskDescription: taskText.trim(),
      isComplexWorkflow: isComplex,
      domainHint: preset?.domainHint,
      algorithmTag: preset?.algorithmTag,
      politenessTier: preset?.politenessTier ?? "neutral",
    };

    try {
      const response = await fetch(`${API_URL}/api/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as TaskResponse | { error?: string };
      if (!response.ok) {
        throw new Error("error" in data ? data.error : "Task execution failed");
      }
      const taskResponse = data as TaskResponse;
      setLastResponse(taskResponse);
      setResult(taskResponse.output);
      setActiveEdges(networkEdges.map((edge) => `${edge.from}-${edge.to}`));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not reach API";
      setResult(`API error: ${message}. Start the backend with npm start in the repo root.`);
      setLastResponse(null);
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#090b12]">
      <header className="sticky top-0 z-30 h-[72px] border-b border-white/[0.07] bg-[#090b12]/90 backdrop-blur-xl px-4 sm:px-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 via-orange-500 to-rose-500 grid place-items-center shadow-lg shadow-amber-950/30">
            <BrainCircuit className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-sm sm:text-base font-semibold text-white truncate">NEURAL INTELLIGENCE NETWORK</p>
            <p className="text-[10px] sm:text-[11px] uppercase tracking-[0.16em] text-slate-500 truncate">
              Cross-Domain Synthesis · {networkNodes.length} Nodes · {networkEdges.length} Links
            </p>
          </div>
        </div>

        <div className="hidden md:flex flex-1 max-w-xl mx-4 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search nodes, domains, algorithms …"
            className="console-input pl-10"
          />
        </div>

        <button onClick={() => selectNode("neural-core")} className="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-amber-400/30 bg-amber-400/10 text-amber-100 text-sm font-medium hover:bg-amber-400/15">
          <Sparkles className="w-4 h-4" />
          Master Summary
        </button>
      </header>

      <div className="grid lg:grid-cols-[240px_minmax(0,1fr)_340px] min-h-[calc(100vh-72px)]">
        <aside className="border-b lg:border-b-0 lg:border-r border-white/[0.07] bg-[#0c0f18] p-4">
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-slate-500 mb-4">
            <Filter className="w-3.5 h-3.5" />
            Domain Filter
          </div>
          <div className="space-y-2">
            {domainFilters.map((filter) => (
              <button
                key={filter.id}
                onClick={() => setActiveFilter(filter.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm transition-all ${
                  activeFilter === filter.id
                    ? "bg-white/[0.09] text-white"
                    : "text-slate-500 hover:text-slate-200 hover:bg-white/[0.04]"
                }`}
              >
                <span className="text-lg">{filter.icon}</span>
                <span className="flex-1">{filter.label}</span>
                <span className="text-xs text-slate-600">{filter.count}</span>
              </button>
            ))}
          </div>

          <div className="mt-8 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[11px] text-slate-500 space-y-2">
            <p><span className="text-slate-300">Hover</span> · preview</p>
            <p><span className="text-slate-300">Click</span> · inspect node</p>
            <p><span className="text-slate-300">Run task</span> · call API</p>
          </div>
        </aside>

        <section className="relative min-h-[520px] overflow-hidden">
          <div className="absolute inset-0 opacity-40 grid-pattern" />
          <div
            className="relative h-full min-h-[520px] transition-transform duration-300 origin-center"
            style={{ transform: `scale(${zoom})` }}
          >
            <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid meet">
              <defs>
                <filter id="node-glow">
                  <feGaussianBlur stdDeviation="1.1" result="blur" />
                  <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
                <radialGradient id="core-gradient">
                  <stop offset="0%" stopColor="#fde68a" stopOpacity="0.8" />
                  <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#1e1b4b" stopOpacity="0" />
                </radialGradient>
              </defs>
              <circle cx="50" cy="50" r="18" fill="url(#core-gradient)" opacity="0.7" />
              {networkEdges.map((edge) => {
                const from = nodeById[edge.from];
                const to = nodeById[edge.to];
                if (!from || !to || !visibleIds.has(from.id) || !visibleIds.has(to.id)) return null;
                const key = `${edge.from}-${edge.to}`;
                const active = activeEdges.includes(key);
                const color = palette[edge.color] ?? palette.slate;
                return (
                  <path
                    key={key}
                    d={getPath(from, to, true)}
                    fill="none"
                    stroke={color.line}
                    strokeWidth={active ? 0.55 : 0.22}
                    opacity={active ? 0.9 : 0.25}
                  />
                );
              })}
            </svg>

            {visibleNodes.map((node) => {
              const selected = node.id === selectedId;
              const color = palette[node.color] ?? palette.slate;
              const isCore = node.kind === "core";
              return (
                <motion.button
                  key={node.id}
                  onClick={() => selectNode(node.id)}
                  animate={selected ? { scale: [1, 1.05, 1] } : { scale: 1 }}
                  transition={selected ? { duration: 2, repeat: Infinity } : {}}
                  className="absolute -translate-x-1/2 -translate-y-1/2 z-10 text-center"
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                >
                  <span
                    className={`relative grid place-items-center rounded-full border ${
                      isCore ? "w-28 h-28 sm:w-32 sm:h-32" : "w-[68px] h-[68px] sm:w-[78px] sm:h-[78px]"
                    }`}
                    style={{
                      borderColor: color.border,
                      backgroundColor: color.fill,
                      boxShadow: selected ? `0 0 ${isCore ? 40 : 22}px ${color.glow}` : undefined,
                    }}
                  >
                    {isCore ? <Sparkles className="w-7 h-7 text-amber-100" /> : <CircleDot className="w-4 h-4" style={{ color: color.text }} />}
                    <span className={`absolute inset-x-1 bottom-2 text-[8px] sm:text-[9px] font-bold leading-tight whitespace-pre-line`} style={{ color: color.text }}>
                      {node.shortLabel}
                    </span>
                  </span>
                </motion.button>
              );
            })}
          </div>

          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-xl border border-white/10 bg-black/50 backdrop-blur px-3 py-2">
            <button onClick={() => setZoom((value) => Math.min(value + 0.1, 1.4))} className="p-1.5 rounded-lg hover:bg-white/10"><ZoomIn className="w-4 h-4" /></button>
            <span className="text-xs text-slate-400 w-12 text-center">{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom((value) => Math.max(value - 0.1, 0.7))} className="p-1.5 rounded-lg hover:bg-white/10"><ZoomOut className="w-4 h-4" /></button>
            <button onClick={() => setZoom(1)} className="px-2 py-1 text-[10px] uppercase tracking-wider text-slate-400 hover:text-white">Reset</button>
          </div>
        </section>

        <aside className="border-t lg:border-t-0 lg:border-l border-white/[0.07] bg-[#0c0f18] p-5 flex flex-col">
          <AnimatePresence mode="wait">
            <motion.div key={selectedNode.id} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{selectedNode.kind}</p>
                  <h2 className="text-xl font-semibold text-white mt-1">{selectedNode.label}</h2>
                </div>
                {selectedNode.sources !== undefined && (
                  <span className="px-2 py-1 rounded-full bg-white/5 text-[10px] text-slate-400">{selectedNode.sources} sources</span>
                )}
              </div>

              {selectedNode.tags && (
                <div className="flex flex-wrap gap-1.5 mt-4">
                  {selectedNode.tags.map((tag) => (
                    <span key={tag} className="px-2 py-1 rounded-md bg-white/5 border border-white/8 text-[11px] text-slate-400">{tag}</span>
                  ))}
                </div>
              )}

              <p className="text-sm leading-relaxed text-slate-400 mt-5">{selectedNode.description}</p>

              <div className="mt-6 space-y-3">
                <label className="text-[10px] uppercase tracking-wider text-slate-500">Task</label>
                <textarea
                  value={taskText}
                  onChange={(event) => setTaskText(event.target.value)}
                  rows={4}
                  className="console-input resize-none"
                  placeholder="Describe a task for the Neural Core …"
                />
                <label className="flex items-center gap-2 text-sm text-slate-400">
                  <input type="checkbox" checked={isComplex} onChange={(event) => setIsComplex(event.target.checked)} className="accent-cyan-400" />
                  Complex workflow (urgency wrapping)
                </label>
                <button onClick={() => void runTask()} disabled={isRunning || !taskText.trim()} className="primary-button w-full">
                  <Play className="w-4 h-4" />
                  {isRunning ? "Running …" : "Run through Neural Core"}
                </button>
              </div>

              <div className="mt-6 rounded-xl border border-white/8 bg-black/20 p-4">
                <p className="text-[10px] uppercase tracking-wider text-cyan-300">Response</p>
                <p className="text-sm text-slate-300 mt-2 break-words">{result}</p>
                {lastResponse && (
                  <p className="text-[11px] text-slate-500 mt-3">
                    {lastResponse.coreNodeId} · {lastResponse.latencyMs}ms
                  </p>
                )}
              </div>
            </motion.div>
          </AnimatePresence>

          <div className="mt-auto pt-5 flex items-center gap-2 text-[11px] text-slate-600">
            <Network className="w-3.5 h-3.5" />
            API: {API_URL}
          </div>
        </aside>
      </div>
    </main>
  );
}
