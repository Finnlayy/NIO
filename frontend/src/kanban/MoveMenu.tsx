import React, { useEffect, useRef } from "react";
import { TaskStatus, STATUS_LABELS, STATUSES } from "./types";
import { useKanbanStore } from "./useKanbanStore";
import { columnTasks } from "./board-logic";

interface MoveMenuProps {
  taskId: string;
  currentStatus: TaskStatus;
  currentIndex: number;
  visibleIds: string[]; // Visible IDs in the current column (for reordering within same column)
  onClose: () => void;
  triggerRef: React.RefObject<HTMLButtonElement>;
}

export const MoveMenu: React.FC<MoveMenuProps> = ({ taskId, currentStatus, currentIndex, visibleIds, onClose, triggerRef }) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const moveTask = useKanbanStore((s) => s.moveTask);
  const board = useKanbanStore((s) => s.board);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        triggerRef.current?.focus();
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const items = Array.from(menuRef.current?.querySelectorAll('[role="menuitem"]:not([disabled])') || []) as HTMLElement[];
        const currentIndex = items.indexOf(document.activeElement as HTMLElement);
        if (items.length > 0) {
          let nextIndex = currentIndex;
          if (e.key === "ArrowDown") {
            nextIndex = currentIndex < items.length - 1 ? currentIndex + 1 : 0;
          } else {
            nextIndex = currentIndex > 0 ? currentIndex - 1 : items.length - 1;
          }
          items[nextIndex].focus();
        }
      }
    }
    
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node) && !triggerRef.current?.contains(e.target as Node)) {
        onClose();
      }
    }
    
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onClickOutside);
    
    // Focus first item initially
    const firstItem = menuRef.current?.querySelector('[role="menuitem"]:not([disabled])') as HTMLElement;
    firstItem?.focus();
    
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onClickOutside);
    };
  }, [onClose, triggerRef]);

  const otherStatuses = STATUSES.filter(s => s !== currentStatus);

  const handleMoveToColumn = (toStatus: TaskStatus) => {
    // Append to the end of the target column (all cards count, filters don't matter here).
    const targetIds = columnTasks(board, toStatus).map((t) => t.id);
    moveTask(taskId, toStatus, targetIds.length, targetIds);
    onClose();
    triggerRef.current?.focus();
  };

  const handleMoveWithinColumn = (direction: 'up' | 'down') => {
    if (direction === 'up' && currentIndex > 0) {
      moveTask(taskId, currentStatus, currentIndex - 1, visibleIds);
    } else if (direction === 'down' && currentIndex < visibleIds.length - 1) {
      moveTask(taskId, currentStatus, currentIndex + 1, visibleIds);
    }
    onClose();
    triggerRef.current?.focus();
  };

  return (
    <div
      ref={menuRef}
      role="menu"
      aria-label="Verschieben nach"
      className="absolute z-50 top-full right-0 mt-1 w-48 rounded-lg shadow-lg border border-white/[0.08] bg-[#0f111a] py-1 text-sm text-slate-200"
    >
      <div className="px-2 py-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
        Verschieben
      </div>
      {otherStatuses.map(status => (
        <button
          key={status}
          role="menuitem"
          tabIndex={-1}
          className="w-full text-left px-3 py-1.5 hover:bg-white/[0.04] focus:bg-white/[0.04] focus:outline-none"
          onClick={() => handleMoveToColumn(status)}
        >
          &rarr; {STATUS_LABELS[status]}
        </button>
      ))}
      <div className="h-px bg-white/[0.08] my-1" />
      <button
        role="menuitem"
        tabIndex={-1}
        className="w-full text-left px-3 py-1.5 hover:bg-white/[0.04] focus:bg-white/[0.04] focus:outline-none disabled:opacity-50"
        onClick={() => handleMoveWithinColumn('up')}
        disabled={currentIndex === 0}
      >
        Nach oben
      </button>
      <button
        role="menuitem"
        tabIndex={-1}
        className="w-full text-left px-3 py-1.5 hover:bg-white/[0.04] focus:bg-white/[0.04] focus:outline-none disabled:opacity-50"
        onClick={() => handleMoveWithinColumn('down')}
        disabled={currentIndex === visibleIds.length - 1}
      >
        Nach unten
      </button>
    </div>
  );
};
