"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronRight,
  Gauge,
  KeyRound,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TerminalSquare,
  X,
  Zap,
} from "lucide-react";
import { MCP_SERVERS, PALETTE, PRIMARY_ENGINES, PROVIDERS } from "./catalog";
import { poolHealth, rankCandidates } from "./routing";
import { selectActiveModel, useApolloStore } from "./store";
import { Badge, EmptyHint, Field, MiniBar, SectionCard, Segmented, Slider, TextInput, Toggle } from "./ui";
import type { ApolloConfiguration, FreeLLMProviderKey } from "./types";

type Tab = "runtime" | "router" | "bridge";

const TABS: Array<{ id: Tab; label: string; icon: typeof Gauge }> = [
  { id: "runtime", label: "Runtime", icon: Gauge },
  { id: "router", label: "FreeLLM Router", icon: Zap },
  { id: "bridge", label: "MCP & Sandbox", icon: ShieldCheck },
];

const PROVIDER_TONE: Record<FreeLLMProviderKey["status"], "emerald" | "amber" | "slate"> = {
  ACTIVE: "emerald",
  LIMIT_REACHED: "amber",
  STANDBY: "slate",
};

export function ApolloDeck() {
  const open = useApolloStore((s) => s.deckOpen);
  const setDeckOpen = useApolloStore((s) => s.setDeckOpen);
  const setTerminalOpen = useApolloStore((s) => s.setTerminalOpen);
  const config = useApolloStore((s) => s.config);
  const applyConfig = useApolloStore((s) => s.applyConfig);
  const restorePrimary = useApolloStore((s) => s.restorePrimary);
  const simulateFailover = useApolloStore((s) => s.simulateFailover);
  const setWeights = useApolloStore((s) => s.setWeights);
  const toggleProvider = useApolloStore((s) => s.toggleProvider);
  const setQuota = useApolloStore((s) => s.setQuota);
  const router = useApolloStore((s) => s.router);
  const activeModel = useApolloStore(selectActiveModel);

  const [tab, setTab] = useState<Tab>("runtime");
  const [draft, setDraft] = useState<ApolloConfiguration>(config);
  const [applied, setApplied] = useState(false);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      // Quota is runtime state, not configuration: seed the draft from the live
      // router so pressing Apply never silently rewinds a drained quota.
      setDraft({ ...structuredClone(config), primaryQuotaPercent: router.primaryQuotaPercent });
      setApplied(false);
    }
  }, [open, config, router.primaryQuotaPercent]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setDeckOpen(false);
      }
      if (event.key === "Tab") {
        const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])',
        );
        if (!focusables || focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, setDeckOpen]);

  const ranked = useMemo(
    () => rankCandidates(draft.freeLLMRouting.fallbackChain, draft.freeLLMRouting.weights),
    [draft.freeLLMRouting],
  );
  const health = poolHealth(draft.freeLLMRouting.providers);
  const endpoints = PROVIDERS.reduce((sum, provider) => sum + provider.endpoints, 0);

  if (!open) return null;

  const patch = (changes: Partial<ApolloConfiguration>) => setDraft((prev) => ({ ...prev, ...changes }));
  const patchRouting = (changes: Partial<ApolloConfiguration["freeLLMRouting"]>) =>
    setDraft((prev) => ({ ...prev, freeLLMRouting: { ...prev.freeLLMRouting, ...changes } }));

  const onApply = () => {
    const ok = applyConfig(draft);
    setApplied(ok);
    if (ok) setTimeout(() => setApplied(false), 2200);
  };

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center p-3 sm:p-6"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) setDeckOpen(false);
      }}
    >
      <div
        aria-hidden
        className="absolute inset-0 bg-[#03060d]/72 backdrop-blur-[10px] apollo-fade-in"
      />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="apollo-deck-title"
        className="apollo-deck relative flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-cyan-300/15 bg-[#070b16]/95 shadow-[0_40px_120px_rgba(0,0,0,0.7)] apollo-rise-in"
      >
        {/* header */}
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan-300/30 bg-cyan-400/10 text-cyan-300">
              <Sparkles size={15} />
            </span>
            <div>
              <h2 id="apollo-deck-title" className="text-[13.5px] font-semibold tracking-wide text-slate-100">
                NIO Apollo Control Deck
              </h2>
              <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-slate-500">
                {activeModel.name} · {router.mode.toLowerCase()} · {router.failoverCount} failover
                {router.failoverCount === 1 ? "" : "s"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={draft.freeLLMRouting.enabled ? "emerald" : "slate"} dot>
              {draft.freeLLMRouting.enabled ? "routing armed" : "routing off"}
            </Badge>
            <Badge tone="cyan">{health.active} keys live</Badge>
            <button
              type="button"
              onClick={() => setDeckOpen(false)}
              aria-label="Close control deck"
              className="grid h-7 w-7 place-items-center rounded-md border border-white/10 text-slate-400 transition-colors hover:border-white/25 hover:text-slate-100"
            >
              <X size={14} />
            </button>
          </div>
        </header>

        {/* tabs */}
        <nav className="flex gap-1 border-b border-white/[0.06] px-3 pt-2" aria-label="Deck sections">
          {TABS.map((entry) => {
            const Icon = entry.icon;
            const active = tab === entry.id;
            return (
              <button
                key={entry.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setTab(entry.id)}
                className={`flex items-center gap-1.5 rounded-t-lg border-b-2 px-3 py-2 text-[11.5px] font-medium transition-colors ${
                  active
                    ? "border-cyan-400 text-cyan-200"
                    : "border-transparent text-slate-500 hover:text-slate-300"
                }`}
              >
                <Icon size={13} />
                {entry.label}
              </button>
            );
          })}
        </nav>

        {/* body */}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5">
          {tab === "runtime" && (
            <div className="grid gap-3 lg:grid-cols-[1.15fr_0.85fr]">
              <SectionCard
                title="Primary runtime"
                hint="The engine in front of the pool. Quota is watched every turn; crossing the threshold hands the task to FreeLLMAPI."
                right={<Badge tone="cyan">{router.primaryQuotaPercent.toFixed(0)}% left</Badge>}
              >
                <div className="space-y-2">
                  {PRIMARY_ENGINES.map((engine) => {
                    const selected = draft.primaryModel === engine.label;
                    return (
                      <button
                        key={engine.id}
                        type="button"
                        onClick={() => patch({ primaryModel: engine.label })}
                        aria-pressed={selected}
                        className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition-colors ${
                          selected
                            ? "border-cyan-400/45 bg-cyan-400/[0.07]"
                            : "border-white/[0.06] bg-white/[0.015] hover:border-white/15"
                        }`}
                      >
                        <span>
                          <span className={`block text-[12px] ${selected ? "text-cyan-100" : "text-slate-200"}`}>
                            {engine.label}
                          </span>
                          <span className="block font-mono text-[9px] uppercase tracking-[0.16em] text-slate-500">
                            {engine.detail}
                          </span>
                        </span>
                        {selected && <Check size={14} className="text-cyan-300" />}
                      </button>
                    );
                  })}
                </div>
              </SectionCard>

              <div className="space-y-3">
                <SectionCard title="Quota monitor" hint="Auto-failover fires at or below the threshold.">
                  <div className="space-y-3">
                    <div>
                      <div className="flex items-baseline justify-between font-mono text-[10px] text-slate-500">
                        <span>primary quota · live</span>
                        <span
                          className="tabular-nums"
                          style={{
                            color:
                              router.primaryQuotaPercent > 50
                                ? PALETTE.emerald
                                : router.primaryQuotaPercent > 15
                                  ? PALETTE.amber
                                  : PALETTE.crimson,
                          }}
                        >
                          {router.primaryQuotaPercent.toFixed(0)}%
                        </span>
                      </div>
                      <div className="mt-1.5">
                        <MiniBar
                          value={router.primaryQuotaPercent}
                          color={
                            router.primaryQuotaPercent > 50
                              ? PALETTE.emerald
                              : router.primaryQuotaPercent > 15
                                ? PALETTE.amber
                                : PALETTE.crimson
                          }
                          height={6}
                        />
                      </div>
                      <div className="mt-2.5">
                        <Slider
                          label="Simulate drain"
                          value={Math.round(router.primaryQuotaPercent)}
                          min={0}
                          max={100}
                          step={1}
                          onChange={setQuota}
                          format={(value) => `${value}%`}
                          hint="Writes straight to the live router — cross the threshold and the next turn fails over."
                          accent={
                            router.primaryQuotaPercent > 50
                              ? PALETTE.emerald
                              : router.primaryQuotaPercent > 15
                                ? PALETTE.amber
                                : PALETTE.crimson
                          }
                        />
                      </div>
                    </div>
                    <Slider
                      label="Failover threshold"
                      value={draft.failoverThresholdPercent}
                      min={0}
                      max={50}
                      step={1}
                      onChange={(value) => patch({ failoverThresholdPercent: value })}
                      format={(value) => `${value}%`}
                      hint="0% = only when the primary is fully spent. Higher values switch earlier."
                      accent={PALETTE.amber}
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setDeckOpen(false);
                          simulateFailover("operator simulated quota exhaustion from the deck");
                        }}
                        className="flex-1 rounded-lg border border-amber-400/30 bg-amber-400/10 px-2 py-1.5 font-mono text-[9.5px] uppercase tracking-[0.16em] text-amber-200 transition-colors hover:bg-amber-400/20"
                      >
                        simulate 429
                      </button>
                      <button
                        type="button"
                        onClick={restorePrimary}
                        className="flex-1 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-[9.5px] uppercase tracking-[0.16em] text-slate-300 transition-colors hover:border-emerald-400/40 hover:text-emerald-200"
                      >
                        reset quota
                      </button>
                    </div>
                  </div>
                </SectionCard>

                <SectionCard title="Sampling & policy">
                  <div className="space-y-3">
                    <Slider
                      label="Temperature"
                      value={draft.temperature}
                      min={0}
                      max={2}
                      step={0.05}
                      onChange={(value) => patch({ temperature: value })}
                      format={(value) => value.toFixed(2)}
                      accent={PALETTE.violet}
                    />
                    <Field label="Max context" htmlFor="deck-max-tokens">
                      <TextInput
                        id="deck-max-tokens"
                        type="number"
                        mono
                        value={draft.maxTokens}
                        onChange={(value) => patch({ maxTokens: Math.max(256, Math.min(1_000_000, Number(value) || 0)) })}
                      />
                    </Field>
                    <Field label="Execution policy">
                      <Segmented
                        label="Execution policy"
                        value={draft.executionPolicy}
                        onChange={(value) => patch({ executionPolicy: value })}
                        options={[
                          { value: "AUTONOMOUS", label: "Autonomous" },
                          { value: "CONSERVATIVE", label: "Conservative" },
                          { value: "SANDBOX_STRICT", label: "Sandbox strict" },
                        ]}
                      />
                    </Field>
                  </div>
                </SectionCard>
              </div>

              <SectionCard
                title="System directive"
                hint="Injected into every dispatch and carried inside the context handoff note."
                className="lg:col-span-2"
              >
                <textarea
                  value={draft.systemDirective}
                  onChange={(event) => patch({ systemDirective: event.target.value })}
                  rows={3}
                  aria-label="System directive"
                  className="w-full resize-y rounded-lg border border-white/[0.08] bg-black/30 px-3 py-2 text-[11.5px] leading-relaxed text-slate-200 outline-none transition-colors focus:border-cyan-400/50"
                />
                <p className="mt-1.5 font-mono text-[9.5px] text-slate-500">
                  {draft.systemDirective.length} chars · handoff notes are clipped to 900
                </p>
              </SectionCard>
            </div>
          )}

          {tab === "router" && (
            <div className="space-y-3">
              <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
                <SectionCard
                  title="FreeLLMAPI failover"
                  hint="Zero-downtime routing across the free-tier pool through one OpenAI-compatible proxy."
                  right={<Badge tone={draft.freeLLMRouting.enabled ? "emerald" : "slate"} dot>{draft.freeLLMRouting.enabled ? "armed" : "off"}</Badge>}
                >
                  <div className="space-y-2">
                    <Toggle
                      id="deck-routing"
                      checked={draft.freeLLMRouting.enabled}
                      onChange={(value) => patchRouting({ enabled: value })}
                      label="Auto-failover on quota exhaustion"
                      detail="On 429 / zero quota, hot-swap to the highest-scored free model."
                    />
                    <Toggle
                      id="deck-handoff"
                      checked={draft.freeLLMRouting.enableContextHandoffNote}
                      onChange={(value) => patchRouting({ enableContextHandoffNote: value })}
                      label="Attach context handoff note"
                      detail="Sends task state, completed steps and pending objectives to the next model."
                    />
                    <Field
                      label="Proxy endpoint"
                      htmlFor="deck-endpoint"
                      hint="Empty = local simulation. Set an OpenAI-compatible base URL to answer live (server-side proxy)."
                    >
                      <TextInput
                        id="deck-endpoint"
                        type="url"
                        mono
                        value={draft.freeLLMRouting.endpointUrl}
                        placeholder="http://127.0.0.1:8080/v1"
                        onChange={(value) => patchRouting({ endpointUrl: value })}
                      />
                    </Field>
                  </div>
                </SectionCard>

                <SectionCard
                  title="Routing weights"
                  hint="Composite score = Σ weights × sub-score. Ties break on reliability."
                  right={<Badge tone="violet">{endpoints} endpoints</Badge>}
                >
                  <div className="space-y-3">
                    <Slider
                      label="Reliability"
                      value={draft.freeLLMRouting.weights.reliability}
                      min={0}
                      max={100}
                      step={5}
                      onChange={(value) => setWeights({ reliability: value })}
                      format={(value) => `${value}%`}
                      accent={PALETTE.emerald}
                    />
                    <Slider
                      label="Speed"
                      value={draft.freeLLMRouting.weights.speed}
                      min={0}
                      max={100}
                      step={5}
                      onChange={(value) => setWeights({ speed: value })}
                      format={(value) => `${value}%`}
                      accent={PALETTE.cyan}
                    />
                    <Slider
                      label="Intelligence"
                      value={draft.freeLLMRouting.weights.intelligence}
                      min={0}
                      max={100}
                      step={5}
                      onChange={(value) => setWeights({ intelligence: value })}
                      format={(value) => `${value}%`}
                      accent={PALETTE.violet}
                    />
                    <p className="font-mono text-[9px] text-slate-500">
                      normalised:{" "}
                      {Object.entries(draft.freeLLMRouting.weights)
                        .map(([key, value]) => `${key.slice(0, 3)} ${Math.round((value / Math.max(1, draft.freeLLMRouting.weights.reliability + draft.freeLLMRouting.weights.speed + draft.freeLLMRouting.weights.intelligence)) * 100)}%`)
                        .join(" · ")}
                    </p>
                  </div>
                </SectionCard>
              </div>

              <SectionCard
                title="Fallback chain"
                hint="Ranked live from the weights. #1 answers; the rest wait in order."
                right={<Badge tone="amber">{router.failoverCount} swaps this session</Badge>}
              >
                <div className="grid gap-2 sm:grid-cols-3">
                  {ranked.slice(0, 3).map((candidate, index) => (
                    <div
                      key={candidate.id}
                      className="rounded-lg border px-2.5 py-2"
                      style={{
                        borderColor:
                          index === 0 ? "rgba(16,185,129,0.35)" : index === 1 ? "rgba(34,211,238,0.22)" : "rgba(255,255,255,0.07)",
                        background: index === 0 ? "rgba(16,185,129,0.06)" : "rgba(255,255,255,0.015)",
                      }}
                    >
                      <div className="flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.16em]">
                        <span className={index === 0 ? "text-emerald-300" : "text-slate-500"}>#{index + 1}</span>
                        <span className={index === 0 ? "text-emerald-300" : "text-slate-500"}>
                          {index === 0 ? "active" : index === 1 ? "ready" : "standby"}
                        </span>
                      </div>
                      <div className="mt-1 truncate text-[11.5px] font-medium text-slate-100">{candidate.name}</div>
                      <div className="flex items-center justify-between font-mono text-[9.5px] text-slate-500">
                        <span className="truncate">{candidate.provider}</span>
                        <span className="tabular-nums">{candidate.compositeScore.toFixed(1)}</span>
                      </div>
                      <div className="mt-1.5">
                        <MiniBar value={candidate.compositeScore} color={index === 0 ? PALETTE.emerald : PALETTE.cyan} height={2} />
                      </div>
                    </div>
                  ))}
                </div>
                {router.lastHandoffNote && (
                  <div className="mt-3 rounded-lg border border-amber-400/20 bg-amber-400/[0.04] p-2.5">
                    <div className="mb-1 flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.18em] text-amber-300/80">
                      <span>last handoff note</span>
                      <span>{router.lastHandoffNote.length} chars</span>
                    </div>
                    <pre className="max-h-28 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-relaxed text-amber-100/80">
                      {router.lastHandoffNote}
                    </pre>
                  </div>
                )}
              </SectionCard>

              <div className="grid gap-3 lg:grid-cols-[0.95fr_1.05fr]">
                <SectionCard
                  title="Encrypted key vault"
                  hint="Masked identifiers only. Keys never reach the bundle; the proxy holds them server-side."
                  right={<Badge tone="cyan"><KeyRound size={8} /> {health.active}/{draft.freeLLMRouting.providers.length}</Badge>}
                >
                  <ul className="space-y-1">
                    {draft.freeLLMRouting.providers.map((provider) => (
                      <li key={provider.providerId}>
                        <button
                          type="button"
                          onClick={() => toggleProvider(provider.providerId)}
                          className="flex w-full items-center justify-between gap-2 rounded-md border border-transparent px-1.5 py-1 text-left transition-colors hover:border-white/10 hover:bg-white/[0.02]"
                        >
                          <span className="min-w-0">
                            <span className="block truncate text-[11.5px] text-slate-200">{provider.name}</span>
                            <span className="block font-mono text-[9px] text-slate-600">{provider.keyMasked}</span>
                          </span>
                          <Badge tone={PROVIDER_TONE[provider.status]} dot>
                            {provider.status === "LIMIT_REACHED" ? "limited" : provider.status.toLowerCase()}
                          </Badge>
                        </button>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 font-mono text-[9px] text-slate-600">click a key to toggle active ⇄ standby</p>
                </SectionCard>

                <SectionCard
                  title="Model leaderboard"
                  hint="Composite score from the current weights."
                  right={<Badge tone="violet">{ranked.length} candidates</Badge>}
                >
                  <div className="max-h-[260px] overflow-y-auto pr-1">
                    <table className="w-full border-collapse text-left">
                      <thead className="sticky top-0 bg-[#0a0f1b]/95 font-mono text-[8.5px] uppercase tracking-[0.16em] text-slate-600">
                        <tr>
                          <th className="py-1 pr-2">#</th>
                          <th className="py-1 pr-2">model</th>
                          <th className="py-1 pr-2 text-right">rel</th>
                          <th className="py-1 pr-2 text-right">spd</th>
                          <th className="py-1 pr-2 text-right">int</th>
                          <th className="py-1 text-right">score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ranked.map((candidate, index) => (
                          <tr key={candidate.id} className="border-t border-white/[0.04]">
                            <td className="py-1 pr-2 font-mono text-[9.5px] text-slate-600">{index + 1}</td>
                            <td className="py-1 pr-2">
                              <div className="truncate text-[11px] text-slate-200">{candidate.name}</div>
                              <div className="truncate font-mono text-[8.5px] text-slate-600">{candidate.provider}</div>
                            </td>
                            <td className="py-1 pr-2 text-right font-mono text-[9.5px] tabular-nums text-slate-400">{candidate.reliability}</td>
                            <td className="py-1 pr-2 text-right font-mono text-[9.5px] tabular-nums text-slate-400">{candidate.speed}</td>
                            <td className="py-1 pr-2 text-right font-mono text-[9.5px] tabular-nums text-slate-400">{candidate.intelligence}</td>
                            <td className="py-1 text-right">
                              <span
                                className="font-mono text-[10px] tabular-nums"
                                style={{ color: index === 0 ? PALETTE.emerald : candidate.status === "LIMIT_REACHED" ? PALETTE.crimson : "#94a3b8" }}
                              >
                                {candidate.compositeScore.toFixed(1)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              </div>
            </div>
          )}

          {tab === "bridge" && (
            <div className="grid gap-3 lg:grid-cols-2">
              <SectionCard title="MCP servers" hint="Live-toggled bridges the orchestrator may call.">
                <div className="space-y-1.5">
                  {MCP_SERVERS.map((server) => {
                    const on = draft.activeMcpServers.includes(server.id);
                    return (
                      <Toggle
                        key={server.id}
                        id={`mcp-${server.id}`}
                        checked={on}
                        label={server.label}
                        detail={server.detail}
                        onChange={(value) =>
                          patch({
                            activeMcpServers: value
                              ? [...draft.activeMcpServers, server.id]
                              : draft.activeMcpServers.filter((id) => id !== server.id),
                          })
                        }
                      />
                    );
                  })}
                </div>
              </SectionCard>

              <div className="space-y-3">
                <SectionCard title="Apollo permissions" hint="Every privilege is explicit and revocable mid-session.">
                  <div className="space-y-1.5">
                    <Toggle
                      id="perm-mutate"
                      checked={draft.allowAppMutation}
                      onChange={(value) => patch({ allowAppMutation: value })}
                      label="Allow Apollo to mutate NIO UI state"
                      detail="Gates Apply & Hot-Reload and config changes from the CLI."
                    />
                    <Toggle
                      id="perm-spawn"
                      checked={draft.allowDynamicNodeSpawn}
                      onChange={(value) => patch({ allowDynamicNodeSpawn: value })}
                      label="Allow dynamic Lymp node spawning"
                      detail="Gates /spawn and orchestrator-initiated mitosis."
                    />
                    <Toggle
                      id="perm-shell"
                      checked={draft.allowSandboxShell}
                      onChange={(value) => patch({ allowSandboxShell: value })}
                      label="Allow sandbox shell execution"
                      detail="Gates /sandbox exec. The route enforces a read-only allowlist regardless."
                    />
                  </div>
                </SectionCard>

                <SectionCard title="Session" hint="What this deck is driving right now.">
                  <dl className="grid grid-cols-2 gap-2 font-mono text-[10px]">
                    {[
                      ["mode", router.mode],
                      ["active", activeModel.name],
                      ["swaps", String(router.failoverCount)],
                      ["quota", `${router.primaryQuotaPercent.toFixed(0)}%`],
                      ["endpoint", draft.freeLLMRouting.endpointUrl ? "live proxy" : "simulated"],
                      ["handoff", draft.freeLLMRouting.enableContextHandoffNote ? "on" : "off"],
                    ].map(([key, value]) => (
                      <div key={key} className="rounded-md border border-white/[0.05] bg-white/[0.015] px-2 py-1.5">
                        <dt className="text-[8.5px] uppercase tracking-[0.16em] text-slate-600">{key}</dt>
                        <dd className="mt-0.5 truncate text-slate-200" title={value}>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setDeckOpen(false);
                        simulateFailover("operator simulation from the MCP tab");
                      }}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-2 py-1.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-amber-200 hover:bg-amber-400/20"
                    >
                      <Activity size={11} /> test failover
                    </button>
                    <button
                      type="button"
                      onClick={() => setDraft(structuredClone(config))}
                      className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-slate-300 hover:border-white/25"
                    >
                      <RotateCcw size={11} /> revert draft
                    </button>
                  </div>
                </SectionCard>
              </div>
            </div>
          )}
        </div>

        {/* footer */}
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.07] bg-black/25 px-4 py-3 sm:px-5">
          <p className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-slate-600">
            <SlidersHorizontal size={9} className="mr-1 inline" />
            {applied ? "hot-reloaded · apollo acknowledged" : "changes apply on hot-reload"}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setDeckOpen(false);
                setTerminalOpen(true);
              }}
              className="flex items-center gap-1.5 rounded-lg border border-white/12 bg-white/5 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-200 transition-colors hover:border-cyan-400/40 hover:text-cyan-200"
            >
              <TerminalSquare size={12} /> open terminal
              <ChevronRight size={11} className="opacity-60" />
            </button>
            <button
              type="button"
              onClick={onApply}
              disabled={!config.allowAppMutation}
              className="apollo-apply flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[11.5px] font-semibold text-[#04121b] transition-transform disabled:cursor-not-allowed disabled:opacity-50"
            >
              {applied ? <Check size={13} /> : <ArrowRight size={13} />}
              Apply &amp; hot-reload Apollo
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
