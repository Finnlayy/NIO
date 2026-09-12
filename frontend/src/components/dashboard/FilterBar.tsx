import { Filter } from "lucide-react";
import { domainFilters, palette, type DomainId } from "@/data/network";

export function FilterBar({
  activeFilter,
  onFilter,
}: {
  activeFilter: DomainId | "all";
  onFilter: (id: DomainId | "all") => void;
}) {
  return (
    <div className="flex items-center gap-2 px-4 sm:px-6 py-2.5 border-b border-white/[0.06] bg-[#0a0d16] overflow-x-auto">
      <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-slate-600 shrink-0 mr-1">
        <Filter className="w-3 h-3" />
        Domain
      </span>
      {domainFilters.map((filter) => {
        const active = activeFilter === filter.id;
        const color = palette[filter.color] ?? palette.slate;
        return (
          <button
            key={filter.id}
            onClick={() => onFilter(filter.id)}
            className={`shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
              active
                ? "bg-white/[0.08] text-white border-white/15"
                : "text-slate-500 border-transparent hover:text-slate-200 hover:bg-white/[0.04]"
            }`}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: active ? color.line : "rgba(148,163,184,0.4)" }}
            />
            {filter.icon} {filter.label}
          </button>
        );
      })}
    </div>
  );
}
