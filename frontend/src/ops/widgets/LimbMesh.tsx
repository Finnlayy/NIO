import { palette } from "@/data/network";
import { Insight } from "./bits";

interface MeshNode {
  id: string;
  label: string;
  kind: string;
  color: string;
}
interface MeshEdge {
  from: string;
  to: string;
  color: string;
}

export function LimbMesh({ data }: { data: Record<string, unknown> }) {
  const nodes = (data.nodes as MeshNode[]) ?? [];
  const edges = (data.edges as MeshEdge[]) ?? [];
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const positions: Record<string, { x: number; y: number }> = {
    "neural-core": { x: 50, y: 46 },
    "ml-architect": { x: 22, y: 22 },
    "dp-engineer": { x: 78, y: 22 },
    "domain-ml": { x: 16, y: 48 },
    "domain-prompts": { x: 34, y: 74 },
    "domain-dp": { x: 66, y: 74 },
    "domain-trading": { x: 84, y: 48 },
    "topic-knapsack": { x: 58, y: 90 },
    "topic-transformer": { x: 9, y: 70 },
    "topic-lcs": { x: 91, y: 70 },
  };

  return (
    <div className="flex flex-col h-full">
      <div className="relative flex-1 min-h-[190px] rounded-lg bg-black/25 border border-white/[0.05] overflow-hidden">
        <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
          {edges.map((e, i) => {
            const a = positions[e.from];
            const b = positions[e.to];
            if (!a || !b) return null;
            const color = palette[e.color]?.line ?? "#475569";
            return (
              <line
                key={i}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={color}
                strokeWidth="0.25"
                opacity="0.45"
              />
            );
          })}
        </svg>
        {nodes.map((n) => {
          const pos = positions[n.id] ?? { x: 50, y: 50 };
          const color = palette[n.color] ?? palette.slate;
          const isCore = n.kind === "core";
          return (
            <div
              key={n.id}
              className="absolute -translate-x-1/2 -translate-y-1/2 text-center"
              style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
              title={`${n.label} · ${n.kind}`}
            >
              <span
                className={`inline-flex items-center justify-center rounded-full border ${
                  isCore ? "w-12 h-12" : "w-8 h-8"
                }`}
                style={{
                  borderColor: color.border,
                  background: color.fill,
                }}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${isCore ? "w-2.5 h-2.5" : ""}`} style={{ background: color.line }} />
              </span>
              <p className="text-[8px] text-slate-400 mt-0.5 whitespace-nowrap max-w-[72px] truncate">
                {n.label}
              </p>
            </div>
          );
        })}
        {/* live edges readout */}
        <span className="absolute top-2 right-2 text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
          {edges.length} links · live
        </span>
      </div>

      <div className="flex items-center gap-3 mt-2 text-[10px] text-slate-500">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> core</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-purple-400" /> agents</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-slate-400" /> domains</span>
      </div>

      <Insight>
        NIO limb mesh hydrated from the orchestrator registry: {byId.size} nodes routed through
        neural-core — MCP hydration keeps topology in sync with the Python limb registry.
      </Insight>
    </div>
  );
}
