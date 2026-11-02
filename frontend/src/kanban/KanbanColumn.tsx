import React, { useRef, useState } from "react";
import { TaskStatus, KanbanTask, STATUS_LABELS } from "./types";
import { useKanbanStore } from "./useKanbanStore";
import { filterTasks, columnCounts, columnTasks, isFilterActive } from "./board-logic";
import { TaskCard } from "./TaskCard";
import { Plus } from "lucide-react";
import { KanbanDragState } from "./dragState";

interface KanbanColumnProps {
  status: TaskStatus;
  dragState: KanbanDragState;
  onDragBegin: (taskId: string, status: TaskStatus) => void;
  onDragOverCol: (status: TaskStatus, index: number) => void;
  onDrop: () => void;
  onOpenEditor: (taskId: string | null, status?: TaskStatus) => void;
}

const STATUS_COLORS: Record<TaskStatus, string> = {
  backlog: "bg-amber-400",
  in_progress: "bg-cyan-400",
  review: "bg-violet-400",
  done: "bg-emerald-400",
};

export const KanbanColumn: React.FC<KanbanColumnProps> = ({
  status,
  dragState,
  onDragBegin,
  onDragOverCol,
  onDrop,
  onOpenEditor
}) => {
  const board = useKanbanStore(s => s.board);
  const filter = useKanbanStore(s => s.filter);
  const counts = columnCounts(board, filter)[status];
  const isFiltered = isFilterActive(filter);

  // Get tasks for this column and sort them by order
  const visibleTasks = filterTasks(columnTasks(board, status), filter);
  const visibleIds = visibleTasks.map(t => t.id);

  const colRef = useRef<HTMLDivElement>(null);

  const handleDragStart = (e: React.DragEvent, taskId: string) => {
    // Required for Firefox
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", taskId);

    // We add a small timeout to let the browser snapshot the drag image before we update state
    setTimeout(() => {
      onDragBegin(taskId, status);
    }, 0);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!dragState.taskId) return;

    // Find closest task or drop at the end
    const taskNodes = Array.from(colRef.current?.querySelectorAll('[data-task-id]') || []);
    let overIndex = visibleTasks.length; // Default to end

    for (let i = 0; i < taskNodes.length; i++) {
      const rect = taskNodes[i].getBoundingClientRect();
      const mid = rect.top + rect.height / 2;
      if (e.clientY < mid) {
        overIndex = i;
        break;
      }
    }

    onDragOverCol(status, overIndex);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    onDrop();
  };

  const isDragOverColumn = dragState.overStatus === status;

  return (
    <div
      className="flex flex-col w-[280px] shrink-0 max-h-full min-h-0 snap-start bg-[#0c0e15] border border-white/[0.04] rounded-xl overflow-hidden"
      ref={colRef}
      data-status={status}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Column Header */}
      <div className="flex items-center justify-between p-3 border-b border-white/[0.04]">
        <div className="flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${STATUS_COLORS[status]}`} />
          <h3 className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
            {STATUS_LABELS[status]}
          </h3>
          <span
            className="text-[10px] text-slate-500 font-medium ml-1 bg-white/[0.03] px-1.5 py-0.5 rounded"
            aria-label={isFiltered ? `${counts.visible} von ${counts.total} Karten sichtbar` : undefined}
          >
            {isFiltered ? `${counts.visible} / ${counts.total}` : counts.total}
          </span>
        </div>
        <button
          className="p-1 rounded text-slate-500 hover:text-slate-200 hover:bg-white/10 transition-colors"
          aria-label={`Karte in ${STATUS_LABELS[status]} hinzufügen`}
          onClick={() => onOpenEditor(null, status)}
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Task List Container */}
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2 min-h-[150px] relative">
        {visibleTasks.map((task, idx) => (
          <React.Fragment key={task.id}>
            {/* Drop Indicator (above) */}
            {isDragOverColumn && dragState.overIndex === idx && (
              <div className="h-1 bg-cyan-500/50 rounded-full mx-1" />
            )}

            <TaskCard
              task={task}
              labels={board.labels}
              assignee={board.members.find(m => m.id === task.assigneeId) || null}
              visibleIds={visibleIds}
              currentIndex={idx}
              onOpenEditor={onOpenEditor}
              onDragStart={(e) => handleDragStart(e, task.id)}
            />
          </React.Fragment>
        ))}

        {/* Drop Indicator (at the end) */}
        {isDragOverColumn && dragState.overIndex === visibleTasks.length && (
          <div className="h-1 bg-cyan-500/50 rounded-full mx-1 mt-auto" />
        )}

        {/* Empty State */}
        {visibleTasks.length === 0 && !isDragOverColumn && (
          <div className="flex-1 flex flex-col items-center justify-center p-4">
            <p className="text-xs text-slate-500 mb-3 text-center">
              {isFiltered ? "Keine Karten für diesen Filter" : "Keine Karten"}
            </p>
            <button
              onClick={() => onOpenEditor(null, status)}
              className="text-[11px] font-medium text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.05] transition-colors"
            >
              Hinzufügen
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
