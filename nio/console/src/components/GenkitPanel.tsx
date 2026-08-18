"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  Beaker,
  CheckCircle2,
  Copy,
  Cpu,
  Database,
  Gauge,
  Play,
  Radio,
  Sparkles,
  Terminal,
  Workflow,
  XCircle,
} from "lucide-react";

interface StatusResponse {
  runtime: { projectId: string | null; location: string; telemetry: boolean; model: string };
  flows: { name: string; description: string; input: string; output: string }[];
  retrievers: { name: string; description: string }[];
  evaluators: { name: string; description: string; dataset: string }[];
}

interface FlowResult {
  degraded: boolean;
  reason?: string;
  latencyMs: number;
  output: {
    behavioralLedgerId: number;
    whatWorked: string[];
    whatFailed: string[];
    rootCause: string | null;
    strategyUpdate: string | null;
    learningDelta: number;
    shouldRetrain: boolean;
  };
}

interface HistoryEntry {
  id: string;
  at: number;
  taskType: string;
  outcome: string;
  delta: number;
  ledgerId: number;
  degraded: boolean;
  latencyMs: number;
}

const SAMPLE_INPUTS: Array<{ label: string; body: unknown }> = [
  {
    label: "Passed · clean PR review",
    body: {
      eventId: Math.floor(2000 + Math.random() * 8000),
      taskId: `task-${Date.now()}`,
      taskType: "pr-review",
      outcome: "passed",
      score: 91,
      agentsUsed: [
        { agentId: "c-reviewer", role: "specialist", performanceScore: 94, executionTimeMs: 8200 },
        { agentId: "python-tester", role: "worker", performanceScore: 88, executionTimeMs: 14300 },
      ],
      evidence: { logs: ["build ok"], artifacts: ["coverage.html"], errors: [] },
    },
  },
  {
    label: "Revised · integration timeout",
    body: {
      eventId: Math.floor(2000 + Math.random() * 8000),
      taskId: `task-${Date.now()}`,
      taskType: "integration-test",
      outcome: "revised",
      score: 64,
      agentsUsed: [{ agentId: "python-tester", role: "worker", performanceScore: 58, executionTimeMs: 41000 }],
      evidence: { logs: ["pytest run"], artifacts: [], errors: ["timeout on suite B"] },
    },
  },
  {
    label: "Escalated · secret leak",
    body: {
      eventId: Math.floor(2000 + Math.random() * 8000),
      taskId: `task-${Date.now()}`,
      taskType: "security-audit",
      outcome: "escalated",
      score: 28,
      agentsUsed: [{ agentId: "security-auditor", role: "specialist", performanceScore: 40, executionTimeMs: 6500 }],
      evidence: { logs: [], artifacts: [], errors: ["hardcoded secret in config.py"] },
      humanFeedback: { decision: "rejected", reasoning: "must never ship a hardcoded secret" },
    },
  },
];

function AnimatedDelta({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<number>(0);

  useEffect(() => {
    const start = performance.now();
    const from = ref.current;
    const to = value;
    const duration = 650;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = from + (to - from) * eased;
      setDisplay(Number(next.toFixed(1)));
      if (t < 1) raf = requestAnimationFrame(tick);
      else ref.current = to;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  const tone =
    display > 0 ? "text-emerald-300" : display < 0 ? "text-rose-300" : "text-slate-300";
  const sign = display > 0 ? "+" : "";
  return <span className={`font-mono tabular-nums ${tone}`}>{sign}{display.toFixed(1)}</span>;
}

export default function GenkitPanel() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [sampleIndex, setSampleIndex] = useState(0);
  const [lastResult, setLastResult] = useState<FlowResult | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/genkit/status")
      .then((r) => r.json())
      .then((data: StatusResponse) => {
        if (cancelled) return;
        setStatus(data);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setStatusError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const runSample = async () => {
    const sample = SAMPLE_INPUTS[sampleIndex];
    setRunning(true);
    setLastResult(null);
    try {
      const response = await fetch("/api/genkit/post-mortem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sample.body),
      });
      const data = (await response.json()) as FlowResult;
      setLastResult(data);
      const entry: HistoryEntry = {
        id: `h-${Date.now()}`,
        at: Date.now(),
        taskType: (sample.body as { taskType: string }).taskType,
        outcome: (sample.body as { outcome: string }).outcome,
        delta: data.output.learningDelta,
        ledgerId: data.output.behavioralLedgerId,
        degraded: data.degraded,
        latencyMs: data.latencyMs,
      };
      setHistory((prev) => [entry, ...prev].slice(0, 6));
    } finally {
      setRunning(false);
    }
  };

  const copyLedgerId = (entryId: string, ledgerId: number) => {
    navigator.clipboard.writeText(`ledger:${ledgerId}`);
    setCopiedId(entryId);
    setTimeout(() => setCopiedId(null), 1200);
  };

  const flowCount = status?.flows.length ?? 0;
  const retrieverCount = status?.retrievers.length ?? 0;
  const evaluatorCount = status?.evaluators.length ?? 0;

  const deltaBarWidth = useMemo(() => {
    if (!lastResult) return 0;
    const v = Math.max(-30, Math.min(30, lastResult.output.learningDelta));
    return Math.abs(v) / 30;
  }, [lastResult]);

  const deltaBarColor = useMemo(() => {
    if (!lastResult) return "bg-slate-500";
    const v = lastResult.output.learningDelta;
    if (v > 5) return "bg-gradient-to-r from-emerald-400 to-teal-300";
    if (v > 0) return "bg-emerald-400/70";
    if (v === 0) return "bg-slate-500";
    if (v > -5) return "bg-amber-400/70";
    return "bg-gradient-to-r from-rose-500 to-rose-400";
  }, [lastResult]);

  return (
    <div className="space-y-5">
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-400/10 border border-emerald-400/20 text-[10px] uppercase tracking-[0.18em] text-emerald-200">
            <Sparkles className="w-3.5 h-3.5" /> Phase 1 · framework layer
          </div>
          <h1 className="mt-3 text-2xl sm:text-3xl font-semibold text-white tracking-tight">
            GenKit runtime
          </h1>
          <p className="mt-1.5 text-sm text-slate-400 max-w-2xl leading-relaxed">
            Flows wrap the existing autodidactic implementation; the trace viewer and Cloud Trace exporter
            light up when <code className="px-1.5 py-0.5 rounded bg-white/5 text-emerald-200 text-[12px]">genkit start</code> runs locally or telemetry is enabled in production.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setSampleIndex((i) => (i + 1) % SAMPLE_INPUTS.length)}
            className="px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs text-slate-200 hover:bg-white/[0.07] transition-colors"
          >
            Sample: {SAMPLE_INPUTS[sampleIndex].label}
          </button>
          <button
            onClick={runSample}
            disabled={running || !status}
            className="primary-button"
          >
            <Play className="w-4 h-4" />
            {running ? "Running flow…" : "Run echoPostMortem"}
          </button>
        </div>
      </header>

      {/* Runtime strip */}
      <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <RuntimeChip
          icon={<Radio className="w-4 h-4" />}
          label="Runtime"
          value={status ? (status.runtime.projectId ?? "local · no ADC") : statusError ? "unreachable" : "probing…"}
          accent={status ? (status.runtime.projectId ? "emerald" : "amber") : statusError ? "rose" : "slate"}
          pulse={Boolean(status)}
        />
        <RuntimeChip
          icon={<Cpu className="w-4 h-4" />}
          label="Default model"
          value={status?.runtime.model ?? "—"}
          accent="cyan"
        />
        <RuntimeChip
          icon={<Activity className="w-4 h-4" />}
          label="Cloud Trace"
          value={status ? (status.runtime.telemetry ? "exporting" : "disabled") : "—"}
          accent={status?.runtime.telemetry ? "emerald" : "slate"}
        />
        <RuntimeChip
          icon={<Beaker className="w-4 h-4" />}
          label="Actions registered"
          value={`${flowCount} flow · ${retrieverCount} retr · ${evaluatorCount} eval`}
          accent="violet"
        />
      </section>

      {/* Flow result */}
      <section className="console-card p-5 sm:p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <Workflow className="w-4 h-4 text-emerald-300" />
            <span className="font-medium">Latest flow result</span>
          </div>
          {lastResult && (
            <span className={`text-[11px] px-2 py-1 rounded-md border ${lastResult.degraded ? "text-amber-200 bg-amber-400/10 border-amber-400/20" : "text-emerald-200 bg-emerald-400/10 border-emerald-400/20"}`}>
              {lastResult.degraded ? "preview (no ledger row)" : "persisted"} · {lastResult.latencyMs} ms
            </span>
          )}
        </div>

        <AnimatePresence mode="wait">
          {lastResult ? (
            <motion.div
              key={lastResult.output.behavioralLedgerId + lastResult.latencyMs}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-5 grid lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-5"
            >
              <div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Learning delta</span>
                  <span className="text-3xl sm:text-4xl font-semibold">
                    <AnimatedDelta value={lastResult.output.learningDelta} />
                  </span>
                </div>
                <div className="mt-3 h-2 rounded-full bg-white/[0.05] overflow-hidden relative">
                  <motion.div
                    className={`absolute inset-y-0 left-0 ${deltaBarColor}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.max(4, deltaBarWidth * 100)}%` }}
                    transition={{ duration: 0.7, ease: "easeOut" }}
                  />
                </div>
                <p className="mt-3 text-xs text-slate-500 leading-relaxed">
                  {lastResult.output.shouldRetrain
                    ? "Retrain recommended — score below threshold on this task family."
                    : lastResult.output.learningDelta >= 0
                    ? "Positive delta — the Twin's strategy update aligns with the observed outcome."
                    : "Negative delta — the Twin should avoid repeating this routing pattern."}
                </p>

                <dl className="mt-5 grid grid-cols-2 gap-3 text-xs">
                  <Stat label="Ledger id" value={lastResult.output.behavioralLedgerId ? `#${lastResult.output.behavioralLedgerId}` : "—"} />
                  <Stat label="Root cause" value={lastResult.output.rootCause ?? "none"} />
                  <Stat label="Strategy" value={lastResult.output.strategyUpdate ?? "no change"} />
                  <Stat label="Retrain" value={lastResult.output.shouldRetrain ? "yes" : "no"} />
                </dl>
              </div>

              <div className="space-y-3">
                <ResultList title="What worked" items={lastResult.output.whatWorked} tone="emerald" />
                <ResultList title="What failed" items={lastResult.output.whatFailed} tone="rose" />
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="mt-6 rounded-xl border border-dashed border-white/[0.08] p-8 text-center text-sm text-slate-500"
            >
              Pick a sample and press <span className="text-emerald-200">Run echoPostMortem</span>. The flow wraps <code className="px-1.5 py-0.5 rounded bg-white/5 text-emerald-200">executePostMortem</code> with schema validation and span tracing.
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* Registered actions + history */}
      <section className="grid lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-5">
        <div className="console-card p-5">
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <Gauge className="w-4 h-4 text-violet-300" />
            <span className="font-medium">Registered actions</span>
          </div>
          <ul className="mt-4 space-y-3 text-sm">
            {status?.flows.map((flow) => (
              <ActionRow
                key={flow.name}
                kind="flow"
                name={flow.name}
                description={flow.description}
                meta={`${flow.input} → ${flow.output}`}
              />
            ))}
            {status?.retrievers.map((retriever) => (
              <ActionRow
                key={retriever.name}
                kind="retriever"
                name={retriever.name}
                description={retriever.description}
              />
            ))}
            {status?.evaluators.map((evaluator) => (
              <ActionRow
                key={evaluator.name}
                kind="evaluator"
                name={evaluator.name}
                description={evaluator.description}
                meta={`dataset · ${evaluator.dataset}`}
              />
            ))}
            {!status && (
              <li className="text-xs text-slate-500">Loading action registry…</li>
            )}
          </ul>
        </div>

        <div className="console-card p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-slate-200">
              <Database className="w-4 h-4 text-cyan-300" />
              <span className="font-medium">Invocation log</span>
            </div>
            <span className="text-[11px] text-slate-500">in-memory</span>
          </div>
          <ul className="mt-4 space-y-2">
            {history.length === 0 && (
              <li className="text-xs text-slate-500 py-6 text-center">No invocations yet.</li>
            )}
            {history.map((entry) => (
              <li
                key={entry.id}
                className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.03] border border-white/[0.06] px-3 py-2 text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {entry.delta >= 0 ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300 flex-shrink-0" />
                  ) : (
                    <XCircle className="w-3.5 h-3.5 text-rose-300 flex-shrink-0" />
                  )}
                  <span className="text-slate-200 truncate">{entry.taskType}</span>
                  <span className="text-slate-500">· {entry.outcome}</span>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="font-mono tabular-nums text-slate-300">
                    {entry.delta > 0 ? "+" : ""}{entry.delta.toFixed(1)}
                  </span>
                  <span className="text-slate-500 tabular-nums">{entry.latencyMs} ms</span>
                  {entry.ledgerId > 0 ? (
                    <button
                      onClick={() => copyLedgerId(entry.id, entry.ledgerId)}
                      className="text-slate-400 hover:text-cyan-200 transition-colors"
                      title="Copy ledger reference"
                    >
                      {copiedId === entry.id ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  ) : (
                    <span className="text-slate-600" title="Preview only — no ledger row">∅</span>
                  )}
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-start gap-2 text-xs text-slate-500">
            <Terminal className="w-4 h-4 mt-0.5 text-slate-400 flex-shrink-0" />
            <p className="leading-relaxed">
              Run the evaluator offline with <code className="px-1.5 py-0.5 rounded bg-white/5 text-slate-200">npx genkit eval:run nexus/postMortemAlignment --dataset genkit-flows/datasets/post-mortem-samples.json --flow echoPostMortem</code>.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function RuntimeChip({
  icon,
  label,
  value,
  accent,
  pulse,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent: "emerald" | "amber" | "rose" | "slate" | "cyan" | "violet";
  pulse?: boolean;
}) {
  const accents: Record<typeof accent, { ring: string; text: string; dot: string }> = {
    emerald: { ring: "border-emerald-400/25", text: "text-emerald-200", dot: "bg-emerald-400" },
    amber: { ring: "border-amber-400/25", text: "text-amber-200", dot: "bg-amber-400" },
    rose: { ring: "border-rose-400/25", text: "text-rose-200", dot: "bg-rose-400" },
    slate: { ring: "border-white/[0.08]", text: "text-slate-300", dot: "bg-slate-500" },
    cyan: { ring: "border-cyan-400/25", text: "text-cyan-200", dot: "bg-cyan-400" },
    violet: { ring: "border-violet-400/25", text: "text-violet-200", dot: "bg-violet-400" },
  };
  const a = accents[accent];
  return (
    <div className={`console-card px-4 py-3 flex items-center gap-3 border ${a.ring}`}>
      <div className={`w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center ${a.text}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500 flex items-center gap-1.5">
          {pulse && <span className={`w-1.5 h-1.5 rounded-full ${a.dot} animate-pulse`} />}
          {label}
        </div>
        <div className={`text-sm font-medium truncate ${a.text}`}>{value}</div>
      </div>
    </div>
  );
}

function ActionRow({
  kind,
  name,
  description,
  meta,
}: {
  kind: "flow" | "retriever" | "evaluator";
  name: string;
  description: string;
  meta?: string;
}) {
  const kindStyles = {
    flow: "bg-emerald-400/10 text-emerald-200 border-emerald-400/20",
    retriever: "bg-cyan-400/10 text-cyan-200 border-cyan-400/20",
    evaluator: "bg-violet-400/10 text-violet-200 border-violet-400/20",
  } as const;
  return (
    <li className="rounded-lg bg-white/[0.025] border border-white/[0.06] p-3 hover:border-white/[0.12] transition-colors">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[13px] text-white">{name}</span>
        <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border ${kindStyles[kind]}`}>{kind}</span>
      </div>
      <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">{description}</p>
      {meta && <p className="mt-2 text-[11px] text-slate-500 font-mono">{meta}</p>}
    </li>
  );
}

function ResultList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "emerald" | "rose";
}) {
  const dot = tone === "emerald" ? "bg-emerald-400" : "bg-rose-400";
  const heading = tone === "emerald" ? "text-emerald-200" : "text-rose-200";
  return (
    <div className="rounded-xl bg-white/[0.025] border border-white/[0.06] p-3.5">
      <div className={`text-[10px] uppercase tracking-[0.18em] ${heading}`}>{title}</div>
      <ul className="mt-2.5 space-y-1.5 text-xs text-slate-300">
        {items.length === 0 && <li className="text-slate-600">—</li>}
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${dot} mt-1.5 flex-shrink-0`} />
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/[0.025] border border-white/[0.06] px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 text-[12px] text-slate-200 leading-snug break-words">{value}</div>
    </div>
  );
}
