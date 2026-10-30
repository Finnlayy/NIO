import React, { useState, useRef, useEffect } from "react";
import { useKanbanStore } from "./useKanbanStore";
import { isFilterActive } from "./board-logic";
import { Filter, X } from "lucide-react";

export const BoardToolbar: React.FC = () => {
  const filter = useKanbanStore(s => s.filter);
  const board = useKanbanStore(s => s.board);
  const setLabelFilter = useKanbanStore(s => s.setLabelFilter);
  const setAssigneeFilter = useKanbanStore(s => s.setAssigneeFilter);
  const resetFilters = useKanbanStore(s => s.resetFilters);
  
  const [labelOpen, setLabelOpen] = useState(false);
  const [personOpen, setPersonOpen] = useState(false);
  
  const labelRef = useRef<HTMLDivElement>(null);
  const personRef = useRef<HTMLDivElement>(null);
  const labelBtnRef = useRef<HTMLButtonElement>(null);
  const personBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (labelOpen) {
          setLabelOpen(false);
          labelBtnRef.current?.focus();
        }
        if (personOpen) {
          setPersonOpen(false);
          personBtnRef.current?.focus();
        }
      }
    }
    
    function onClickOutside(e: MouseEvent) {
      if (labelOpen && labelRef.current && !labelRef.current.contains(e.target as Node)) {
        setLabelOpen(false);
      }
      if (personOpen && personRef.current && !personRef.current.contains(e.target as Node)) {
        setPersonOpen(false);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onClickOutside);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onClickOutside);
    };
  }, [labelOpen, personOpen]);

  const toggleLabel = (id: string) => {
    if (filter.labelIds.includes(id)) {
      setLabelFilter(filter.labelIds.filter(l => l !== id));
    } else {
      setLabelFilter([...filter.labelIds, id]);
    }
  };

  const toggleAssignee = (id: string) => {
    if (filter.assigneeIds.includes(id)) {
      setAssigneeFilter(filter.assigneeIds.filter(a => a !== id));
    } else {
      setAssigneeFilter([...filter.assigneeIds, id]);
    }
  };
  
  const activeChips: { id: string, name: string, type: 'label' | 'person' }[] = [];
  filter.labelIds.forEach(id => {
    const l = board.labels.find(x => x.id === id);
    if (l) activeChips.push({ id, name: l.name, type: 'label' });
  });
  filter.assigneeIds.forEach(id => {
    if (id === "__unassigned__") {
      activeChips.push({ id, name: "Nicht zugewiesen", type: 'person' });
    } else {
      const m = board.members.find(x => x.id === id);
      if (m) activeChips.push({ id, name: m.name, type: 'person' });
    }
  });

  return (
    <div className="flex flex-wrap items-center gap-2 mb-4 px-4 sm:px-6">
      {/* Label Filter */}
      <div className="relative" ref={labelRef}>
        <button
          ref={labelBtnRef}
          onClick={() => setLabelOpen(!labelOpen)}
          aria-expanded={labelOpen}
          aria-controls="label-filter-menu"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.08] text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] transition-colors"
        >
          <Filter className="w-3.5 h-3.5" />
          Label
        </button>
        {labelOpen && (
          <div 
            id="label-filter-menu"
            className="absolute z-50 top-full left-0 mt-1 w-48 rounded-lg shadow-lg border border-white/[0.08] bg-[#0f111a] py-1 text-sm text-slate-200"
          >
            {board.labels.map(l => (
              <label key={l.id} className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/[0.04] cursor-pointer">
                <input 
                  type="checkbox"
                  checked={filter.labelIds.includes(l.id)}
                  onChange={() => toggleLabel(l.id)}
                  className="rounded border-white/20 bg-white/5"
                />
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: l.color }} />
                <span className="truncate">{l.name}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Person Filter */}
      <div className="relative" ref={personRef}>
        <button
          ref={personBtnRef}
          onClick={() => setPersonOpen(!personOpen)}
          aria-expanded={personOpen}
          aria-controls="person-filter-menu"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-white/[0.08] text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] transition-colors"
        >
          <Filter className="w-3.5 h-3.5" />
          Person
        </button>
        {personOpen && (
          <div 
            id="person-filter-menu"
            className="absolute z-50 top-full left-0 mt-1 w-56 rounded-lg shadow-lg border border-white/[0.08] bg-[#0f111a] py-1 text-sm text-slate-200"
          >
            <label className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/[0.04] cursor-pointer">
              <input 
                type="checkbox"
                checked={filter.assigneeIds.includes("__unassigned__")}
                onChange={() => toggleAssignee("__unassigned__")}
                className="rounded border-white/20 bg-white/5"
              />
              <span className="truncate italic text-slate-400">Nicht zugewiesen</span>
            </label>
            {board.members.map(m => (
              <label key={m.id} className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/[0.04] cursor-pointer">
                <input 
                  type="checkbox"
                  checked={filter.assigneeIds.includes(m.id)}
                  onChange={() => toggleAssignee(m.id)}
                  className="rounded border-white/20 bg-white/5"
                />
                <div className="w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold text-white border border-white/10 shrink-0" style={{ backgroundColor: m.color }}>
                  {m.initials}
                </div>
                <span className="truncate">{m.name}</span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Active Filter Chips */}
      {activeChips.map(chip => (
        <span 
          key={`${chip.type}-${chip.id}`}
          className="inline-flex items-center gap-1 px-2 py-1 rounded bg-cyan-500/10 border border-cyan-500/20 text-[11px] text-cyan-200"
        >
          {chip.name}
          <button 
            onClick={() => chip.type === 'label' ? toggleLabel(chip.id) : toggleAssignee(chip.id)}
            aria-label={`Filter ${chip.name} entfernen`}
            className="hover:bg-cyan-500/20 rounded p-0.5"
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}

      {/* Reset all */}
      {isFilterActive(filter) && (
        <button
          onClick={resetFilters}
          className="text-[11px] font-medium text-slate-400 hover:text-slate-200 ml-2"
        >
          Filter zurücksetzen
        </button>
      )}
    </div>
  );
};
