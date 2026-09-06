import { Bot } from "lucide-react";
import { networkNodes, palette } from "@/data/network";
import { ModuleHeader, StatusDot, Tile } from "./shared";

export function AgentsTile({
  visibleIds,
  selectedId,
  onSelect,
}: {
  visibleIds: Set<string>;
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const agents = networkNodes.filter((node) => node.kind === "agent");

  return (
    <Tile className="p-4 h-full">
      <ModuleHeader
        icon={<Bot className="w-4 h-4" />}
        title="Specialist Agents"
        meta={`${agents.length} routed`}
        status={<StatusDot tone="active" label="Live" />}
      />

      <div className="grid grid-cols-2 gap-2.5">
        {agents.map((agent) => {
          const color = palette[agent.color] ?? palette.slate;
          const dimmed = !visibleIds.has(agent.id);
          const selected = selectedId === agent.id;
          return (
            <Tile
              key={agent.id}
              onClick={() => onSelect(agent.id)}
              dimmed={dimmed}
              selected={selected}
              accent={color.line}
              className="p-3 h-full"
            >
              <span
                className="w-8 h-8 rounded-lg grid place-items-center border"
                style={{ borderColor: color.border, background: color.fill }}
              >
                <Bot className="w-4 h-4" style={{ color: color.text }} />
              </span>
              <p className="text-[12px] font-medium text-slate-100 mt-2 leading-tight">
                {agent.label}
              </p>
              <p className="text-[10px] text-slate-500 mt-1 leading-snug line-clamp-2">
                {agent.description}
              </p>
              <p className="mt-2">
                <StatusDot tone="online" />
              </p>
            </Tile>
          );
        })}
      </div>
    </Tile>
  );
}
