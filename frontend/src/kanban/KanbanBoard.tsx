"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useKanbanStore } from "./useKanbanStore";
import { STATUSES, TaskStatus, STATUS_LABELS } from "./types";
import { BoardToolbar } from "./BoardToolbar";
import { KanbanColumn } from "./KanbanColumn";
import { createDragState } from "./dragState";
import { Plus } from "lucide-react";

export const KanbanBoard: React.FC = () => {
  const hydrate = useKanbanStore(s => s.hydrate);
  const hydrated = useKanbanStore(s => s.hydrated);
  const saveFailed = useKanbanStore(s => s.saveFailed);
  const moveTask = useKanbanStore(s => s.moveTask);
  const board = useKanbanStore(s => s.board);
  const filter = useKanbanStore(s => s.filter);

  const [ds] = useState(() => createDragState());
  // Need to force re-render when drag state changes
  const [, forceRender] = useState({});

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const handleOpenEditor = useCallback((taskId: string) => {
    // Placeholder for UI-03 (Card editor dialog)
    console.log("onOpenEditor called with:", taskId);
  }, []);

  const handleDragBegin = useCallback((taskId: string, status: TaskStatus) => {
    ds.begin(taskId, status);
    forceRender({});
  }, [ds]);

  const handleDragOverCol = useCallback((status: TaskStatus, index: number) => {
    const nextDs = ds.over(status, index);
    if (nextDs) forceRender({});
  }, [ds]);

  const handleDrop = useCallback(() => {
    const move = ds.drop();
    if (move) {
      // Find visible IDs in the target column after filtering
      const targetVisibleTasks = board.tasks
        .filter(t => t.status === move.toStatus)
        .filter(t => {
          if (filter.labelIds.length > 0 && !filter.labelIds.some(id => t.labelIds.includes(id))) return false;
          if (filter.assigneeIds.length > 0) {
            const matchId = t.assigneeId === null ? "__unassigned__" : t.assigneeId;
            if (!filter.assigneeIds.includes(matchId)) return false;
          }
          return true;
        })
        .sort((a, b) => a.order - b.order)
        .map(t => t.id);

      moveTask(move.taskId, move.toStatus, move.toIndex, targetVisibleTasks);
    }
    forceRender({});
  }, [ds, moveTask, board.tasks, filter]);

  // Handle drag cancel on escape and missing drop
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && ds.active) {
        ds.cancel();
        forceRender({});
      }
    };

    const handleDragEnd = () => {
      if (ds.active) {
        ds.cancel();
        forceRender({});
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("dragend", handleDragEnd);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("dragend", handleDragEnd);
    };
  }, [ds]);

  const currentState = ds.current;

  return (
    <div className="flex flex-col h-screen min-w-0 bg-[#090b12] text-slate-200 font-sans">
      {/* Header */}
      <header className="shrink-0 flex items-center justify-between px-4 sm:px-6 py-4 border-b border-white/[0.06] bg-[#0c0e15]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 via-blue-500 to-violet-600 grid place-items-center font-bold text-white shadow-lg text-xs">
            NIO
          </div>
          <div>
            <h1 className="text-[15px] font-semibold tracking-tight text-white leading-tight">
              Kanban
            </h1>
            <p className="text-[11px] text-slate-400 uppercase tracking-widest mt-0.5">
              Lokal in diesem Browser gespeichert
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {saveFailed && (
            <span role="status" className="text-[11px] font-medium text-amber-400/90 bg-amber-400/10 border border-amber-400/20 px-2 py-1 rounded">
              Nicht lokal gespeichert – Speicher nicht verfügbar
            </span>
          )}
          <button
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-900 transition-colors"
            onClick={() => handleOpenEditor("new")}
          >
            <Plus className="w-4 h-4" />
            Neue Karte
          </button>
        </div>
      </header>

      {/* Toolbar */}
      <div className="shrink-0 pt-4 bg-[#0c0e15]/50 border-b border-white/[0.04]">
        <BoardToolbar />
      </div>

      {/* Board Area */}
      <main className="flex-1 overflow-x-auto overflow-y-hidden snap-x">
        <div className="h-full p-4 sm:p-6 flex items-start gap-4 sm:gap-6 min-w-max">
          {!hydrated ? (
            /* Skeleton Columns (Must match real columns structure) */
            STATUSES.map(status => (
              <div key={status} className="flex flex-col w-[280px] shrink-0 h-full max-h-full bg-[#0c0e15] border border-white/[0.04] rounded-xl overflow-hidden opacity-50">
                <div className="flex items-center p-3 border-b border-white/[0.04]">
                  <h3 className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider ml-3.5">
                    {STATUS_LABELS[status]}
                  </h3>
                </div>
                <div className="p-4" />
              </div>
            ))
          ) : (
            /* Real Columns */
            STATUSES.map(status => (
              <KanbanColumn
                key={status}
                status={status}
                dragState={currentState}
                onDragBegin={handleDragBegin}
                onDragOverCol={handleDragOverCol}
                onDrop={handleDrop}
                onOpenEditor={handleOpenEditor}
              />
            ))
          )}
        </div>
      </main>
    </div>
  );
};
