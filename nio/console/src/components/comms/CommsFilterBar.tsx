"use client";

import { Search } from "lucide-react";
import type { CommsFilterScope } from "@/lib/manifest-types";
import type { CommsChannelFilter, CommsSeverityFilter } from "./comms-filter";

export default function CommsFilterBar({
  scope,
  channel,
  severity,
  search,
  onScopeChange,
  onChannelChange,
  onSeverityChange,
  onSearchChange,
}: {
  scope: CommsFilterScope;
  channel: CommsChannelFilter;
  severity: CommsSeverityFilter;
  search: string;
  onScopeChange: (v: CommsFilterScope) => void;
  onChannelChange: (v: CommsChannelFilter) => void;
  onSeverityChange: (v: CommsSeverityFilter) => void;
  onSearchChange: (v: string) => void;
}) {
  const channels: { id: CommsChannelFilter; label: string }[] = [
    { id: "all", label: "All channels" },
    { id: "atlas", label: "Atlas" },
    { id: "cody", label: "Cody" },
    { id: "you", label: "You" },
    { id: "limbs", label: "Limbs" },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-lg border border-white/10 p-0.5 bg-white/[0.03]">
          <button
            type="button"
            onClick={() => onScopeChange("relevant")}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              scope === "relevant"
                ? "bg-amber-500/20 text-amber-100 border border-amber-400/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Relevant
          </button>
          <button
            type="button"
            onClick={() => onScopeChange("all")}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              scope === "all"
                ? "bg-cyan-500/20 text-cyan-100 border border-cyan-400/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            All traffic
          </button>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {channels.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => onChannelChange(c.id)}
              className={`text-[10px] px-2.5 py-1 rounded-full border transition-colors ${
                channel === c.id
                  ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-100"
                  : "border-white/10 text-slate-500 hover:text-slate-200 hover:border-white/20"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="search"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search headlines, actors, body…"
            className="console-input w-full pl-10 text-sm"
          />
        </div>
        <select
          value={severity}
          onChange={(e) => onSeverityChange(e.target.value as CommsSeverityFilter)}
          className="console-input text-sm sm:w-40"
        >
          <option value="all">All severity</option>
          <option value="info">Info</option>
          <option value="success">Success</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select>
      </div>
    </div>
  );
}
