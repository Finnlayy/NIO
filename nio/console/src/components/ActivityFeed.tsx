"use client";

import { ChevronRight } from "lucide-react";
import type { MockActivity } from "@/data/mock-orchestrator";
import type { FormattedInterAgentLine } from "@/lib/manifest-types";
import { openCommsView } from "@/hooks/useCommsAudit";
import { useActivityFeed } from "@/hooks/useActivityFeed";

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

function activityStyle(type: MockActivity["type"]): string {
  if (type === "success") return "bg-emerald-400";
  if (type === "warning") return "bg-amber-400";
  if (type === "review") return "bg-violet-400";
  return "bg-cyan-400";
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

function InterAgentLineItem({ line }: { line: FormattedInterAgentLine }) {
  const needsAction = line.requiresAction || line.type === "approval_request";

  return (
    <div className="flex gap-3">
      <div className="pt-1">
        <i className={`block w-2 h-2 rounded-full ${severityDot(line.severity)}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex justify-between gap-3">
          <p className="text-sm text-slate-200 min-w-0">
            <span className="font-medium text-white">
              {line.actors.from} → {line.actors.to}
            </span>
            <span className="text-slate-500"> · </span>
            <span className="text-slate-300">{line.headline}</span>
          </p>
          <span className="text-[10px] text-slate-600 whitespace-nowrap shrink-0">
            {formatTime(line.timestamp)}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-slate-500 mt-1 line-clamp-2">
          {line.body.replace(/\*\*/g, "")}
        </p>
        {needsAction ? (
          <span className="inline-flex mt-1.5 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-400/25 text-amber-200">
            Action required
          </span>
        ) : null}
      </div>
    </div>
  );
}

function TelemetryLineItem({ activity }: { activity: MockActivity }) {
  return (
    <div className="flex gap-3">
      <div className="pt-1">
        <i className={`block w-2 h-2 rounded-full ${activityStyle(activity.type)}`} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex justify-between gap-3">
          <p className="text-sm text-slate-200">
            <span className="font-medium text-white">{activity.agent}</span> · {activity.action}
          </p>
          <span className="text-[10px] text-slate-600 whitespace-nowrap">{activity.timestamp}</span>
        </div>
        <p className="text-xs leading-relaxed text-slate-500 mt-1">{activity.detail}</p>
      </div>
    </div>
  );
}

export default function ActivityFeed({
  activities,
  orchestratorLive,
}: {
  activities: MockActivity[];
  orchestratorLive: boolean;
}) {
  const { lines, apiLive: busLive, loading } = useActivityFeed();
  const showBus = busLive && lines.length > 0;
  const live = showBus ? busLive : orchestratorLive;

  return (
    <section className="console-card overflow-hidden">
      <div className="p-5 sm:p-6 flex items-center justify-between border-b border-white/[0.07]">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500">
            {showBus ? "Inter-agent bus" : "Event stream"}
          </p>
          <h2 className="text-lg font-semibold text-white mt-1">
            {showBus ? "Signal tape" : "Recent system signals"}
          </h2>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span
            className={`flex items-center gap-1.5 text-xs ${
              live ? "text-emerald-300" : "text-slate-500"
            }`}
          >
            <i
              className={`w-1.5 h-1.5 rounded-full ${
                live ? "bg-emerald-400 pulse-dot" : "bg-slate-600"
              }`}
            />
            {live ? (showBus ? "Bus live" : "Live stream") : loading ? "Connecting…" : "Offline"}
          </span>
          {showBus ? (
            <button
              type="button"
              onClick={openCommsView}
              className="text-[11px] text-cyan-300 hover:text-cyan-100 flex items-center gap-0.5"
            >
              Full audit <ChevronRight className="w-3 h-3" />
            </button>
          ) : null}
        </div>
      </div>
      <div className="p-4 sm:p-5 space-y-4">
        {showBus
          ? lines.slice(0, 5).map((line) => <InterAgentLineItem key={line.messageId} line={line} />)
          : activities.slice(0, 5).map((activity) => (
              <TelemetryLineItem key={activity.id} activity={activity} />
            ))}
        {!showBus && activities.length === 0 ? (
          <p className="text-sm text-slate-500 py-4 text-center">No recent signals</p>
        ) : null}
        {showBus && lines.length === 0 ? (
          <p className="text-sm text-slate-500 py-4 text-center">No inter-agent traffic yet</p>
        ) : null}
      </div>
    </section>
  );
}
