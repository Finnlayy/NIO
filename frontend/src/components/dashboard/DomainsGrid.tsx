import { Layers } from "lucide-react";
import {
  domainFilters,
  networkEdges,
  networkNodes,
  palette,
  type DomainId,
  type NetworkNode,
} from "@/data/network";
import { ModuleHeader, StatusDot, Tile } from "./shared";

const DOMAIN_CLUSTERS = domainFilters
  .filter((filter) => filter.id !== "all")
  .map((filter) => {
    const nodes = networkNodes.filter((node) => node.domain === filter.id);
    const domainNode = nodes.find((node) => node.kind === "domain");
    const topics = nodes.filter((node) => node.kind === "topic");
    const links = networkEdges.filter((edge) => {
      const from = networkNodes.find((n) => n.id === edge.from);
      const to = networkNodes.find((n) => n.id === edge.to);
      return from?.domain === filter.id || to?.domain === filter.id;
    }).length;
    return { filter, nodes, domainNode, topics, links };
  });

export function DomainsGrid({
  visibleIds,
  selectedId,
  onSelectNode,
}: {
  visibleIds: Set<string>;
  selectedId: string;
  onSelectNode: (id: string) => void;
}) {
  return (
    <Tile className="p-4 h-full">
      <ModuleHeader
        icon={<Layers className="w-4 h-4" />}
        title="Domain Clusters"
        meta={<><span className="font-mono tabular-nums">{DOMAIN_CLUSTERS.filter((d) => d.nodes.length > 0).length}</span> active</>}
        status={<StatusDot tone="active" label="Mesh" />}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {DOMAIN_CLUSTERS.map(({ filter, nodes, domainNode, topics, links }) => {
          const color = palette[filter.color] ?? palette.slate;
          const idle = nodes.length === 0;
          const selected = domainNode?.id === selectedId || topics.some((t) => t.id === selectedId);
          const dimmed = nodes.length > 0 && !nodes.some((node) => visibleIds.has(node.id));

          return (
            <Tile
              key={filter.id}
              accent={color.line}
              selected={selected}
              dimmed={dimmed}
              onClick={
                domainNode
                  ? () => onSelectNode(domainNode.id)
                  : undefined
              }
              className="p-3.5"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-base leading-none">{filter.icon}</span>
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-slate-100 truncate">
                      {filter.label}
                    </p>
                    <p className="text-[10px] text-slate-600 font-mono truncate">
                      {filter.id}
                    </p>
                  </div>
                </div>
                <StatusDot tone={idle ? "idle" : "online"} pulse={!idle} />
              </div>

              <p className="text-[11px] text-slate-500 mt-2 leading-relaxed min-h-[32px]">
                {idle
                  ? "Standby — no knowledge nodes registered yet."
                  : domainNode?.description ?? "Cluster node pending registration."}
              </p>

              {topics.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {topics.map((topic) => (
                    <TopicChip
                      key={topic.id}
                      topic={topic}
                      onSelect={onSelectNode}
                      dimmed={!visibleIds.has(topic.id)}
                    />
                  ))}
                </div>
              )}

              <div className="flex items-center gap-3 mt-3 pt-2.5 border-t border-white/[0.05] text-[10px] text-slate-600">
                <span><span className="font-mono tabular-nums">{nodes.length}</span> nodes</span>
                <span><span className="font-mono tabular-nums">{links}</span> links</span>
              </div>
            </Tile>
          );
        })}
      </div>
    </Tile>
  );
}

const TOPIC_COLOR_CLASSES: Record<string, string> = {
  yellow: "text-[#fef08a]",
  purple: "text-[#e9d5ff]",
  orange: "text-[#fed7aa]",
  green: "text-[#bbf7d0]",
  cyan: "text-[#a5f3fc]",
  blue: "text-[#bfdbfe]",
  red: "text-[#fecdd3]",
  slate: "text-[#e2e8f0]",
};

function TopicChip({
  topic,
  onSelect,
  dimmed,
}: {
  topic: NetworkNode;
  onSelect: (id: string) => void;
  dimmed: boolean;
}) {
  const textColorClass = TOPIC_COLOR_CLASSES[topic.color] ?? TOPIC_COLOR_CLASSES.slate;

  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onSelect(topic.id);
      }}
      className={`px-2 py-1 rounded-md text-[10px] font-medium border border-white/10 bg-white/5 transition-colors ${textColorClass} ${
        dimmed ? "opacity-40" : "hover:border-current"
      }`}
    >
      {topic.shortLabel.replace("\n", " ")}
    </button>
  );
}
