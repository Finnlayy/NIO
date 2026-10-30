import React, { useState, useEffect } from "react";
import { useKanbanStore } from "./useKanbanStore";
import { TaskStatus, STATUS_LABELS, KanbanTask } from "./types";
import { createDraft, validateDraft, isDirty, TaskDraft } from "./dialogState";
import { columnTasks, localToday, newId } from "./board-logic";
import { useFocusTrap } from "./useFocusTrap";
import { ChecklistEditor } from "./ChecklistEditor";
import { X, CalendarX2 } from "lucide-react";

interface TaskDialogProps {
  taskId: string | null;
  initialStatus?: TaskStatus; // Used when creating a new task
  onClose: () => void;
}

export const TaskDialog: React.FC<TaskDialogProps> = ({ taskId, initialStatus = "backlog", onClose }) => {
  const board = useKanbanStore((s) => s.board);
  const addTask = useKanbanStore((s) => s.addTask);
  const updateTask = useKanbanStore((s) => s.updateTask);
  const moveTask = useKanbanStore((s) => s.moveTask);
  const removeTask = useKanbanStore((s) => s.removeTask);
  
  const originalTask = taskId ? board.tasks.find((t) => t.id === taskId) || null : null;
  
  const [draft, setDraft] = useState<TaskDraft>(() => 
    createDraft(originalTask, originalStatus(), localToday())
  );
  
  function originalStatus(): TaskStatus {
    if (originalTask) return originalTask.status;
    return initialStatus;
  }
  
  const [errors, setErrors] = useState<{ title?: string }>({});
  const [showConfirmDiscard, setShowConfirmDiscard] = useState(false);
  const [pendingItem, setPendingItem] = useState("");

  const dialogRef = useFocusTrap(true, "#title-input");

  // The card vanished while editing (e.g. deleted in another tab): close instead of saving a duplicate.
  useEffect(() => {
    if (taskId && !originalTask) onClose();
  }, [taskId, originalTask, onClose]);

  // The discard prompt covers the form, so keyboard focus moves onto it — and back to the title when it closes.
  const promptWasOpen = React.useRef(false);
  useEffect(() => {
    if (showConfirmDiscard) {
      dialogRef.current?.querySelector<HTMLElement>("[data-discard-cancel]")?.focus();
    } else if (promptWasOpen.current) {
      dialogRef.current?.querySelector<HTMLElement>("#title-input")?.focus();
    }
    promptWasOpen.current = showConfirmDiscard;
  }, [showConfirmDiscard, dialogRef]);
  
  const isEditMode = !!originalTask;
  const isDialogDirty = isDirty(draft, originalTask) || pendingItem.trim() !== "";

  // Global hotkeys (Escape and Save)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Capture phase: the dialog owns Escape and Cmd/Ctrl+Enter while open (native <select> popups handle their own Escape).
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        if (showConfirmDiscard) {
          setShowConfirmDiscard(false);
        } else if (isDialogDirty) {
          setShowConfirmDiscard(true);
        } else {
          onClose();
        }
      }

      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSave();
      }
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, [isDialogDirty, showConfirmDiscard, draft, pendingItem, onClose]);

  const handleSave = () => {
    // A checklist item typed but not yet confirmed with Enter is still part of what the user meant to save.
    const pendingTitle = pendingItem.trim();
    const withPending: TaskDraft = pendingTitle
      ? { ...draft, checklist: [...draft.checklist, { id: newId("chk"), title: pendingTitle, completed: false }] }
      : draft;
    const validation = validateDraft(withPending);
    if (!validation.ok) {
      setErrors(validation.errors);
      
      // Focus the title input if it has an error
      if (validation.errors.title) {
        const titleInput = dialogRef.current?.querySelector('input[name="title"]') as HTMLInputElement;
        titleInput?.focus();
      }
      return;
    }

    if (isEditMode && taskId && originalTask) {
      const { status, ...fields } = validation.value;
      updateTask(taskId, fields);
      // A status change is a move: append to the end of the new column like the move menu does.
      if (status !== originalTask.status) {
        const targetIds = columnTasks(board, status).map((t) => t.id);
        moveTask(taskId, status, targetIds.length, targetIds);
      }
    } else {
      addTask(validation.value);
    }
    onClose();
  };

  const handleDelete = () => {
    if (taskId) {
      removeTask(taskId);
      onClose();
    }
  };

  const toggleLabel = (id: string) => {
    setDraft((prev) => {
      const labelIds = prev.labelIds.includes(id)
        ? prev.labelIds.filter((l) => l !== id)
        : [...prev.labelIds, id];
      return { ...prev, labelIds };
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-6 bg-black/60 backdrop-blur-sm">
      <div 
        ref={dialogRef}
        role="dialog" 
        aria-modal="true" 
        aria-labelledby="dialog-title"
        className="w-full h-full sm:h-auto sm:max-h-[90vh] sm:max-w-2xl bg-[#0c0e15] sm:border border-white/[0.08] sm:rounded-xl shadow-2xl flex flex-col overflow-hidden relative"
      >
        {/* Discard Confirmation Overlay */}
        {showConfirmDiscard && (
          <div className="absolute inset-0 z-10 bg-[#0c0e15]/95 flex flex-col items-center justify-center p-6 text-center">
            <h3 className="text-lg font-medium text-white mb-2">Änderungen verwerfen?</h3>
            <p className="text-sm text-slate-400 mb-6">Sie haben ungespeicherte Änderungen.</p>
            <div className="flex gap-3">
              <button 
                data-discard-cancel
                onClick={() => setShowConfirmDiscard(false)}
                className="px-4 py-2 rounded-lg text-sm font-medium border border-white/[0.08] hover:bg-white/[0.04] text-slate-300"
              >
                Weiter bearbeiten
              </button>
              <button 
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20"
              >
                Verwerfen
              </button>
            </div>
          </div>
        )}

        <header className="shrink-0 flex items-center justify-between p-4 sm:p-5 border-b border-white/[0.04]">
          <h2 id="dialog-title" className="text-lg font-semibold text-white">
            {isEditMode ? "Karte bearbeiten" : "Neue Karte"}
          </h2>
          <button 
            onClick={() => isDialogDirty ? setShowConfirmDiscard(true) : onClose()}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-white/10 transition-colors"
            aria-label="Schließen"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4 sm:p-5 flex flex-col gap-5">
          {/* Title */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="title-input" className="text-xs font-medium text-slate-400">
              Titel
            </label>
            <input
              id="title-input"
              name="title"
              type="text"
              value={draft.title}
              onChange={(e) => {
                setDraft((prev) => ({ ...prev, title: e.target.value }));
                if (errors.title) setErrors((prev) => ({ ...prev, title: undefined }));
              }}
              aria-invalid={!!errors.title}
              aria-describedby={errors.title ? "title-error" : undefined}
              className={`w-full bg-[#090b12] border ${errors.title ? 'border-red-500' : 'border-white/[0.08] focus:border-cyan-500/50'} rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 ${errors.title ? 'focus:ring-red-500' : 'focus:ring-cyan-500/50'}`}
            />
            {errors.title && (
              <span id="title-error" className="text-xs text-red-400 mt-1">{errors.title}</span>
            )}
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="desc-input" className="text-xs font-medium text-slate-400">
              Beschreibung
            </label>
            <textarea
              id="desc-input"
              value={draft.description}
              onChange={(e) => setDraft((prev) => ({ ...prev, description: e.target.value }))}
              rows={4}
              className="w-full bg-[#090b12] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 resize-y"
            />
          </div>

          {/* Labels */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium text-slate-400">Labels</span>
            <div className="flex flex-wrap gap-2">
              {board.labels.map((l) => (
                <button
                  key={l.id}
                  type="button"
                  aria-pressed={draft.labelIds.includes(l.id)}
                  onClick={() => toggleLabel(l.id)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                    draft.labelIds.includes(l.id)
                      ? "bg-white/[0.08]"
                      : "bg-transparent opacity-60 hover:opacity-100"
                  }`}
                  style={{
                    borderColor: draft.labelIds.includes(l.id) ? l.color : `${l.color}40`,
                    color: l.color,
                  }}
                >
                  {l.name}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {/* Assignee */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="assignee-select" className="text-xs font-medium text-slate-400">
                Zuständig
              </label>
              <select
                id="assignee-select"
                value={draft.assigneeId || ""}
                onChange={(e) => setDraft((prev) => ({ ...prev, assigneeId: e.target.value || null }))}
                className="w-full bg-[#090b12] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50"
              >
                <option value="">Nicht zugewiesen</option>
                {board.members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Status */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="status-select" className="text-xs font-medium text-slate-400">
                Status
              </label>
              <select
                id="status-select"
                value={draft.status}
                onChange={(e) => setDraft((prev) => ({ ...prev, status: e.target.value as TaskStatus }))}
                className="w-full bg-[#090b12] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50"
              >
                {(Object.keys(STATUS_LABELS) as TaskStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </option>
                ))}
              </select>
            </div>
            
            {/* Due Date */}
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label htmlFor="dueDate-input" className="text-xs font-medium text-slate-400">
                Fällig
              </label>
              <div className="flex gap-2">
                <input
                  id="dueDate-input"
                  type="date"
                  value={draft.dueDate || ""}
                  onChange={(e) => setDraft((prev) => ({ ...prev, dueDate: e.target.value || null }))}
                  className="flex-1 bg-[#090b12] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 [color-scheme:dark]"
                />
                {draft.dueDate && (
                  <button
                    type="button"
                    onClick={() => setDraft((prev) => ({ ...prev, dueDate: null }))}
                    className="p-2 border border-white/[0.08] rounded-lg text-slate-400 hover:text-red-400 hover:bg-white/[0.04] transition-colors"
                    aria-label="Datum entfernen"
                    title="Datum entfernen"
                  >
                    <CalendarX2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Checklist */}
          <div className="pt-2 border-t border-white/[0.04]">
            <ChecklistEditor 
              items={draft.checklist} 
              onChange={(checklist) => setDraft((prev) => ({ ...prev, checklist }))} 
              pending={pendingItem}
              onPendingChange={setPendingItem}
            />
          </div>
        </div>

        <footer className="shrink-0 flex items-center justify-between p-4 sm:p-5 border-t border-white/[0.04] bg-[#0c0e15]">
          <div>
            {isEditMode && (
              <button
                onClick={handleDelete}
                className="text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 px-3 py-1.5 rounded-lg transition-colors border border-transparent hover:border-red-400/20"
              >
                Karte löschen
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => isDialogDirty ? setShowConfirmDiscard(true) : onClose()}
              className="text-sm font-medium text-slate-300 hover:text-white px-3 py-1.5"
            >
              Abbrechen
            </button>
            <button
              onClick={handleSave}
              className="text-sm font-semibold text-slate-900 bg-cyan-500 hover:bg-cyan-400 px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
            >
              {isEditMode ? "Speichern" : "Karte anlegen"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
};
