"use client";

import { useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Gauge,
  GitBranch,
  Keyboard,
  Layers,
  Radio,
  TerminalSquare,
  Zap,
} from "lucide-react";
import { ApolloDeck } from "@/apollo/ApolloDeck";
import { ApolloOrb } from "@/apollo/ApolloOrb";
import { NeuralGraph } from "@/apollo/NeuralGraph";
import { HybridTerminal } from "@/apollo/Terminal";
import { NODE_CATEGORY_STYLE, PALETTE, POOL_ENDPOINTS, POOL_PROVIDERS } from "@/apollo/catalog";
import { selectActiveModel, useApolloStore } from "@/apollo/store";
import { Badge, MiniBar } from "@/apollo/ui";
import { ORB_STATE_STYLE } from "@/apollo/catalog";

export default function ApolloStagePage() {
  const orbState = useApolloStore((s) => s.orbState);
  const router = useApolloStore((s) => s.router);
  const config = useApolloStore((s) => s.config);
  const task = useApolloStore((s) => s.task);
  const nodes = useApolloStore((s) => s.nodes);
  const activeModel = useApolloStore(selectActiveModel);
  const setDeckOpen = useApolloStore((s) => s.setDeckOpen);
  const setTerminalOpen = useApolloStore((s) => s.setTerminalOpen);
  const terminalOpen = useApolloStore((s) => s.terminalOpen);
  const deckOpen = useApolloStore((s) => s.deckOpen);
  const runCommand = useApolloStore((s) => s.runCommand);
  const log = useApolloStore((s) => s.log);
  const booted = useRef(false);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    log({
      origin: "NIO_CORE",
      level: "INFO",
      message: `Apollo core online · ${POOL_PROVIDERS} FreeLLMAPI providers · ${POOL_ENDPOINTS} endpoints indexed · primary ${config.primaryModel}.`,
    });
  }, [log, config.primaryModel]);

  const toggleDeck = useCallback(() => setDeckOpen(!useApolloStore.getState().deckOpen), [setDeckOpen]);
  const toggleTerminal = useCallback(
    () => setTerminalOpen(!useApolloStore.getState().terminalOpen),
    [setTerminalOpen],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable === true;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggleDeck();
        return;
      }
      if (typing) return;
      if (event.key === "`" || (event.ctrlKey && event.key === "t")) {
        event.preventDefault();
        toggleTerminal();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleDeck, toggleTerminal]);

  const stateStyle = ORB_STATE_STYLE[orbState];
  const quota = Math.round(router.primaryQuotaPercent);
  const modeTone = router.mode === "FAILOVER" ? "amber" : router.mode === "EXHAUSTED" ? "crimson" : "emerald";
  const failover = router.mode !== "PRIMARY";

  return (
    <div className="apollo-stage relative flex h-[100svh] min-h-[640px] flex-col overflow-hidden bg-[#05070d] text-slate-200">
      {/* ------------------------------------------------------------ header */}
      <header className="relative z-30 flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] bg-[#05070d]/80 px-3 py-2 backdrop-blur-xl sm:px-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className="grid h-7 w-7 place-items-center rounded-lg border"
              style={{ borderColor: `${stateStyle.color}55`, background: `${stateStyle.color}14`, color: stateStyle.color }}
            >
              <GitBranch size={13} />
            </span>
            <div>
              <div className="text-[12.5px] font-semibold tracking-[0.12em] text-slate-100">NIO · APOLLO</div>
              <div className="font-mono text-[8.5px] uppercase tracking-[0.24em] text-slate-400">
                neural orchestration stage
              </div>
            </div>
          </div>
          <span className="hidden h-6 w-px bg-white/10 sm:block" />
          <div className="hidden items-center gap-1.5 sm:flex">
            <Badge tone={modeTone} dot>{router.mode}</Badge>
            <Badge tone="cyan">{activeModel.name}</Badge>
            <Badge tone="slate">{nodes.length} nodes</Badge>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <div className="hidden items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-2 py-1 lg:flex">
            <span className="font-mono text-[8.5px] uppercase tracking-[0.16em] text-slate-400">quota</span>
            <div className="w-16">
              <MiniBar value={quota} color={quota > 50 ? PALETTE.emerald : quota > 15 ? PALETTE.amber : PALETTE.crimson} />
            </div>
            <span className="font-mono text-[10px] tabular-nums text-slate-300">{quota}%</span>
          </div>
          <button
            type="button"
            onClick={toggleTerminal}
            aria-pressed={terminalOpen}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-300 transition-colors hover:border-emerald-400/40 hover:text-emerald-200"
          >
            <TerminalSquare size={11} /> terminal
            <kbd className="hidden rounded border border-white/10 px-1 text-[8px] text-slate-400 sm:inline">`</kbd>
          </button>
          <button
            type="button"
            onClick={toggleDeck}
            aria-pressed={deckOpen}
            className="flex items-center gap-1.5 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-cyan-200 transition-colors hover:bg-cyan-400/20"
          >
            <Layers size={11} /> deck
            <kbd className="hidden rounded border border-cyan-400/20 px-1 text-[8px] text-cyan-300/70 sm:inline">⌘K</kbd>
          </button>
          <Link
            href="/ops"
            className="hidden rounded-lg border border-white/10 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-400 transition-colors hover:border-white/25 hover:text-slate-200 md:flex md:items-center md:gap-1.5"
          >
            ops grid <ArrowRight size={10} />
          </Link>
        </div>
      </header>

      {/* failover ribbon */}
      <div className="relative z-20">
        <div
          className={`absolute left-0 right-0 top-0 border-b border-amber-400/25 bg-amber-400/[0.07] transition-transform duration-500 ${
            failover ? "translate-y-0" : "-translate-y-full"
          }`}
          aria-live="polite"
        >
          <div className="flex flex-wrap items-center gap-2 px-3 py-1.5 sm:px-4">
            <span className="flex items-center gap-1.5 font-mono text-[9.5px] uppercase tracking-[0.18em] text-amber-300">
              <Zap size={11} /> failover active
            </span>
            <span className="text-[11px] text-amber-100/90">
              {config.primaryModel} quota spent — answering through <strong className="font-semibold">{activeModel.name}</strong> ({activeModel.provider}).
            </span>
            {router.lastHandoffNote && (
              <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-amber-300/60">
                · context handoff attached ({router.lastHandoffNote.length} chars)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- stage */}
      <main className="relative min-h-0 flex-1">
        <NeuralGraph>
          <div className="absolute inset-0 z-[5] grid place-items-center">
            <ApolloOrb />
          </div>
        </NeuralGraph>

        {/* corner telemetry */}
        <div className="apollo-hud pointer-events-none absolute left-3 top-3 z-20 hidden flex-col gap-1.5 sm:flex">
          <TelemetryChip icon={<Radio size={10} />} label="orb" value={stateStyle.label} accent={stateStyle.color} />
          <TelemetryChip icon={<Activity size={10} />} label="latency" value={`${42} ms`} />
          <TelemetryChip
            icon={<Zap size={10} />}
            label="pool"
            value={config.freeLLMRouting.enabled ? `${POOL_PROVIDERS} · ${POOL_ENDPOINTS}` : "disabled"}
            accent={config.freeLLMRouting.enabled ? PALETTE.emerald : undefined}
          />
        </div>

        <div className="apollo-hud pointer-events-none absolute right-3 top-3 z-20 hidden flex-col items-end gap-1.5 sm:flex">
          <TelemetryChip icon={<Gauge size={10} />} label="swaps" value={String(router.failoverCount)} accent={router.failoverCount > 0 ? PALETTE.amber : undefined} />
          <TelemetryChip icon={<Keyboard size={10} />} label="hotkeys" value="⌘K · `" />
        </div>

        {/* legend */}
        <div className="apollo-legend pointer-events-none absolute bottom-2 left-1/2 z-20 hidden -translate-x-1/2 items-center gap-3 rounded-full border border-white/[0.06] bg-[#05080f]/70 px-3 py-1 font-mono text-[8.5px] uppercase tracking-[0.16em] text-slate-400 backdrop-blur md:flex">
          {[
            ["dispatch", PALETTE.cyan],
            ["result", PALETTE.emerald],
            ["handoff", PALETTE.amber],
            ["memory", PALETTE.magenta],
          ].map(([label, color]) => (
            <span key={label} className="flex items-center gap-1.5">
              <span className="h-1 w-4 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
              {label}
            </span>
          ))}
        </div>
      </main>

      {/* ------------------------------------------------------------ footer */}
      {/* Reserve a floor: the task rail switches to a 4-row step list once a task
          is live, and the footer must never squash it into the page edge. */}
      <footer className="relative z-20 grid min-h-[132px] shrink-0 items-stretch gap-2 border-t border-white/[0.06] bg-[#05070d]/85 p-2.5 backdrop-blur-xl lg:grid-cols-[1.35fr_1fr] sm:p-3">
        <TaskRail />

        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-1.5">
            {[
              { label: "/spawn inference", tone: "cyan" as const },
              { label: "/failover simulate", tone: "amber" as const },
              { label: "/router status", tone: "emerald" as const },
              { label: "/sandbox exec ls", tone: "slate" as const },
            ].map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => {
                  setTerminalOpen(true);
                  void runCommand(action.label);
                }}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 font-mono text-[9.5px] text-slate-300 transition-colors hover:border-cyan-400/40 hover:text-cyan-200"
              >
                {action.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {nodes.slice(0, 8).map((node) => (
              <span
                key={node.id}
                className="flex items-center gap-1 rounded border border-white/[0.06] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[8.5px] text-slate-400"
                title={`${node.label} · ${node.category}`}
              >
                <span
                  className="h-1 w-1 rounded-full"
                  style={{ background: NODE_CATEGORY_STYLE[node.category].color }}
                />
                {NODE_CATEGORY_STYLE[node.category].short.toLowerCase()}
              </span>
            ))}
          </div>
        </div>
      </footer>

      <ApolloDeck />
      <HybridTerminal />
    </div>
  );
}

/* -------------------------------------------------------------------- */

function TelemetryChip({
  icon,
  label,
  value,
  accent = "#94a3b8",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <span className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-[#05080f]/70 px-2 py-1 backdrop-blur">
      <span style={{ color: accent }}>{icon}</span>
      <span className="font-mono text-[8.5px] uppercase tracking-[0.16em] text-slate-400">{label}</span>
      <span className="font-mono text-[10px] text-slate-300">{value}</span>
    </span>
  );
}

function TaskRail() {
  const task = useApolloStore((s) => s.task);
  const nodes = useApolloStore((s) => s.nodes);

  if (!task) {
    return (
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] px-3 py-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-slate-400">task rail</span>
          <Badge tone="slate">idle</Badge>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
          Ask Apollo something in the terminal (or hit a quick command) — the orb turns violet, an axon fires, the
          target node streams, and the answer returns through a synthesising pulse.
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1 font-mono text-[8.5px] uppercase tracking-[0.14em] text-slate-400">
          <span className="rounded border border-white/[0.06] px-1.5 py-0.5">{nodes.length} nodes online</span>
          <span className="rounded border border-white/[0.06] px-1.5 py-0.5">
            {Object.keys(ORB_STATE_STYLE).length} orb states
          </span>
          <span className="rounded border border-white/[0.06] px-1.5 py-0.5">
            {Object.keys(NODE_CATEGORY_STYLE).length} node kinds
          </span>
          <span className="rounded border border-white/[0.06] px-1.5 py-0.5">4 impulse kinds</span>
        </div>
      </div>
    );
  }

  const done = task.steps.filter((step) => step.status === "DONE").length;
  const pct = Math.round((done / task.steps.length) * 100);

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono text-[9px] uppercase tracking-[0.22em] text-slate-400">
          task · {task.label}
        </span>
        <Badge tone={pct === 100 ? "emerald" : "violet"}>{pct}%</Badge>
      </div>
      <div className="mt-1.5">
        <MiniBar value={pct} color={pct === 100 ? PALETTE.emerald : PALETTE.violet} />
      </div>
      <ol className="mt-1.5 grid gap-1 sm:grid-cols-2">
        {task.steps.map((step) => (
          <li key={step.id} className="flex items-center gap-1.5 font-mono text-[9px] text-slate-400">
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                step.status === "DONE"
                  ? "bg-emerald-400"
                  : step.status === "RUNNING"
                    ? "bg-violet-400 pulse-dot"
                    : step.status === "FAILED"
                      ? "bg-rose-400"
                      : "bg-slate-700"
              }`}
            />
            <span className={`truncate ${step.status === "RUNNING" ? "text-violet-200" : ""}`}>{step.label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
