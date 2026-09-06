import { BrainCircuit, ScanEye } from "lucide-react";
import { palette, networkNodes, type NetworkNode } from "@/data/network";
import { ModuleHeader, StatusDot, Tile } from "./shared";

export function CoreTile({
  node,
  selected,
  dimmed,
  onSelect,
}: {
  node: NetworkNode;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
}) {
  const color = palette[node.color] ?? palette.yellow;

  return (
    <Tile
      onClick={onSelect}
      selected={selected}
      dimmed={dimmed}
      accent={color.line}
      className="p-4 h-full flex flex-col"
    >
      <ModuleHeader
        icon={<BrainCircuit className="w-4 h-4" />}
        title="Core Synthesis Hub"
        meta="neural-core"
        status={<StatusDot tone="online" pulse label="Online" />}
      />

      <div className="flex items-center gap-3 mt-1">
        <span
          className="w-11 h-11 rounded-full grid place-items-center border shrink-0"
          style={{ borderColor: color.border, background: color.fill }}
        >
          <BrainCircuit className="w-5 h-5" style={{ color: color.text }} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white truncate">{node.label}</p>
          <p className="text-[11px] text-slate-500">Cross-domain routing · middleware pipeline</p>
        </div>
      </div>

      <p className="text-xs leading-relaxed text-slate-400 mt-3">{node.description}</p>

      <div className="mt-auto pt-3 grid grid-cols-3 gap-2 text-center">
        <Stat value={networkNodes.filter((n) => n.kind !== "core").length} label="linked nodes" />
        <Stat value={node.sources ?? 0} label="sources" />
        <Stat value={node.tags?.length ?? 0} label="capabilities" />
      </div>

      <p className="flex items-center gap-1.5 text-[10px] text-slate-600 mt-3">
        <ScanEye className="w-3 h-3" />
        Click to inspect and load the master task
      </p>
    </Tile>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-lg bg-white/[0.03] border border-white/[0.05] py-2">
      <p className="text-sm font-semibold text-white tabular-nums">{value}</p>
      <p className="text-[9px] uppercase tracking-[0.12em] text-slate-600">{label}</p>
    </div>
  );
}
