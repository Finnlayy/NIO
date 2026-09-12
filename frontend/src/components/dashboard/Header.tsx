import { BrainCircuit, Search, Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";

export function Header({
  search,
  onSearch,
  onMasterSummary,
}: {
  search: string;
  onSearch: (value: string) => void;
  onMasterSummary: () => void;
}) {
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTagName = document.activeElement?.tagName.toLowerCase();
      if (activeTagName === "input" || activeTagName === "textarea" || (document.activeElement as HTMLElement)?.isContentEditable) {
        if (e.key === "Escape" && document.activeElement === searchInputRef.current) {
          searchInputRef.current?.blur();
        }
        return;
      }

      if (e.key === "/" || (e.key === "k" && (e.metaKey || e.ctrlKey))) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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
          ref={searchInputRef}
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Filter modules, nodes, tags …"
          className="console-input pl-9 pr-12 py-2 text-[13px]"
          aria-label="Search network nodes"
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none flex items-center gap-1">
          <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[9px] font-mono text-slate-400 bg-slate-800/50 border border-slate-700 rounded shadow-sm">
            /
          </kbd>
        </div>
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
