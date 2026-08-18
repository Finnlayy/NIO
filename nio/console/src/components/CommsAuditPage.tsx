"use client";

import { useEffect } from "react";
import { CircleDot, RefreshCw, Radio } from "lucide-react";
import CommsEventCard from "@/components/comms/CommsEventCard";
import CommsFilterBar from "@/components/comms/CommsFilterBar";
import { useCommsAudit } from "@/hooks/useCommsAudit";

function formatLastUpdated(d: Date | null): string {
  if (!d) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(d);
}

export default function CommsAuditPage() {
  const audit = useCommsAudit({ enabled: true });

  useEffect(() => {
    audit.markRead();
  }, [audit.markRead]);

  return (
    <div className="space-y-5">
      <header className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-amber-300" />
            <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Signal tape · inter-agent bus</p>
          </div>
          <h1 className="text-2xl font-semibold text-white mt-1">Comms audit</h1>
          <p className="text-sm text-slate-400 mt-1 max-w-xl">
            User-relevant Cody, gate, and limb events. Toggle all traffic for full bus debug view.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {!audit.apiExtended ? (
            <span className="text-[10px] px-2 py-1 rounded-full border border-amber-500/25 bg-amber-500/10 text-amber-200">
              API upgrade pending
            </span>
          ) : null}
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-medium ${
              audit.apiLive
                ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-200"
                : "bg-amber-500/10 border border-amber-500/20 text-amber-200"
            }`}
          >
            <CircleDot className="w-3.5 h-3.5" />
            {audit.apiLive ? "Live" : "Offline"}
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            Updated {formatLastUpdated(audit.lastUpdated)}
          </span>
          <button
            type="button"
            onClick={() => void audit.refresh()}
            disabled={audit.loading}
            className="p-2 rounded-lg border border-white/10 text-slate-400 hover:text-white hover:border-white/20 disabled:opacity-50"
            aria-label="Refresh comms"
          >
            <RefreshCw className={`w-4 h-4 ${audit.loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      <section className="console-card p-4 sm:p-5">
        <CommsFilterBar
          scope={audit.scope}
          channel={audit.channel}
          severity={audit.severity}
          search={audit.search}
          onScopeChange={audit.setScope}
          onChannelChange={audit.setChannel}
          onSeverityChange={audit.setSeverity}
          onSearchChange={audit.setSearch}
        />
      </section>

      <section className="console-card overflow-hidden min-h-[480px] flex flex-col">
        <div className="px-5 py-3 border-b border-white/[0.07] flex items-center justify-between">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Signal tape · {audit.filteredLines.length} event{audit.filteredLines.length === 1 ? "" : "s"}
          </p>
          {audit.scope === "relevant" ? (
            <span className="text-[10px] text-amber-300/80">Filtered to user-relevant</span>
          ) : (
            <span className="text-[10px] text-cyan-300/80">All bus traffic</span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-3 max-h-[calc(100vh-22rem)]">
          {audit.loading && audit.filteredLines.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-16">Loading signal tape…</p>
          ) : audit.filteredLines.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-16">
              {audit.apiLive
                ? "No comms match your filters. Try All traffic or adjust channel chips."
                : "NIO API offline — comms will appear when backend is reachable."}
            </p>
          ) : (
            audit.filteredLines.map((line) => (
              <CommsEventCard
                key={line.messageId}
                line={line}
                isNew={audit.newMessageIds.has(line.messageId)}
                onApprovalComplete={() => void audit.refresh()}
              />
            ))
          )}
        </div>

        <footer className="px-5 py-4 border-t border-white/[0.07] bg-white/[0.02]">
          <label className="flex items-center gap-3 cursor-pointer group">
            <button
              type="button"
              role="switch"
              aria-checked={audit.publishToBus}
              onClick={() => audit.togglePublishToBus(!audit.publishToBus)}
              className={`relative w-11 h-6 rounded-full transition-colors shrink-0 ${
                audit.publishToBus ? "bg-amber-400" : "bg-slate-700"
              }`}
            >
              <span
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  audit.publishToBus ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
            <div>
              <p className="text-sm text-white group-hover:text-amber-50 transition-colors">
                Publish Cody actions to audit bus
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                When backend ships publish-back, chat sends <code className="text-slate-400">publishToBus: true</code>
              </p>
            </div>
          </label>
        </footer>
      </section>
    </div>
  );
}
