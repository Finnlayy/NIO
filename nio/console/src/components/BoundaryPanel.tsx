"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Lock,
  RotateCcw,
  ShieldCheck,
  ShieldHalf,
  Sparkles,
  Terminal,
  Wand2,
  XCircle,
} from "lucide-react";
import {
  applyLimbManifestPatch,
  auditLine,
  CORE_AGENT_IDS,
  validateManifestMutation,
  type ManifestRegistry,
  type RegistryAgent,
  type ValidationVerdict,
} from "@/lib/autodidactic/limb-boundary";
import { CANNED_ATTEMPTS, INITIAL_REGISTRY, type CannedAttempt } from "@/lib/autodidactic/limb-boundary.test-data";
import {
  applyManifestProposal,
  proposeManifestMutation,
  submitCrossReview,
} from "@/lib/nio-client";
import type { ManifestProposal } from "@/lib/manifest-types";

interface LogEntry {
  id: string;
  at: number;
  label: string;
  path: string;
  verdict: ValidationVerdict;
  allowed: boolean;
  proposalId?: string;
  crossReviewPending?: boolean;
}

interface ArcSegment {
  agent: RegistryAgent;
  startAngle: number;
  endAngle: number;
}

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, rOuter: number, rInner: number, start: number, end: number) {
  const p1 = polar(cx, cy, rOuter, start);
  const p2 = polar(cx, cy, rOuter, end);
  const p3 = polar(cx, cy, rInner, end);
  const p4 = polar(cx, cy, rInner, start);
  const largeArc = end - start > 180 ? 1 : 0;
  return `M ${p1.x} ${p1.y} A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${p2.x} ${p2.y} L ${p3.x} ${p3.y} A ${rInner} ${rInner} 0 ${largeArc} 0 ${p4.x} ${p4.y} Z`;
}

function useGoogleFonts() {
  useEffect(() => {
    const existing = document.getElementById("nexus-boundary-fonts");
    if (existing) return;
    const link = document.createElement("link");
    link.id = "nexus-boundary-fonts";
    link.rel = "stylesheet";
    link.href =
      "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap";
    document.head.appendChild(link);
  }, []);
}

export default function BoundaryPanel() {
  useGoogleFonts();

  const [registry, setRegistry] = useState<ManifestRegistry>(INITIAL_REGISTRY);
  const [selectedLimbId, setSelectedLimbId] = useState<string | null>("pyra-python-tester");
  const [log, setLog] = useState<LogEntry[]>([]);
  const [activeStamp, setActiveStamp] = useState<{ allowed: boolean; path: string; verdict: ValidationVerdict; attemptId: string } | null>(null);
  const [recentlyMutatedId, setRecentlyMutatedId] = useState<string | null>(null);
  const [pendingProposal, setPendingProposal] = useState<ManifestProposal | null>(null);
  const stampTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const glowTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const limbs = useMemo(() => registry.agents.filter((a) => a.kind === "limb"), [registry]);
  const cores = useMemo(() => registry.agents.filter((a) => a.kind === "core"), [registry]);
  const selectedAgent = useMemo(
    () => registry.agents.find((a) => a.id === selectedLimbId) ?? null,
    [registry, selectedLimbId]
  );

  const arcs: ArcSegment[] = useMemo(() => {
    const gap = 3;
    const slice = 360 / Math.max(1, limbs.length);
    return limbs.map((agent, i) => ({
      agent,
      startAngle: i * slice + gap / 2,
      endAngle: (i + 1) * slice - gap / 2,
    }));
  }, [limbs]);

  const runAttempt = async (attempt: CannedAttempt) => {
    const verdict = validateManifestMutation(registry, attempt.request);
    const needsCrossReview =
      attempt.request.target === "core" ||
      attempt.request.target === "policy" ||
      (attempt.request.agentId ? CORE_AGENT_IDS.has(attempt.request.agentId) : false);

    let proposalId: string | undefined;
    let crossReviewPending = false;

    try {
      const { proposal, canApply } = await proposeManifestMutation({
        target: attempt.request.target,
        agentId: attempt.request.agentId,
        op: attempt.request.op,
        value: attempt.request.value,
        reason: attempt.request.reason,
        evidence: attempt.request.evidence,
        boundaryVerdict: {
          allowed: verdict.allowed,
          violations: verdict.violations,
          warnings: verdict.warnings,
          path: verdict.path,
        },
      });
      proposalId = proposal.proposal_id;
      crossReviewPending = proposal.requires_cross_review && proposal.review_verdict === "pending";
      if (crossReviewPending) setPendingProposal(proposal);
    } catch {
      // API offline — local-only sandbox
    }

    const entry: LogEntry = {
      id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      at: Date.now(),
      label: attempt.label,
      path: verdict.path,
      verdict,
      allowed: verdict.allowed && !needsCrossReview,
      proposalId,
      crossReviewPending: needsCrossReview || crossReviewPending,
    };
    setLog((prev) => [entry, ...prev].slice(0, 8));
    setActiveStamp({
      allowed: needsCrossReview ? false : verdict.allowed,
      path: verdict.path,
      verdict,
      attemptId: attempt.id,
    });
    if (stampTimeout.current) clearTimeout(stampTimeout.current);
    stampTimeout.current = setTimeout(() => setActiveStamp(null), 2600);

    if (verdict.allowed && !needsCrossReview) {
      const next = applyLimbManifestPatch(registry, attempt.request);
      setRegistry(next);
      if (attempt.request.agentId) {
        setSelectedLimbId(attempt.request.agentId);
        setRecentlyMutatedId(attempt.request.agentId);
        if (glowTimeout.current) clearTimeout(glowTimeout.current);
        glowTimeout.current = setTimeout(() => setRecentlyMutatedId(null), 1400);
      }
    }
  };

  const approveCrossReview = async () => {
    if (!pendingProposal) return;
    try {
      const { proposal } = await submitCrossReview(pendingProposal.proposal_id, {
        verdict: "approved",
        notes: "Simulated cross-review approval (zen-review skill path)",
      });
      await applyManifestProposal(proposal.proposal_id);
      setPendingProposal(null);
      setLog((prev) => [
        {
          id: `log-cr-${Date.now()}`,
          at: Date.now(),
          label: `Cross-review approved · ${proposal.agent_id ?? proposal.target}`,
          path: proposal.op,
          verdict: { allowed: true, violations: [], warnings: [], path: proposal.op },
          allowed: true,
          proposalId: proposal.proposal_id,
        },
        ...prev,
      ].slice(0, 8));
    } catch {
      // offline fallback
      setPendingProposal(null);
    }
  };

  const reset = () => {
    setRegistry(INITIAL_REGISTRY);
    setLog([]);
    setActiveStamp(null);
    setRecentlyMutatedId(null);
    setSelectedLimbId("pyra-python-tester");
  };

  const lockedCount = CORE_AGENT_IDS.size + 4; // core agents + 4 policy invariants

  return (
    <div
      className="space-y-5"
      style={{
        // Local ambient backdrop — layered radial + faint grid, scoped to this panel.
        backgroundImage:
          "radial-gradient(1100px 540px at 12% -10%, rgba(16,185,129,0.10), transparent 60%), radial-gradient(900px 520px at 92% 0%, rgba(244,63,94,0.08), transparent 60%), linear-gradient(to bottom, rgba(255,255,255,0.015) 1px, transparent 1px), linear-gradient(to right, rgba(255,255,255,0.015) 1px, transparent 1px)",
        backgroundSize: "auto, auto, 44px 44px, 44px 44px",
        borderRadius: "1rem",
        padding: "clamp(1rem, 2.2vw, 1.75rem)",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <header className="flex flex-col xl:flex-row xl:items-end xl:justify-between gap-4">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-400/10 border border-emerald-400/25 text-[10px] uppercase tracking-[0.22em] text-emerald-200">
            <Sparkles className="w-3.5 h-3.5" /> self-modification scope · limb-only
          </div>
          <h1
            className="mt-3 text-[clamp(1.9rem,3.6vw,3rem)] leading-[0.95] tracking-[-0.03em] text-white"
            style={{ fontFamily: "'Space Grotesk', system-ui, sans-serif", fontWeight: 600 }}
          >
            The Twin may grow limbs,
            <br />
            <span className="text-emerald-300">never</span> rewrite its brain.
          </h1>
          <p className="mt-3 text-[14px] leading-relaxed text-slate-400">
            Every manifest mutation passes through <code className="font-mono text-[12px] px-1.5 py-0.5 rounded bg-white/5 text-emerald-200">validateManifestMutation</code> before it can apply. The membrane below is the same gate the autodidactic engine consults — try a change and watch the verdict land.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill icon={<Lock className="w-3.5 h-3.5" />} tone="rose" label={`${lockedCount} invariants locked`} />
          <StatusPill icon={<ShieldCheck className="w-3.5 h-3.5" />} tone="emerald" label="validator armed" pulse />
          {pendingProposal && (
            <button
              onClick={() => void approveCrossReview()}
              className="px-3 py-2 rounded-lg bg-amber-400/10 border border-amber-400/25 text-xs text-amber-200 hover:bg-amber-400/20 transition-colors"
            >
              Approve cross-review ({pendingProposal.proposal_id})
            </button>
          )}
          <button onClick={reset} className="px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs text-slate-200 hover:bg-white/[0.07] transition-colors inline-flex items-center gap-1.5">
            <RotateCcw className="w-3.5 h-3.5" /> Reset snapshot
          </button>
        </div>
      </header>

      <div className="grid xl:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)] gap-5">
        {/* Radial membrane */}
        <section className="console-card p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-slate-200">
              <ShieldHalf className="w-4 h-4 text-emerald-300" />
              <span className="font-medium">Membrane</span>
            </div>
            <span className="text-[11px] text-slate-500">click a limb · click a core lock to test</span>
          </div>
          <div className="mt-4 relative">
            <svg viewBox="0 0 400 400" className="w-full max-w-[520px] mx-auto">
              <defs>
                <radialGradient id="core-gradient" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="rgba(244,63,94,0.18)" />
                  <stop offset="100%" stopColor="rgba(244,63,94,0.02)" />
                </radialGradient>
                <pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
                  <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(244,63,94,0.18)" strokeWidth="1" />
                </pattern>
              </defs>

              {/* Limb arcs */}
              {arcs.map(({ agent, startAngle, endAngle }) => {
                const isSelected = selectedLimbId === agent.id;
                const isGlowing = recentlyMutatedId === agent.id;
                return (
                  <g key={agent.id} className="cursor-pointer" onClick={() => setSelectedLimbId(agent.id)}>
                    <motion.path
                      d={arcPath(200, 200, 150, 96, startAngle, endAngle)}
                      fill={isSelected ? "rgba(16,185,129,0.28)" : "rgba(16,185,129,0.10)"}
                      stroke={isGlowing ? "#6ee7b7" : isSelected ? "#34d399" : "rgba(16,185,129,0.45)"}
                      strokeWidth={isGlowing ? 2.5 : 1}
                      initial={false}
                      animate={{
                        filter: isGlowing ? "drop-shadow(0 0 10px rgba(110,231,183,0.85))" : "none",
                      }}
                      transition={{ duration: 0.6 }}
                      whileHover={{ fill: "rgba(16,185,129,0.22)" }}
                    />
                    {(() => {
                      const mid = (startAngle + endAngle) / 2;
                      const pos = polar(200, 200, 123, mid);
                      return (
                        <text
                          x={pos.x}
                          y={pos.y}
                          fill={isSelected ? "#ecfdf5" : "#a7f3d0"}
                          fontSize="10.5"
                          fontWeight={isSelected ? 600 : 500}
                          textAnchor="middle"
                          dominantBaseline="middle"
                          style={{ fontFamily: "'Space Grotesk', system-ui, sans-serif", pointerEvents: "none", letterSpacing: "0.01em" }}
                        >
                          {agent.label.split(" · ")[0]}
                        </text>
                      );
                    })()}
                  </g>
                );
              })}

              {/* Core disk */}
              <circle cx="200" cy="200" r="82" fill="url(#core-gradient)" stroke="rgba(244,63,94,0.35)" strokeWidth="1" />
              <circle cx="200" cy="200" r="82" fill="url(#hatch)" />
              <g style={{ pointerEvents: "none" }}>
                <ShieldCheck x={186} y={174} width={28} height={28} className="text-rose-300" />
                <text x="200" y="220" fill="#fecdd3" fontSize="10" fontWeight={600} textAnchor="middle" style={{ fontFamily: "'Space Grotesk', system-ui, sans-serif", letterSpacing: "0.18em" }}>
                  CORE
                </text>
              </g>

              {/* Core agent locks placed around the core */}
              {cores.map((agent, i) => {
                const angle = 90 + i * 120;
                const pos = polar(200, 200, 178, angle);
                return (
                  <g
                    key={agent.id}
                    className="cursor-pointer"
                    onClick={() => {
                      const attempt = CANNED_ATTEMPTS.find((a) => a.request.agentId === agent.id && a.request.op === "setSystemPrompt");
                      if (attempt) runAttempt(attempt);
                    }}
                  >
                    <circle cx={pos.x} cy={pos.y} r="22" fill="rgba(244,63,94,0.12)" stroke="rgba(244,63,94,0.45)" strokeWidth="1" />
                    <Lock x={pos.x - 7} y={pos.y - 7} width={14} height={14} className="text-rose-300" />
                    <text x={pos.x} y={pos.y + 36} fill="#fda4af" fontSize="9.5" fontWeight={500} textAnchor="middle" style={{ fontFamily: "'Space Grotesk', system-ui, sans-serif" }}>
                      {agent.label.split(" · ")[0]}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500 justify-center">
            <LegendDot color="#34d399" label="limb · mutable" />
            <LegendDot color="#fb7185" label="core · locked" />
            <LegendDot color="#fbbf24" label="warning" />
          </div>
        </section>

        {/* Sandbox + inspector */}
        <section className="space-y-5">
          <div className="console-card p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-slate-200">
                <Wand2 className="w-4 h-4 text-emerald-300" />
                <span className="font-medium">Mutation sandbox</span>
              </div>
              <span className="text-[11px] text-slate-500">{CANNED_ATTEMPTS.length} attempts</span>
            </div>
            <ul className="mt-4 space-y-2">
              {CANNED_ATTEMPTS.map((attempt) => (
                <li key={attempt.id} className="group rounded-lg bg-white/[0.025] border border-white/[0.06] px-3 py-2.5 hover:border-white/[0.14] transition-colors">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[13px] text-white leading-snug">{attempt.label}</div>
                      <div className="mt-1 text-[11px] text-slate-500 leading-relaxed line-clamp-2 group-hover:line-clamp-none">{attempt.narration}</div>
                    </div>
                    <button
                      onClick={() => runAttempt(attempt)}
                      className="flex-shrink-0 px-2.5 py-1 rounded-md bg-emerald-400/10 border border-emerald-400/25 text-[11px] text-emerald-200 hover:bg-emerald-400/20 transition-colors inline-flex items-center gap-1"
                    >
                      <Terminal className="w-3 h-3" /> try
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="console-card p-5 min-h-[220px] relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-slate-200">
                <Cpu className="w-4 h-4 text-cyan-300" />
                <span className="font-medium">Selected limb</span>
              </div>
              {selectedAgent && <span className="text-[11px] text-slate-500 font-mono">{selectedAgent.id}</span>}
            </div>

            {selectedAgent ? (
              <div className="mt-4 space-y-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Label</div>
                  <div className="mt-1 text-[15px] text-white" style={{ fontFamily: "'Space Grotesk', system-ui, sans-serif" }}>{selectedAgent.label}</div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500">
                    <span>Tools ({selectedAgent.tools.length})</span>
                    <span>limb scope</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {selectedAgent.tools.map((tool) => (
                      <span key={tool} className="px-2 py-1 rounded-md bg-white/[0.05] border border-white/[0.08] text-[11px] text-slate-200 font-mono">{tool}</span>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Context window</div>
                    <div className="mt-1 font-mono text-[13px] text-slate-200">{(selectedAgent.contextWindow / 1000).toFixed(0)}k tokens</div>
                    <div className="mt-1.5 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-emerald-400 to-teal-300"
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(100, (selectedAgent.contextWindow / 1_000_000) * 100)}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Model · tier {selectedAgent.modelTier}</div>
                    <div className="mt-1 font-mono text-[13px] text-slate-200">{selectedAgent.model}</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-8 text-center text-[13px] text-slate-500">Pick a limb in the membrane.</div>
            )}

            {/* Verdict stamp overlay */}
            <AnimatePresence>
              {activeStamp && (
                <motion.div
                  key={activeStamp.attemptId + activeStamp.path}
                  initial={{ opacity: 0, scale: 1.45, rotate: -16 }}
                  animate={{ opacity: 1, scale: 1, rotate: -8 }}
                  exit={{ opacity: 0, scale: 0.96, rotate: -8 }}
                  transition={{ type: "spring", stiffness: 260, damping: 18 }}
                  className="absolute inset-0 flex items-center justify-center pointer-events-none"
                >
                  <div
                    className={`px-6 py-3 rounded-xl border-2 ${
                      activeStamp.allowed
                        ? "border-emerald-300/70 text-emerald-200 bg-emerald-400/10"
                        : "border-rose-400/70 text-rose-200 bg-rose-400/10"
                    } backdrop-blur-sm`}
                    style={{ fontFamily: "'Space Grotesk', system-ui, sans-serif" }}
                  >
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] opacity-80">
                      {activeStamp.allowed ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      verdict
                    </div>
                    <div className="mt-1 text-[26px] font-bold leading-none">
                      {activeStamp.allowed ? "ALLOWED" : pendingProposal ? "CROSS-REVIEW" : "REJECTED"}
                    </div>
                    <div className="mt-1.5 font-mono text-[10.5px] opacity-80">{activeStamp.path}</div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Verdict details */}
          <AnimatePresence mode="wait">
            {activeStamp && (
              <motion.div
                key={activeStamp.attemptId + "-details"}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                className="console-card p-4"
              >
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                  {activeStamp.allowed ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" /> : <XCircle className="w-3.5 h-3.5 text-rose-300" />}
                  violations · warnings
                </div>
                {activeStamp.verdict.violations.length > 0 ? (
                  <ul className="mt-3 space-y-1.5">
                    {activeStamp.verdict.violations.map((v, i) => (
                      <li key={i} className="flex items-start gap-2 text-[12px] text-rose-200 font-mono leading-relaxed">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-rose-300" /> {v}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-[12px] text-emerald-200">No violations — mutation applied to snapshot.</p>
                )}
                {activeStamp.verdict.warnings.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {activeStamp.verdict.warnings.map((w, i) => (
                      <li key={i} className="flex items-start gap-2 text-[12px] text-amber-200 font-mono leading-relaxed">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-amber-300" /> {w}
                      </li>
                    ))}
                  </ul>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </section>
      </div>

      {/* Attempt log */}
      <section className="console-card p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <Terminal className="w-4 h-4 text-slate-300" />
            <span className="font-medium">Attempt log</span>
          </div>
          <span className="text-[11px] text-slate-500">session-only · newest first</span>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] text-[12px]">
            <thead className="text-[10px] uppercase tracking-[0.18em] text-slate-500 text-left">
              <tr>
                <th className="py-2 pr-3 font-medium">Time</th>
                <th className="py-2 pr-3 font-medium">Attempt</th>
                <th className="py-2 pr-3 font-medium">Path</th>
                <th className="py-2 pr-3 font-medium">Verdict</th>
                <th className="py-2 pr-3 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence initial={false}>
                {log.length === 0 && (
                  <tr key="empty">
                    <td colSpan={5} className="py-8 text-center text-slate-500">No attempts yet — pick one from the sandbox above.</td>
                  </tr>
                )}
                {log.map((entry) => (
                  <motion.tr
                    key={entry.id}
                    layout
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="border-t border-white/[0.05]"
                  >
                    <td className="py-2.5 pr-3 text-slate-500 font-mono tabular-nums">{new Date(entry.at).toLocaleTimeString("en-GB")}</td>
                    <td className="py-2.5 pr-3 text-slate-200">{entry.label}</td>
                    <td className="py-2.5 pr-3 text-slate-400 font-mono">{entry.path}</td>
                    <td className="py-2.5 pr-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] uppercase tracking-wider ${entry.allowed ? "text-emerald-200 bg-emerald-400/10 border-emerald-400/25" : "text-rose-200 bg-rose-400/10 border-rose-400/25"}`}>
                        {entry.allowed ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />} {entry.allowed ? "allowed" : "rejected"}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-slate-500 font-mono">
                      {entry.allowed ? `${entry.verdict.warnings.length} warning${entry.verdict.warnings.length === 1 ? "" : "s"}` : `${entry.verdict.violations.length} violation${entry.verdict.violations.length === 1 ? "" : "s"}`}
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      </section>

      <footer className="text-[11px] text-slate-500 leading-relaxed max-w-3xl">
        Audit lines are produced by <code className="font-mono text-slate-300">auditLine(request, verdict)</code> and persisted via <code className="font-mono text-slate-300">POST /api/manifest/propose</code>. Core and policy mutations require cross-review approval before apply; limb mutations within allow-list apply immediately when the boundary validator passes.
      </footer>
    </div>
  );
}

function StatusPill({
  icon,
  label,
  tone,
  pulse,
}: {
  icon: React.ReactNode;
  label: string;
  tone: "emerald" | "rose";
  pulse?: boolean;
}) {
  const styles = tone === "emerald"
    ? "bg-emerald-400/10 border-emerald-400/25 text-emerald-200"
    : "bg-rose-400/10 border-rose-400/25 text-rose-200";
  const dot = tone === "emerald" ? "bg-emerald-400" : "bg-rose-400";
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${styles}`}>
      {pulse && <span className={`w-1.5 h-1.5 rounded-full ${dot} animate-pulse`} />}
      {!pulse && icon}
      {label}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="w-2 h-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

// Re-export so other modules can construct an audit entry without importing
// the validator file directly. Not used inside this component, but kept here
// so the Boundary surface is the canonical home of the audit-line pattern.
export { auditLine };
