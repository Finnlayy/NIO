import { BOARD_SCHEMA_VERSION, BoardState, KanbanTask, BoardLabel, BoardMember } from "./types";

/**
 * Creates a deterministic seed board with demo data for a small product team working on NIO.
 * This is demo data, not real telemetry or production state.
 * @param today - A string in "YYYY-MM-DD" format.
 */
/** Calendar arithmetic on a "YYYY-MM-DD" string, entirely in UTC so no local offset can shift the day. */
function addDays(ymd: string, days: number): string {
  const [y, m, d] = ymd.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

export function createSeedBoard(today: string): BoardState {
  const ts = today + "T09:00:00.000Z";
  const pastDate = addDays(today, -5);
  const soonDate = addDays(today, 3);

  const labels: BoardLabel[] = [
    { id: "lbl-1", name: "Frontend", color: "#3b82f6" }, // blue
    { id: "lbl-2", name: "Backend", color: "#10b981" },  // green
    { id: "lbl-3", name: "Bug", color: "#ef4444" },      // red
    { id: "lbl-4", name: "Design", color: "#f59e0b" },   // amber
    { id: "lbl-5", name: "Infra", color: "#8b5cf6" },    // violet
    { id: "lbl-6", name: "Doku", color: "#6b7280" },     // gray
  ];

  const members: BoardMember[] = [
    { id: "mem-1", name: "Lena Hoffmann", initials: "LH", color: "#ec4899" }, // pink
    { id: "mem-2", name: "Jonas Weber", initials: "JW", color: "#06b6d4" }, // cyan
    { id: "mem-3", name: "Mira Schulz", initials: "MS", color: "#eab308" }, // yellow
    { id: "mem-4", name: "Tobias Krüger", initials: "TK", color: "#84cc16" }, // lime
  ];

  const tasks: KanbanTask[] = [
    {
      id: "seed-1",
      title: "Ops-Grid: Widget-Snap verbessern",
      description: "Widgets sollen beim Drag & Drop besser einrasten.",
      labelIds: ["lbl-1", "lbl-4"],
      assigneeId: "mem-1",
      dueDate: null,
      checklist: [
        { id: "chk-1", title: "Snapping Logic implementieren", completed: true },
        { id: "chk-2", title: "Tests schreiben", completed: false },
      ],
      status: "in_progress",
      order: 0,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-2",
      title: "Telegram-Alerts für Breaker",
      description: "Wenn ein Breaker auslöst, soll eine Telegram-Nachricht an den Channel gesendet werden.",
      labelIds: ["lbl-2", "lbl-5"],
      assigneeId: "mem-2",
      dueDate: pastDate, // Overdue
      checklist: [],
      status: "backlog",
      order: 0,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-3",
      title: "Onboarding-Doku Kanban",
      description: "Dokumentation für das neue Kanban-Board schreiben.",
      labelIds: ["lbl-6"],
      assigneeId: null, // Unassigned
      dueDate: today,
      checklist: [],
      status: "review",
      order: 0,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-4",
      title: "Apollo GraphQL Caching prüfen",
      description: "Caching im Apollo Client optimieren, um überflüssige Requests zu vermeiden.",
      labelIds: ["lbl-1", "lbl-2"],
      assigneeId: "mem-3",
      dueDate: null,
      checklist: [
        { id: "chk-3", title: "Cache Policies analysieren", completed: true },
        { id: "chk-4", title: "Umsetzung Frontend", completed: true },
        { id: "chk-5", title: "PR Review", completed: false },
      ],
      status: "in_progress",
      order: 1,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-5",
      title: "Bug: Login-Button flackert",
      description: "Der Login-Button flackert kurz beim Laden der Seite.",
      labelIds: ["lbl-1", "lbl-3"],
      assigneeId: "mem-4",
      dueDate: today,
      checklist: [],
      status: "done",
      order: 0,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-6",
      title: "CI/CD Pipeline beschleunigen",
      description: "Die Build-Zeit in der CI/CD Pipeline reduzieren.",
      labelIds: ["lbl-5"],
      assigneeId: "mem-2",
      dueDate: soonDate,
      checklist: [],
      status: "backlog",
      order: 1,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-7",
      title: "Neues Farbschema entwerfen",
      description: "Designvorschläge für das Q3 Update sammeln.",
      labelIds: ["lbl-4"],
      assigneeId: "mem-4",
      dueDate: null,
      checklist: [],
      status: "backlog",
      order: 2,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-8",
      title: "API-Dokumentation aktualisieren",
      description: "Die neuen Endpunkte im Swagger UI dokumentieren.",
      labelIds: ["lbl-2", "lbl-6"],
      assigneeId: "mem-1",
      dueDate: null,
      checklist: [],
      status: "backlog",
      order: 3,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-9",
      title: "Datenbank-Indizes prüfen",
      description: "Slow Queries im Production-Log analysieren und Indizes anlegen.",
      labelIds: ["lbl-2", "lbl-5"],
      assigneeId: "mem-3",
      dueDate: null,
      checklist: [],
      status: "review",
      order: 1,
      createdAt: ts,
      updatedAt: ts,
    },
    {
      id: "seed-10",
      title: "Landingpage Performance messen",
      description: "Lighthouse Score der Startseite verbessern.",
      labelIds: ["lbl-1"],
      assigneeId: "mem-1",
      dueDate: null,
      checklist: [],
      status: "done",
      order: 1,
      createdAt: ts,
      updatedAt: ts,
    },
  ];

  return {
    version: BOARD_SCHEMA_VERSION,
    labels,
    members,
    tasks,
  };
}
