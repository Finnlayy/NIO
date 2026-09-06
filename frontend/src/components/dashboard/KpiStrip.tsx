import { Boxes, Bot, Gauge, Share2, Waypoints } from "lucide-react";
import { Tile } from "./shared";

function Kpi({
  icon,
  value,
  label,
  sub,
}: {
  icon: React.ReactNode;
  value: string | number;
  label: string;
  sub: string;
}) {
  return (
    <Tile className="p-3.5 flex items-center gap-3">
      <span className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.06] grid place-items-center text-slate-400 shrink-0">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-lg font-semibold text-white leading-tight tabular-nums">
          {value}
        </span>
        <span className="block text-[10px] uppercase tracking-[0.12em] text-slate-500 truncate">
          {label}
        </span>
        <span className="block text-[10px] text-slate-600 truncate">{sub}</span>
      </span>
    </Tile>
  );
}

export function KpiStrip({
  nodeCount,
  domainCount,
  agentCount,
  edgeCount,
  latencyMs,
}: {
  nodeCount: number;
  domainCount: number;
  agentCount: number;
  edgeCount: number;
  latencyMs: number | null;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-3">
      <Kpi icon={<Boxes className="w-4 h-4" />} value={nodeCount} label="Nodes Online" sub="graph registered" />
      <Kpi icon={<Waypoints className="w-4 h-4" />} value={domainCount} label="Active Domains" sub="knowledge clusters" />
      <Kpi icon={<Bot className="w-4 h-4" />} value={agentCount} label="Agents Routed" sub="specialist roles" />
      <Kpi icon={<Share2 className="w-4 h-4" />} value={edgeCount} label="Links Active" sub="mesh connections" />
      <Kpi
        icon={<Gauge className="w-4 h-4" />}
        value={latencyMs === null ? "—" : `${latencyMs}ms`}
        label="Last Routing"
        sub="core latency"
      />
    </div>
  );
}
