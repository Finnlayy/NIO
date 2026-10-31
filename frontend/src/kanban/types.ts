export const STATUSES = ["backlog", "in_progress", "review", "done"] as const;
export type TaskStatus = typeof STATUSES[number];

export const STATUS_LABELS: Record<TaskStatus, string> = {
  backlog: "Backlog",
  in_progress: "In Arbeit",
  review: "Review",
  done: "Erledigt",
};

export const BOARD_SCHEMA_VERSION = 1;

export interface ChecklistItem {
  id: string;
  title: string;
  completed: boolean;
}

export interface KanbanTask {
  id: string;
  title: string;
  description: string;
  labelIds: string[];
  assigneeId: string | null;
  dueDate: string | null; // "YYYY-MM-DD"
  checklist: ChecklistItem[];
  status: TaskStatus;
  order: number;
  createdAt: string; // ISO
  updatedAt: string; // ISO
}

export interface BoardLabel {
  id: string;
  name: string;
  color: string;
}

export interface BoardMember {
  id: string;
  name: string;
  initials: string;
  color: string;
}

export interface BoardState {
  version: typeof BOARD_SCHEMA_VERSION;
  tasks: KanbanTask[];
  labels: BoardLabel[];
  members: BoardMember[];
}

export interface BoardFilter {
  labelIds: string[];
  assigneeIds: string[];
}
