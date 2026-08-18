"use client";

import type { FormattedInterAgentLine } from "@/lib/manifest-types";

function severityClass(severity: FormattedInterAgentLine["severity"]): string {
  switch (severity) {
    case "success":
      return "border-emerald-500/25 bg-emerald-500/10 text-emerald-100";
    case "warning":
      return "border-amber-500/25 bg-amber-500/10 text-amber-100";
    case "error":
      return "border-rose-500/25 bg-rose-500/10 text-rose-100";
    default:
      return "border-white/10 bg-white/[0.04] text-slate-300";
  }
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

/** Render formatted inter-agent lines as system bubbles. */
export default function CodyCommsTimeline({ lines }: { lines: FormattedInterAgentLine[] }) {
  if (lines.length === 0) return null;

  return (
    <div className="space-y-2 pb-2 border-b border-white/[0.06] mb-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-600 px-1">Agent comms</p>
      {lines.slice(0, 8).map((line) => (
        <article
          key={line.messageId}
          className={`rounded-lg border px-3 py-2 text-xs leading-relaxed ${severityClass(line.severity)}`}
        >
          <div className="flex justify-between gap-2 mb-0.5">
            <span className="font-medium">{line.headline}</span>
            <span className="text-[10px] opacity-60 shrink-0">{formatTime(line.timestamp)}</span>
          </div>
          <p className="opacity-90">{line.body.replace(/\*\*/g, "")}</p>
        </article>
      ))}
    </div>
  );
}
