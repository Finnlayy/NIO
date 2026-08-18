"use client";

import { useEffect, useState } from "react";
import { MessageCircle, Timer, Zap, AlertTriangle, Route, Activity, ChevronDown, ChevronUp } from "lucide-react";
import type { CodyStats, FormattedInterAgentLine } from "@/lib/manifest-types";
import { fetchCodySupervisor } from "@/lib/nio-client";
import { openCodyPet } from "@/hooks/useCodyPet";
import { openCommsView } from "@/hooks/useCommsAudit";
import { filterByScope } from "@/components/comms/comms-filter";

function formatDuration(ms: number): string {
  if (ms <= 0) return "—";
  const sec = Math.floor(ms / 1000);
  const min = Math.floor(sec / 60);
  const hr = Math.floor(min / 60);
  const day = Math.floor(hr / 24);
  if (day > 0) return `${day}d ${hr % 24}h`;
  if (hr > 0) return `${hr}h ${min % 60}m`;
  if (min > 0) return `${min}m ${sec % 60}s`;
  return `${sec}s`;
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      day: "2-digit",
      month: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function CodyStatsBoard({ stats }: { stats: CodyStats | null }) {
  const online = stats?.online ?? false;
  const telegram = stats?.channels?.telegram ?? online;
  const consoleCh = stats?.channels?.console ?? false;
  const [commsOpen, setCommsOpen] = useState(false);
  const [commsLines, setCommsLines] = useState<FormattedInterAgentLine[]>([]);

  useEffect(() => {
    void fetchCodySupervisor()
      .then((sup) => {
        const relevant = filterByScope(sup.interAgentTimeline ?? [], "relevant");
        setCommsLines(relevant.slice(0, 5));
      })
      .catch(() => undefined);
  }, [stats?.supervisor?.summary]);

  const channelLabel =
    telegram && consoleCh
      ? "Telegram + Console"
      : telegram
        ? "Telegram"
        : consoleCh
          ? "Console"
          : "Offline";

  return (
    <section className="console-card overflow-hidden border border-amber-400/20 bg-gradient-to-br from-amber-500/[0.06] via-transparent to-cyan-500/[0.04]">
      <div className="p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.07]">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl grid place-items-center font-bold text-sm bg-amber-500/15 text-amber-200 border border-amber-400/30">
            ⚡
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Supervisor · user · orchestrator · limbs</p>
            <h2 className="text-lg font-semibold text-white mt-0.5">Cody stat board</h2>
            {stats?.supervisor?.summary ? (
              <p className="text-[11px] text-slate-400 mt-1">{stats.supervisor.summary}</p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col sm:items-end gap-2">
          <span
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-medium ${
              online
                ? "bg-emerald-500/10 border border-emerald-500/25 text-emerald-200"
                : "bg-slate-500/10 border border-slate-500/25 text-slate-400"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${online ? "bg-emerald-400 pulse-dot" : "bg-slate-500"}`} />
            {online ? `Online · ${channelLabel}` : "Offline"}
          </span>
          <button
            type="button"
            onClick={openCodyPet}
            className="text-[11px] px-3 py-1 rounded-full border border-amber-400/30 text-amber-200 hover:bg-amber-500/10"
          >
            Chat with Cody
          </button>
        </div>
      </div>

      <div className="p-5 sm:p-6 grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatTile icon={Timer} label="Lifetime uptime" value={formatDuration(stats?.uptimeMs ?? 0)} caption={`Since ${formatWhen(stats?.startedAt ?? null)}`} />
        <StatTile icon={MessageCircle} label="Messages" value={String(stats?.messagesTotal ?? 0)} caption={`${stats?.messagesUser ?? 0} in · ${stats?.messagesAssistant ?? 0} out`} />
        <StatTile icon={Route} label="NIO tasks routed" value={String(stats?.nioTasksTotal ?? 0)} caption={`${stats?.nioTasksSuccess ?? 0} ok · ${stats?.nioTasksFailed ?? 0} failed`} />
        <StatTile icon={AlertTriangle} label="Quota events" value={String(stats?.quotaEvents ?? 0)} caption={`Telemetry tagged: ${stats?.telegramTelemetryCount ?? 0}`} accent={(stats?.quotaEvents ?? 0) > 0 ? "amber" : undefined} />
      </div>

      {commsLines.length > 0 ? (
        <div className="px-5 sm:px-6 pb-4 border-t border-white/[0.05] pt-4">
          <button
            type="button"
            onClick={() => setCommsOpen((v) => !v)}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-white w-full"
          >
            {commsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            Recent agent comms ({commsLines.length})
          </button>
          {commsOpen ? (
            <ul className="mt-3 space-y-2">
              {commsLines.map((line) => (
                <li key={line.messageId} className="text-[11px] text-slate-400 leading-relaxed">
                  <span className="text-slate-300 font-medium">{line.headline}</span>
                  {" — "}
                  {line.body.replace(/\*\*/g, "")}
                </li>
              ))}
              <li className="pt-2">
                <button
                  type="button"
                  onClick={openCommsView}
                  className="text-[11px] text-amber-300 hover:text-amber-200"
                >
                  Open full audit →
                </button>
              </li>
            </ul>
          ) : null}
        </div>
      ) : null}

      <div className="px-5 sm:px-6 pb-5 sm:pb-6 flex flex-wrap gap-4 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5" />
          Last heartbeat: {formatWhen(stats?.lastHeartbeatAt ?? null)}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Zap className="w-3.5 h-3.5" />
          Last activity: {formatWhen(stats?.lastActivityAt ?? null)}
        </span>
        <span className="text-slate-600">{stats?.route ?? "Cody supervisor → NIO"}</span>
      </div>
    </section>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
  caption,
  accent,
}: {
  icon: typeof Timer;
  label: string;
  value: string;
  caption: string;
  accent?: "amber";
}) {
  return (
    <div className={`rounded-xl p-4 border ${accent === "amber" ? "border-amber-400/25 bg-amber-500/[0.06]" : "border-white/[0.07] bg-white/[0.025]"}`}>
      <div className="flex items-center gap-2 text-slate-500">
        <Icon className="w-3.5 h-3.5" />
        <p className="text-[10px] uppercase tracking-wider">{label}</p>
      </div>
      <p className="text-2xl font-semibold text-white mt-2">{value}</p>
      <p className="text-[11px] text-slate-500 mt-1">{caption}</p>
    </div>
  );
}
