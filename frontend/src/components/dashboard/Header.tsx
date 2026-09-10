import { useEffect, useRef } from "react";
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
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is already typing in an input or textarea
      if (
        e.key === "/" &&
        document.activeElement?.tagName !== "INPUT" &&
        document.activeElement?.tagName !== "TEXTAREA"
      ) {
        e.preventDefault();
        inputRef.current?.focus();
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

      <div className="hidden md:flex flex-1 max-w-sm ml-auto relative group">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input
          ref={inputRef}
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Filter modules, nodes, tags …"
          className="console-input peer pl-9 pr-8 py-2 text-[13px]"
          aria-label="Search network nodes"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 hidden md:inline-flex items-center justify-center h-5 px-1.5 text-[10px] font-medium font-mono text-slate-500 bg-white/[0.05] border border-white/[0.1] rounded opacity-0 group-hover:opacity-100 transition-opacity peer-focus:opacity-100">
          /
        </kbd>
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
