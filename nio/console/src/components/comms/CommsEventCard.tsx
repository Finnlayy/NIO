"use client";

import type { FormattedInterAgentLine } from "@/lib/manifest-types";
import CommsApprovalBar from "./CommsApprovalBar";

function severityClass(severity: FormattedInterAgentLine["severity"]): string {
  switch (severity) {
    case "success":
      return "border-emerald-500/25 bg-emerald-500/10";
    case "warning":
      return "border-amber-500/25 bg-amber-500/10";
    case "error":
      return "border-rose-500/25 bg-rose-500/10";
    default:
      return "border-white/10 bg-white/[0.04]";
  }
}

function severityDot(severity: FormattedInterAgentLine["severity"]): string {
  switch (severity) {
    case "success":
      return "bg-emerald-400";
    case "warning":
      return "bg-amber-400";
    case "error":
      return "bg-rose-400";
    default:
      return "bg-cyan-400";
  }
}

function channelRailColor(from: string, to: string): string {
  if (from === "Cody" || to === "Cody") return "from-amber-400 to-amber-600";
  if (from === "You" || to === "You") return "from-rose-400 to-rose-600";
  if (from === "Atlas" || to === "Atlas") return "from-cyan-400 to-cyan-600";
  if (from === "Limb" || to === "Limb" || from === "Subagent" || to === "Subagent") {
    return "from-violet-400 to-violet-600";
  }
  return "from-slate-500 to-slate-600";
}

function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function isCodySourced(line: FormattedInterAgentLine): boolean {
  return line.actors.from === "Cody" || line.type === "cody_relay";
}

export default function CommsEventCard({
  line,
  isNew,
  onApprovalComplete,
}: {
  line: FormattedInterAgentLine;
  isNew?: boolean;
  onApprovalComplete?: () => void;
}) {
  const rail = channelRailColor(line.actors.from, line.actors.to);
  const codyBadge = isCodySourced(line);

  return (
    <article
      className={`relative flex gap-3 rounded-xl border overflow-hidden transition-all ${severityClass(line.severity)} ${
        isNew ? "comms-signal-pulse" : ""
      }`}
    >
      <div
        className={`w-1 shrink-0 bg-gradient-to-b ${rail} ${isNew ? "animate-pulse" : ""}`}
        aria-hidden
      />
      <div className="flex-1 min-w-0 py-3 pr-4 pl-1">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className={`w-2 h-2 rounded-full shrink-0 ${severityDot(line.severity)}`} />
          <span className="text-[10px] font-mono text-slate-500">{formatTime(line.timestamp)}</span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] border border-white/10 text-slate-400">
            {line.actors.from} → {line.actors.to}
          </span>
          {codyBadge ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-400/25 text-amber-200">
              ⚡ Cody
            </span>
          ) : null}
          {line.type ? (
            <span className="text-[10px] text-slate-600 uppercase tracking-wider">{line.type.replace(/_/g, " ")}</span>
          ) : null}
        </div>
        <h3 className="text-sm font-medium text-white">{line.headline}</h3>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">{line.body.replace(/\*\*/g, "")}</p>
        {line.requiresAction || line.type === "approval_request" ? (
          <CommsApprovalBar line={line} onComplete={onApprovalComplete} />
        ) : null}
      </div>
    </article>
  );
}
