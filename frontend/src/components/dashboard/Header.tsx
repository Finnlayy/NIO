import { BrainCircuit, Search, Sparkles } from "lucide-react";

export function Header({
  search,
  onSearch,
  onMasterSummary,
}: {
  search: string;
  onSearch: (value: string) => void;
  onMasterSummary: () => void;
}) {
  return (
    <header className="sticky top-0 z-30 h-14 border-b border-white/[0.06] bg-[#090b12]/90 backdrop-blur-xl px-4 sm:px-6 flex items-center gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 via-orange-500 to-rose-500 grid place-items-center shrink-0">
          <BrainCircuit className="w-4 h-4 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-white leading-tight truncate">
            NEURAL INTELLIGENCE NETWORK
          </p>
          <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500 leading-tight">
            Monitoring Grid
          </p>
        </div>
      </div>

      <div className="hidden md:flex flex-1 max-w-sm ml-auto relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Filter modules, nodes, tags …"
          className="console-input pl-9 py-2 text-[13px]"
          aria-label="Search network nodes"
        />
      </div>

      <button
        onClick={onMasterSummary}
        className="hidden sm:inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-amber-400/25 bg-amber-400/10 text-amber-100 text-xs font-medium hover:bg-amber-400/15 transition-colors ml-auto md:ml-0"
      >
        <Sparkles className="w-3.5 h-3.5" />
        Master Summary
      </button>
    </header>
  );
}
