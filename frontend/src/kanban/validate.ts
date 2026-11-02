import { BOARD_SCHEMA_VERSION, BoardState, KanbanTask, STATUSES } from "./types";
import { normalizeOrders } from "./board-logic";

const isObj = (v: unknown): v is Record<string, any> => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, fallback: string): string => (typeof v === "string" ? v : fallback);

export function parseStoredBoard(
  raw: string | null
): { board: BoardState | null; recovered: boolean; reason?: string } {
  if (!raw || !raw.trim()) {
    return { board: null, recovered: false };
  }

  let parsed: any;
  try {
    parsed = JSON.parse(raw);
  } catch (err: any) {
    return { board: null, recovered: true, reason: "Invalid JSON" };
  }

  if (!isObj(parsed)) {
    return { board: null, recovered: true, reason: "Not an object" };
  }

  if (parsed.version !== BOARD_SCHEMA_VERSION) {
    return { board: null, recovered: true, reason: `Wrong version: expected ${BOARD_SCHEMA_VERSION}, got ${parsed.version}` };
  }

  if (!Array.isArray(parsed.tasks) || !Array.isArray(parsed.labels) || !Array.isArray(parsed.members)) {
    return { board: null, recovered: true, reason: "Missing or invalid core arrays (tasks, labels, members)" };
  }

  let recovered = false;

  // Validate labels
  const validLabelIds = new Set<string>();
  const labels = [];
  for (const l of parsed.labels) {
    if (!isObj(l) || typeof l.id !== "string" || typeof l.name !== "string" || validLabelIds.has(l.id)) {
      recovered = true;
      continue;
    }
    if (typeof l.color !== "string") recovered = true;
    validLabelIds.add(l.id);
    labels.push({ id: l.id, name: l.name, color: str(l.color, "#64748b") });
  }

  // Validate members
  const validMemberIds = new Set<string>();
  const members = [];
  for (const m of parsed.members) {
    if (!isObj(m) || typeof m.id !== "string" || typeof m.name !== "string" || validMemberIds.has(m.id)) {
      recovered = true;
      continue;
    }
    if (typeof m.initials !== "string" || typeof m.color !== "string") recovered = true;
    validMemberIds.add(m.id);
    const initials = str(m.initials, m.name.split(/\s+/).map((w: string) => w[0] ?? "").join("").slice(0, 2).toUpperCase());
    members.push({ id: m.id, name: m.name, initials, color: str(m.color, "#64748b") });
  }

  // Validate tasks
  const seenTaskIds = new Set<string>();
  const tasks: KanbanTask[] = [];

  for (const t of parsed.tasks) {
    if (!isObj(t) || typeof t.id !== "string" || typeof t.title !== "string" || !t.title.trim()) {
      recovered = true;
      continue; // drop task
    }
    if (seenTaskIds.has(t.id)) {
      recovered = true;
      continue; // drop duplicate
    }
    seenTaskIds.add(t.id);

    // Repair status
    let status = t.status;
    if (!STATUSES.includes(status)) {
      status = "backlog";
      recovered = true;
    }

    // Repair labels
    let labelIds = t.labelIds;
    if (!Array.isArray(labelIds)) {
      labelIds = [];
      recovered = true;
    } else {
      const filteredLabels = labelIds.filter((id: any) => validLabelIds.has(id));
      if (filteredLabels.length !== labelIds.length) {
        recovered = true;
      }
      labelIds = filteredLabels;
    }

    // Repair assignee
    let assigneeId = t.assigneeId;
    if (assigneeId !== null && !(typeof assigneeId === "string" && validMemberIds.has(assigneeId))) {
      assigneeId = null;
      recovered = true;
    }

    // Repair dueDate
    let dueDate = t.dueDate;
    if (dueDate !== null) {
      if (typeof dueDate !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) {
        dueDate = null;
        recovered = true;
      }
    }

    // Repair checklist
    let checklist = t.checklist;
    if (!Array.isArray(checklist)) {
      checklist = [];
      recovered = true;
    } else {
      const validChecklist = checklist
        .filter((c: unknown) => isObj(c) && typeof c.id === "string" && typeof c.title === "string" && c.title.trim() !== "")
        .map((c: Record<string, any>) => ({ id: c.id, title: c.title, completed: c.completed === true }));
      if (validChecklist.length !== checklist.length || checklist.some((c: any) => isObj(c) && typeof c.completed !== "boolean")) {
        recovered = true;
      }
      checklist = validChecklist;
    }

    tasks.push({
      id: t.id,
      title: t.title,
      description: typeof t.description === "string" ? t.description : "",
      labelIds,
      assigneeId,
      dueDate,
      checklist,
      status,
      order: Number.isFinite(t.order) ? t.order : 0,
      createdAt: typeof t.createdAt === "string" ? t.createdAt : new Date(0).toISOString(),
      updatedAt: typeof t.updatedAt === "string" ? t.updatedAt : new Date(0).toISOString(),
    });
  }

  const normalizedTasks = normalizeOrders(tasks);

  // Check if normalization changed any orders
  const normalizedTaskMap = new Map(normalizedTasks.map(t => [t.id, t]));
  for (const t of tasks) {
    const nt = normalizedTaskMap.get(t.id);
    if (!nt || t.order !== nt.order || t.status !== nt.status) {
      recovered = true;
      break;
    }
  }

  const board: BoardState = {
    version: BOARD_SCHEMA_VERSION,
    labels,
    members,
    tasks: normalizedTasks,
  };

  return { board, recovered };
}
