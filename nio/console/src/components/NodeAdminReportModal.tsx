"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  BrainCircuit,
  LockKeyhole,
  Send,
  ShieldCheck,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import type { MockAgent, GoogleCloudAgentRegistryEntry } from "@/data/mock-orchestrator";
import type { LimbInstance, LimbTemplate } from "@/lib/manifest-types";
import {
  dispatchSubagent,
  fetchCodySupervisor,
  runTask,
} from "@/lib/nio-client";
import { openCodyPet } from "@/hooks/useCodyPet";
import { isCoreMockId } from "@/data/atlas-limb";

export type NodeKind = "orchestrator" | "cody" | "limb" | "core";

function detectNodeKind(agentId: string): NodeKind {
  if (agentId === "orchestrator") return "orchestrator";
  if (agentId === "cody") return "cody";
  if (agentId.startsWith("limb-")) return "limb";
  return "core";
}

function formatWhen(iso: string | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function NodeAdminReportModal({
  open,
  agent,
  limb,
  template,
  registryEntry,
  templates,
  apiLive,
  onClose,
  onActionComplete,
}: {
  open: boolean;
  agent: MockAgent | null;
  limb: LimbInstance | null;
  template: LimbTemplate | null;
  registryEntry: GoogleCloudAgentRegistryEntry | undefined;
  templates: LimbTemplate[];
  apiLive: boolean;
  onClose: () => void;
  onActionComplete?: () => void;
}) {
  const [adminMode, setAdminMode] = useState(false);
  const [supervisorSummary, setSupervisorSummary] = useState<string | null>(null);
  const [steerText, setSteerText] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [role, setRole] = useState("worker");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const kind = agent ? detectNodeKind(agent.id) : null;

  useEffect(() => {
    if (!open) {
      setAdminMode(false);
      setSteerText("");
      setResult(null);
      setError(null);
      return;
    }
    setTemplateId(limb?.template_id ?? templates[0]?.template_id ?? "");
    setRole(template?.role ?? "worker");
    void fetchCodySupervisor()
      .then((s) => setSupervisorSummary(s.summary))
      .catch(() => setSupervisorSummary(null));
  }, [open, limb?.template_id, template?.role, templates]);

  const handleSteerTask = useCallback(async () => {
    if (!steerText.trim() || !agent) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const prefix =
        kind === "limb" && limb
          ? `[Admin steer · ${limb.limb_instance_id} · ${limb.task_id}] `
          : `[Admin steer · ${agent.name}] `;
      const res = await runTask({
        taskDescription: prefix + steerText.trim(),
        templateId: templateId || undefined,
        role,
        source: "console",
        isComplexWorkflow: kind === "limb",
        domainHint: kind === "limb" ? "dev_dp" : "generic",
      });
      setResult(typeof res.output === "string" ? res.output.slice(0, 400) : "Task accepted");
      onActionComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Steer failed");
    } finally {
      setBusy(false);
    }
  }, [agent, kind, limb, onActionComplete, role, steerText, templateId]);

  const handleRedeploy = useCallback(async () => {
    if (!steerText.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await dispatchSubagent({
        taskDescription: steerText.trim(),
        templateId: templateId || undefined,
        role,
        source: "console",
      });
      setResult(res.dispatched ? `Dispatched limb ${res.limbInstanceId ?? ""}` : `Blocked: ${res.gateRun.blockedBy ?? "gates"}`);
      onActionComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dispatch failed");
    } finally {
      setBusy(false);
    }
  }, [onActionComplete, role, steerText, templateId]);

  if (!agent) return null;

  const lockedCore = isCoreMockId(agent.id) && agent.id !== "orchestrator";

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-labelledby="node-admin-title"
            className="w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-2xl border border-white/10 bg-[#0c0f16] shadow-2xl flex flex-col"
            initial={{ scale: 0.96, y: 12 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.96, y: 12 }}
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-start justify-between gap-4 px-6 py-5 border-b border-white/[0.07]">
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-12 h-12 rounded-xl grid place-items-center bg-white/[0.04] border border-white/10 shrink-0">
                  {kind === "orchestrator" ? (
                    <BrainCircuit className="w-6 h-6 text-cyan-300" />
                  ) : kind === "cody" ? (
                    <Zap className="w-6 h-6 text-amber-300" />
                  ) : (
                    <span className="font-bold text-sm text-violet-300">{agent.initials}</span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Node report</p>
                  <h2 id="node-admin-title" className="text-lg font-semibold text-white truncate">
                    {agent.name}
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">{agent.role} · {agent.domain}</p>
                </div>
              </div>
              <button type="button" onClick={onClose} className="p-2 text-slate-500 hover:text-white" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </header>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              <section className="grid sm:grid-cols-2 gap-3">
                <ReportTile label="Status" value={agent.status} />
                <ReportTile label="Runtime" value={registryEntry?.runtime ?? agent.runtime} />
                <ReportTile label="Model" value={registryEntry?.llmModel ?? agent.model} />
                <ReportTile label="Reliability" value={`${agent.reliability}%`} />
              </section>

              <section className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                <p className="text-[10px] uppercase tracking-wider text-slate-600 mb-2">Last action</p>
                <p className="text-sm text-slate-300 leading-relaxed">{agent.lastAction}</p>
                {supervisorSummary ? (
                  <p className="text-[11px] text-slate-500 mt-3">Supervisor: {supervisorSummary}</p>
                ) : null}
              </section>

              {kind === "limb" && limb ? (
                <section className="rounded-xl border border-violet-500/20 bg-violet-500/[0.04] p-4 space-y-2">
                  <p className="text-xs font-medium text-violet-200">Active limb instance</p>
                  <div className="grid sm:grid-cols-2 gap-2 text-[11px] text-slate-400">
                    <span>ID: <code className="text-slate-300">{limb.limb_instance_id}</code></span>
                    <span>Task: <code className="text-slate-300">{limb.task_id}</code></span>
                    <span>State: <span className="text-white">{limb.state}</span></span>
                    <span>Deployed: {formatWhen(limb.deployed_at)}</span>
                    <span>Template: {limb.template_id}</span>
                    <span>Mock: {limb.mock_id}</span>
                  </div>
                  {template ? (
                    <p className="text-xs text-slate-500 pt-1">{template.description ?? template.display_name}</p>
                  ) : null}
                </section>
              ) : null}

              {kind === "orchestrator" ? (
                <section className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.04] p-4">
                  <p className="text-xs font-medium text-cyan-200">Atlas orchestrator</p>
                  <p className="text-sm text-slate-400 mt-2 leading-relaxed">
                    Coordinates gated subagent dispatch, limb lifecycle, and Cody supervisor mediation.
                    Admin takeover lets you dispatch or steer tasks through the fabric.
                  </p>
                </section>
              ) : null}

              {kind === "cody" ? (
                <section className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <p className="text-sm text-slate-400">Human supervisor channel — Telegram + console pet.</p>
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      openCodyPet();
                    }}
                    className="text-xs px-3 py-1.5 rounded-lg border border-amber-400/30 text-amber-200 hover:bg-amber-500/10"
                  >
                    Open Cody
                  </button>
                </section>
              ) : null}

              {!adminMode ? (
                <button
                  type="button"
                  disabled={lockedCore || !apiLive}
                  onClick={() => setAdminMode(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-rose-400/30 bg-rose-500/[0.08] text-rose-100 text-sm font-medium hover:bg-rose-500/12 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <LockKeyhole className="w-4 h-4" />
                  Take over as Admin
                </button>
              ) : (
                <section className="rounded-xl border border-rose-400/25 bg-rose-500/[0.06] p-4 space-y-4">
                  <div className="flex items-center gap-2 text-rose-200 text-sm font-medium">
                    <ShieldCheck className="w-4 h-4" />
                    Admin takeover active
                  </div>

                  <div className="grid sm:grid-cols-2 gap-3">
                    <label className="block text-[11px] text-slate-500">
                      Template
                      <select
                        value={templateId}
                        onChange={(e) => setTemplateId(e.target.value)}
                        className="mt-1 w-full rounded-lg bg-white/[0.04] border border-white/10 px-2 py-2 text-xs text-white"
                      >
                        {templates.map((t) => (
                          <option key={t.template_id} value={t.template_id}>
                            {t.display_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-[11px] text-slate-500">
                      Role
                      <select
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                        className="mt-1 w-full rounded-lg bg-white/[0.04] border border-white/10 px-2 py-2 text-xs text-white"
                      >
                        <option value="worker">worker</option>
                        <option value="judge">judge</option>
                        <option value="coordinator">coordinator</option>
                      </select>
                    </label>
                  </div>

                  <label className="block text-[11px] text-slate-500">
                    Steer / task instruction
                    <textarea
                      value={steerText}
                      onChange={(e) => setSteerText(e.target.value)}
                      rows={4}
                      placeholder={
                        kind === "limb"
                          ? "New instruction for this subagent limb…"
                          : "Task description to run through Atlas…"
                      }
                      className="mt-1 w-full rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-slate-600 resize-none"
                    />
                  </label>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy || !steerText.trim()}
                      onClick={() => void handleSteerTask()}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500/20 border border-cyan-400/30 text-cyan-100 text-xs font-medium hover:bg-cyan-500/30 disabled:opacity-40"
                    >
                      <Send className="w-3.5 h-3.5" />
                      Steer task
                    </button>
                    {(kind === "orchestrator" || kind === "limb") && (
                      <button
                        type="button"
                        disabled={busy || !steerText.trim()}
                        onClick={() => void handleRedeploy()}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-500/20 border border-violet-400/30 text-violet-100 text-xs font-medium hover:bg-violet-500/30 disabled:opacity-40"
                      >
                        <Terminal className="w-3.5 h-3.5" />
                        Dispatch subagent
                      </button>
                    )}
                  </div>

                  {error ? <p className="text-xs text-rose-300">{error}</p> : null}
                  {result ? (
                    <pre className="text-[10px] text-slate-400 bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                      {result}
                    </pre>
                  ) : null}
                </section>
              )}

              {lockedCore ? (
                <p className="text-xs text-rose-300/80">Locked core agents require cross-review — admin takeover disabled.</p>
              ) : null}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function ReportTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/[0.03] border border-white/[0.06] p-3">
      <p className="text-[10px] uppercase tracking-wider text-slate-600">{label}</p>
      <p className="text-sm font-medium text-white mt-1 capitalize">{value}</p>
    </div>
  );
}
