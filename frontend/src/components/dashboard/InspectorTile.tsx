import { Eye } from "lucide-react";
import { palette, type NetworkNode } from "@/data/network";
import { ModuleHeader, StatusDot, Tile } from "./shared";

const kindLabel: Record<NetworkNode["kind"], string> = {
  core: "Core",
  domain: "Domain cluster",
  topic: "Topic",
  agent: "Specialist agent",
};

export function InspectorTile({
  node,
  dimmed,
  hasPreset,
}: {
  node: NetworkNode;
  dimmed: boolean;
  hasPreset: boolean;
}) {
  const color = palette[node.color] ?? palette.slate;

  return (
    <Tile dimmed={dimmed} accent={color.line} className="p-4 h-full">
      <ModuleHeader
        icon={<Eye className="w-4 h-4" />}
        title="Inspector"
        status={<StatusDot tone="active" label="Selected" />}
      />

      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
        {kindLabel[node.kind]}
      </p>
      <h4 className="text-base font-semibold text-white mt-1 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color.line }} />
        <span className="truncate">{node.label}</span>
      </h4>

      {node.tags && node.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {node.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 rounded-md bg-white/[0.05] border border-white/[0.06] text-[10px] text-slate-400 font-mono"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <p className="text-xs leading-relaxed text-slate-400 mt-3">{node.description}</p>

      <dl className="mt-3 grid grid-cols-2 gap-2">
        {node.sources !== undefined && (
          <div className="rounded-lg bg-white/[0.03] border border-white/[0.05] px-2.5 py-2">
            <dt className="text-[9px] uppercase tracking-[0.12em] text-slate-600">Sources</dt>
            <dd className="text-sm font-semibold text-slate-200 tabular-nums">{node.sources}</dd>
          </div>
        )}
        <div className="rounded-lg bg-white/[0.03] border border-white/[0.05] px-2.5 py-2">
          <dt className="text-[9px] uppercase tracking-[0.12em] text-slate-600">Task preset</dt>
          <dd className={`text-xs font-medium mt-0.5 ${hasPreset ? "text-cyan-300" : "text-slate-500"}`}>
            {hasPreset ? "Loaded" : "Manual"}
          </dd>
        </div>
      </dl>
    </Tile>
  );
}
