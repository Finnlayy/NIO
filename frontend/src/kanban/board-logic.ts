import { BoardState, KanbanTask, TaskStatus, BoardFilter, ChecklistItem } from "./types";

export function localToday(d: Date = new Date()): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function isOverdue(task: KanbanTask, today: string): boolean {
  if (task.dueDate === null) return false;
  if (task.status === "done") return false;
  return task.dueDate < today;
}

export function newId(prefix: string = "t"): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function columnTasks(board: BoardState, status: TaskStatus): KanbanTask[] {
  return board.tasks.filter((t) => t.status === status).sort((a, b) => a.order - b.order);
}

export function isFilterActive(filter: BoardFilter): boolean {
  return filter.labelIds.length > 0 || filter.assigneeIds.length > 0;
}

export function filterTasks(tasks: KanbanTask[], filter: BoardFilter): KanbanTask[] {
  if (!isFilterActive(filter)) return tasks;

  return tasks.filter((t) => {
    let labelMatch = true;
    if (filter.labelIds.length > 0) {
      labelMatch = filter.labelIds.some((id) => t.labelIds.includes(id));
    }

    let assigneeMatch = true;
    if (filter.assigneeIds.length > 0) {
      const matchId = t.assigneeId === null ? "__unassigned__" : t.assigneeId;
      assigneeMatch = filter.assigneeIds.includes(matchId);
    }

    return labelMatch && assigneeMatch;
  });
}

export function normalizeOrders(tasks: KanbanTask[]): KanbanTask[] {
  const byStatus: Record<string, KanbanTask[]> = {};
  for (const t of tasks) {
    if (!byStatus[t.status]) byStatus[t.status] = [];
    byStatus[t.status].push(t);
  }

  const result: KanbanTask[] = [];
  for (const status in byStatus) {
    const sorted = byStatus[status].sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      if (a.createdAt !== b.createdAt) return a.createdAt < b.createdAt ? -1 : 1;
      return a.id < b.id ? -1 : 1;
    });

    for (let i = 0; i < sorted.length; i++) {
      sorted[i] = { ...sorted[i], order: i };
      result.push(sorted[i]);
    }
  }

  return result;
}

/**
 * Move a task to `toStatus` at position `toVisibleIndex`.
 *
 * `visibleIds` are the ids currently shown in the target column (after
 * filtering, display order). The index counts positions among the visible
 * cards *other than the moved one* — i.e. the slot the card lands in once it
 * has been lifted out. Hidden cards keep their relative order: the task is
 * inserted directly before the visible card that ends up after it, or after
 * the last visible card. Returns the same board object for unknown ids and
 * for moves that change nothing.
 */
export function moveTask(
  board: BoardState,
  taskId: string,
  toStatus: TaskStatus,
  toVisibleIndex: number,
  visibleIds: string[],
  now: string
): BoardState {
  const task = board.tasks.find((t) => t.id === taskId);
  if (!task) return board;

  const targetCol = columnTasks(board, toStatus);
  const others = targetCol.filter((t) => t.id !== taskId);
  const visibleOthers = visibleIds.filter((id) => id !== taskId && others.some((t) => t.id === id));
  const slot = Math.min(Math.max(0, Math.trunc(toVisibleIndex) || 0), visibleOthers.length);

  let insertAt: number;
  if (slot < visibleOthers.length) {
    insertAt = others.findIndex((t) => t.id === visibleOthers[slot]);
  } else if (visibleOthers.length > 0) {
    insertAt = others.findIndex((t) => t.id === visibleOthers[visibleOthers.length - 1]) + 1;
  } else {
    insertAt = others.length;
  }

  const nextIds = others.map((t) => t.id);
  nextIds.splice(insertAt, 0, taskId);
  if (task.status === toStatus && nextIds.join("\n") === targetCol.map((t) => t.id).join("\n")) {
    return board;
  }

  const position = new Map(nextIds.map((id, i) => [id, i]));
  const nextTasks = board.tasks.map((t) => {
    if (t.id === taskId) return { ...t, status: toStatus, order: position.get(t.id)!, updatedAt: now };
    if (t.status === toStatus) return { ...t, order: position.get(t.id)! };
    return t;
  });
  return { ...board, tasks: normalizeOrders(nextTasks) };
}

export function addTask(
  board: BoardState,
  draft: Omit<KanbanTask, "id" | "order" | "createdAt" | "updatedAt">,
  now: string
): BoardState {
  const title = draft.title.trim().slice(0, 200);
  if (!title) throw new Error("Task title cannot be empty");

  const colTasks = columnTasks(board, draft.status);
  const maxOrder = colTasks.length > 0 ? colTasks[colTasks.length - 1].order : -1;

  const newTask: KanbanTask = {
    ...draft,
    title,
    id: newId(),
    order: maxOrder + 1,
    createdAt: now,
    updatedAt: now,
  };

  return {
    ...board,
    tasks: [...board.tasks, newTask],
  };
}

export function updateTask(
  board: BoardState,
  id: string,
  patch: Partial<Omit<KanbanTask, "id" | "createdAt" | "updatedAt">>,
  now: string
): BoardState {
  const taskIndex = board.tasks.findIndex((t) => t.id === id);
  if (taskIndex === -1) return board;

  let title = patch.title !== undefined ? patch.title : board.tasks[taskIndex].title;
  if (patch.title !== undefined) {
    title = title.trim().slice(0, 200);
    if (!title) throw new Error("Task title cannot be empty");
  }

  const nextTasks = [...board.tasks];
  nextTasks[taskIndex] = {
    ...nextTasks[taskIndex],
    ...patch,
    title,
    updatedAt: now,
  };

  return {
    ...board,
    tasks: normalizeOrders(nextTasks),
  };
}

/** A removed task plus its position within its column, for undo. */
export interface RemovedTask {
  task: KanbanTask;
  index: number;
}

export function removeTask(board: BoardState, id: string): { board: BoardState; removed: RemovedTask | null } {
  const task = board.tasks.find((t) => t.id === id);
  if (!task) return { board, removed: null };
  const index = columnTasks(board, task.status).findIndex((t) => t.id === id);
  return {
    board: { ...board, tasks: normalizeOrders(board.tasks.filter((t) => t.id !== id)) },
    removed: { task, index },
  };
}

/** Re-insert a removed task at its old column position (clamped if the column shrank meanwhile). */
export function restoreTask(board: BoardState, removed: RemovedTask): BoardState {
  if (board.tasks.some((t) => t.id === removed.task.id)) return board;
  const ids = columnTasks(board, removed.task.status).map((t) => t.id);
  ids.splice(Math.min(Math.max(0, removed.index), ids.length), 0, removed.task.id);
  const position = new Map(ids.map((id, i) => [id, i]));
  const nextTasks = [...board.tasks, removed.task].map((t) =>
    t.status === removed.task.status ? { ...t, order: position.get(t.id)! } : t
  );
  return { ...board, tasks: normalizeOrders(nextTasks) };
}

export function addChecklistItem(task: KanbanTask, title: string): KanbanTask {
  const trimmed = title.trim();
  if (!trimmed) return task;
  const newItem: ChecklistItem = { id: newId("chk"), title: trimmed, completed: false };
  return { ...task, checklist: [...task.checklist, newItem] };
}

export function toggleChecklistItem(task: KanbanTask, itemId: string): KanbanTask {
  const nextChecklist = task.checklist.map((item) =>
    item.id === itemId ? { ...item, completed: !item.completed } : item
  );
  return { ...task, checklist: nextChecklist };
}

export function renameChecklistItem(task: KanbanTask, itemId: string, title: string): KanbanTask {
  const trimmed = title.trim();
  if (!trimmed) {
    return removeChecklistItem(task, itemId);
  }
  const nextChecklist = task.checklist.map((item) =>
    item.id === itemId ? { ...item, title: trimmed } : item
  );
  return { ...task, checklist: nextChecklist };
}

export function removeChecklistItem(task: KanbanTask, itemId: string): KanbanTask {
  return { ...task, checklist: task.checklist.filter((i) => i.id !== itemId) };
}

export function checklistProgress(task: KanbanTask): { done: number; total: number } {
  const total = task.checklist.length;
  const done = task.checklist.filter((i) => i.completed).length;
  return { done, total };
}

export function columnCounts(
  board: BoardState,
  filter: BoardFilter
): Record<TaskStatus, { visible: number; total: number }> {
  const counts: Record<TaskStatus, { visible: number; total: number }> = {
    backlog: { visible: 0, total: 0 },
    in_progress: { visible: 0, total: 0 },
    review: { visible: 0, total: 0 },
    done: { visible: 0, total: 0 },
  };

  const filtered = filterTasks(board.tasks, filter);
  const filteredIds = new Set(filtered.map((t) => t.id));

  for (const t of board.tasks) {
    if (!counts[t.status]) continue; // Guard against unknown status if it somehow bypassed types
    counts[t.status].total++;
    if (filteredIds.has(t.id)) {
      counts[t.status].visible++;
    }
  }

  return counts;
}
