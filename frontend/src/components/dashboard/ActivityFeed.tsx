import { useEffect, useRef } from "react";
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, Info, Radio } from "lucide-react";
import { ModuleHeader, Tile } from "./shared";
import type { FeedEvent, FeedStatus } from "./types";

const statusIcon: Record<FeedStatus, React.ReactNode> = {
  info: <Info className="w-3 h-3 text-cyan-400" />,
  success: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  warn: <AlertTriangle className="w-3 h-3 text-amber-400" />,
  error: <AlertTriangle className="w-3 h-3 text-rose-400" />,
  trace: <ArrowRight className="w-3 h-3 text-slate-500" />,
};

export function ActivityFeed({ events }: { events: FeedEvent[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events]);

  return (
    <Tile className="p-4 h-full flex flex-col">
      <ModuleHeader
        icon={<Activity className="w-4 h-4" />}
        title="Activity Stream"
        meta="live event log"
        status={
          <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <Radio className="w-3 h-3 text-emerald-400 pulse-dot" />
            Live
          </span>
        }
      />

      <div className="overflow-y-auto max-h-44 pr-1 -mr-1 space-y-1.5">
        {events.map((event) => (
          <div
            key={event.id}
            className="flex items-start gap-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] px-2.5 py-2"
          >
            <span className="mt-0.5 shrink-0">{statusIcon[event.status]}</span>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-slate-300 leading-snug">
                <span className="text-slate-500 font-mono mr-1.5">{event.timestamp}</span>
                <span className="font-medium">{event.label}</span>
                {event.detail && (
                  <span className="text-slate-500"> · {event.detail}</span>
                )}
              </p>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </Tile>
  );
}
