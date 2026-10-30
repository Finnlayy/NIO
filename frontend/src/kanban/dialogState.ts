import { KanbanTask, TaskStatus, ChecklistItem } from "./types";
import { newId } from "./board-logic";

export interface TaskDraft {
  title: string;
  description: string;
  labelIds: string[];
  assigneeId: string | null;
  dueDate: string | null;
  status: TaskStatus;
  checklist: ChecklistItem[];
}

export function createDraft(
  task: KanbanTask | null,
  status: TaskStatus,
  today: string
): TaskDraft {
  if (task) {
    // Return a deep copy of the relevant fields for editing
    return {
      title: task.title,
      description: task.description,
      labelIds: [...task.labelIds],
      assigneeId: task.assigneeId,
      dueDate: task.dueDate,
      status: task.status,
      checklist: task.checklist.map((item) => ({ ...item })),
    };
  }
  // New task draft
  return {
    title: "",
    description: "",
    labelIds: [],
    assigneeId: null,
    dueDate: null,
    status,
    checklist: [],
  };
}

export function isDirty(draft: TaskDraft, original: KanbanTask | null): boolean {
  if (!original) {
    // For a new task, it's dirty if any user input is present
    return (
      draft.title.trim() !== "" ||
      draft.description.trim() !== "" ||
      draft.labelIds.length > 0 ||
      draft.assigneeId !== null ||
      draft.dueDate !== null ||
      draft.checklist.length > 0
    );
  }

  // Deep comparison for edits
  if (draft.title !== original.title) return true;
  if (draft.description !== original.description) return true;
  if (draft.status !== original.status) return true;
  if (draft.assigneeId !== original.assigneeId) return true;
  if (draft.dueDate !== original.dueDate) return true;
  
  if (draft.labelIds.length !== original.labelIds.length) return true;
  const originalLabels = new Set(original.labelIds);
  if (!draft.labelIds.every(id => originalLabels.has(id))) return true;

  if (draft.checklist.length !== original.checklist.length) return true;
  for (let i = 0; i < draft.checklist.length; i++) {
    const a = draft.checklist[i];
    const b = original.checklist[i];
    if (a.title !== b.title || a.completed !== b.completed) return true;
  }

  return false;
}

export interface ValidationSuccess {
  ok: true;
  value: TaskDraft;
}

export interface ValidationFailure {
  ok: false;
  errors: { title?: string };
}

export function validateDraft(draft: TaskDraft): ValidationSuccess | ValidationFailure {
  let title = draft.title.trim();
  const errors: { title?: string } = {};

  if (!title) {
    errors.title = "Titel darf nicht leer sein";
  }
  
  title = title.slice(0, 200);

  let dueDate = draft.dueDate;
  if (dueDate !== null && !/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) {
    // If somehow an invalid date format arrives, clear it
    dueDate = null;
  }

  // Filter out checklist items with empty titles
  const validChecklist = draft.checklist
    .filter(item => item.title.trim() !== "")
    .map(item => ({ ...item, title: item.title.trim() }));

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    value: {
      ...draft,
      title,
      dueDate,
      checklist: validChecklist,
    },
  };
}
