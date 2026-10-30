import React, { useState, useRef } from "react";
import { KanbanTask, BoardLabel, BoardMember, STATUS_LABELS, TaskStatus } from "./types";
import { checklistProgress, isOverdue, localToday } from "./board-logic";
import { MoveMenu } from "./MoveMenu";
import { MoreHorizontal } from "lucide-react";

interface TaskCardProps {
  task: KanbanTask;
  labels: BoardLabel[];
  assignee: BoardMember | null;
  visibleIds: string[];
  currentIndex: number;
  onOpenEditor: (taskId: string | null, status?: TaskStatus) => void;
  // Drag and drop handlers passed from column
  onDragStart?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDragEnter?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
}

function formatDate(dateStr: string) {
  // Extract month and day without instantiating a full Date to avoid timezone issues
  // dateStr format: "YYYY-MM-DD"
  const [, monthStr, dayStr] = dateStr.split('-');
  if (!monthStr || !dayStr) return dateStr;
  
  const monthInt = parseInt(monthStr, 10);
  const dayInt = parseInt(dayStr, 10);
  
  const months = [
    "Jan.", "Feb.", "März", "Apr.", "Mai", "Juni",
    "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."
  ];
  return `${dayInt}. ${months[monthInt - 1]}`;
}

export const TaskCard: React.FC<TaskCardProps> = React.memo(({ 
  task, 
  labels, 
  assignee, 
  visibleIds,
  currentIndex,
  onOpenEditor,
  onDragStart,
  onDragOver,
  onDragEnter,
  onDrop
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const moveBtnRef = useRef<HTMLButtonElement>(null);
  
  const today = localToday();
  const overdue = isOverdue(task, today);
  const chkProgress = checklistProgress(task);
  
  // Resolve labels
  const taskLabels = task.labelIds
    .map(id => labels.find(l => l.id === id))
    .filter(Boolean) as BoardLabel[];
    
  const visibleLabels = taskLabels.slice(0, 3);
  const hiddenLabelsCount = taskLabels.length - 3;

  return (
    <article 
      className="group relative flex flex-col gap-2 p-3 bg-white/[0.03] hover:bg-white/[0.05] border border-white/[0.06] rounded-lg transition-colors cursor-grab active:cursor-grabbing"
      tabIndex={0}
      role="button"
      aria-label={`${task.title}, Status: ${STATUS_LABELS[task.status]}`}
      onClick={() => onOpenEditor(task.id)}
      onKeyDown={(e) => {
        // Only keys aimed at the card itself; Enter/Space in the nested move menu must reach its buttons.
        if (e.target !== e.currentTarget) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpenEditor(task.id);
        }
      }}
      draggable={!!onDragStart}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnter={onDragEnter}
      onDrop={onDrop}
      data-task-id={task.id}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-slate-200 line-clamp-2 break-words leading-tight">
          {task.title}
        </h4>
        <div className="relative" onClick={e => e.stopPropagation()}>
          <button
            ref={moveBtnRef}
            className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/10 [@media(hover:hover)]:opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 transition-opacity motion-reduce:transition-none"
            aria-label="Verschieben nach …"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen(!menuOpen);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                setMenuOpen(true);
              }
            }}
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>
          {menuOpen && (
            <MoveMenu 
              taskId={task.id}
              currentStatus={task.status}
              currentIndex={currentIndex}
              visibleIds={visibleIds}
              onClose={() => setMenuOpen(false)}
              triggerRef={moveBtnRef as React.RefObject<HTMLButtonElement>}
            />
          )}
        </div>
      </div>
      
      {task.description && (
        <p className="text-xs text-slate-400 line-clamp-2 leading-snug">
          {task.description}
        </p>
      )}

      {(visibleLabels.length > 0 || task.dueDate || chkProgress.total > 0 || assignee) && (
        <div className="flex flex-wrap items-center gap-2 mt-1">
          {visibleLabels.map(l => (
            <span key={l.id} className="px-1.5 py-0.5 rounded text-[10px] font-medium border" style={{ backgroundColor: `${l.color}15`, borderColor: `${l.color}30`, color: l.color }}>
              {l.name}
            </span>
          ))}
          {hiddenLabelsCount > 0 && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium border border-white/10 bg-white/[0.04] text-slate-400">
              +{hiddenLabelsCount}
            </span>
          )}

          <div className="flex-1" />

          {chkProgress.total > 0 && (
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400" title="Checkliste">
              <span>{chkProgress.done}/{chkProgress.total}</span>
              <div className="w-12 h-1 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-cyan-400/80 transition-transform origin-left" 
                  style={{ transform: `scaleX(${chkProgress.done / chkProgress.total})` }} 
                />
              </div>
            </div>
          )}

          {task.dueDate && (
            <span className={`text-[10px] font-medium flex items-center gap-1 ${overdue ? "text-red-400/90" : "text-slate-400"}`}>
              {overdue && <span className="sr-only">überfällig</span>}
              {formatDate(task.dueDate)}
            </span>
          )}

          {assignee && (
            <div 
              className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white border border-white/10 shrink-0 ml-1"
              style={{ backgroundColor: assignee.color }}
              title={`Zugewiesen an ${assignee.name}`}
            >
              {assignee.initials}
            </div>
          )}
        </div>
      )}
    </article>
  );
});
