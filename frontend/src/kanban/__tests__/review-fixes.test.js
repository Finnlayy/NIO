const test = require("node:test");
const assert = require("node:assert/strict");
const { moveTask, removeTask, restoreTask, columnTasks, filterTasks } = require("../kanban/board-logic");
const { parseStoredBoard } = require("../kanban/validate");
const { kanbanHotkey } = require("../kanban/hotkeys");
const { createKanbanStore } = require("../kanban/store");
const { createSeedBoard } = require("../kanban/seed");

const NOW = "2024-06-01T10:00:00.000Z";

function task(id, status, order, labelIds = []) {
  return {
    id, title: id, description: "", labelIds, assigneeId: null, dueDate: null, checklist: [],
    status, order, createdAt: "2024-01-01T00:00:00.000Z", updatedAt: "2024-01-01T00:00:00.000Z",
  };
}

function board(tasks) {
  return { version: 1, tasks, labels: [{ id: "x", name: "X", color: "#fff" }], members: [] };
}

const ids = (b, status) => columnTasks(b, status).map((t) => t.id);

test("moveTask: filtered target keeps hidden cards in place", () => {
  // review column: a(x) h1 b(x) h2 — only a and b are visible under the label filter.
  const b = board([
    task("a", "review", 0, ["x"]), task("h1", "review", 1), task("b", "review", 2, ["x"]),
    task("h2", "review", 3), task("m", "backlog", 0, ["x"]),
  ]);
  const visible = filterTasks(columnTasks(b, "review"), { labelIds: ["x"], assigneeIds: [] }).map((t) => t.id);
  assert.deepEqual(visible, ["a", "b"]);

  assert.deepEqual(ids(moveTask(b, "m", "review", 1, visible, NOW), "review"), ["a", "h1", "m", "b", "h2"]);
  assert.deepEqual(ids(moveTask(b, "m", "review", 0, visible, NOW), "review"), ["m", "a", "h1", "b", "h2"]);
  // Past the last visible card: right after it, before the trailing hidden card.
  assert.deepEqual(ids(moveTask(b, "m", "review", 9, visible, NOW), "review"), ["a", "h1", "b", "m", "h2"]);
});

test("moveTask: same-column moves, no-op returns the identical board", () => {
  const b = board([task("a", "backlog", 0), task("b", "backlog", 1), task("c", "backlog", 2)]);
  const all = ["a", "b", "c"];
  assert.deepEqual(ids(moveTask(b, "a", "backlog", 2, all, NOW), "backlog"), ["b", "c", "a"]);
  assert.deepEqual(ids(moveTask(b, "c", "backlog", 0, all, NOW), "backlog"), ["c", "a", "b"]);
  assert.equal(moveTask(b, "b", "backlog", 1, all, NOW), b);
  assert.equal(moveTask(b, "nope", "review", 0, [], NOW), b);
  const moved = moveTask(b, "a", "done", 0, [], NOW);
  assert.equal(moved.tasks.find((t) => t.id === "a").updatedAt, NOW);
  assert.deepEqual(ids(moved, "backlog").map((id) => moved.tasks.find((t) => t.id === id).order), [0, 1]);
});

test("restoreTask: returns to its column position even after the column was renumbered", () => {
  const b = board([task("a", "backlog", 0), task("b", "backlog", 1), task("c", "backlog", 2), task("d", "backlog", 3)]);
  const { board: without, removed } = removeTask(b, "c");
  assert.equal(removed.index, 2);
  // Someone reorders meanwhile: d to the top.
  const reordered = moveTask(without, "d", "backlog", 0, ["a", "b", "d"], NOW);
  assert.deepEqual(ids(reordered, "backlog"), ["d", "a", "b"]);
  assert.deepEqual(ids(restoreTask(reordered, removed), "backlog"), ["d", "a", "c", "b"]);
  // Column shrank below the old index: clamp to the end.
  const shrunk = removeTask(removeTask(without, "a").board, "b").board;
  assert.deepEqual(ids(restoreTask(shrunk, removed), "backlog"), ["d", "c"]);
});

test("parseStoredBoard: null entries and missing fields are repaired, not thrown", () => {
  const raw = JSON.stringify({
    version: 1,
    labels: [null, { id: "l1", name: "Bug" }, { id: "l1", name: "Dup", color: "#000" }],
    members: [7, { id: "m1", name: "Lena Hoffmann" }],
    tasks: [
      null, "x", { id: "t0", title: "   " },
      {
        id: "t1", title: "Echt", status: "backlog", order: "NaN", labelIds: ["l1"], assigneeId: { id: "m1" },
        dueDate: "2024-06-01", checklist: [null, { id: "c1", title: "Punkt" }, { id: "c2", title: "ok", completed: true }],
      },
    ],
  });
  const { board: b, recovered } = parseStoredBoard(raw);
  assert.equal(recovered, true);
  assert.deepEqual(b.labels, [{ id: "l1", name: "Bug", color: "#64748b" }]);
  assert.deepEqual(b.members, [{ id: "m1", name: "Lena Hoffmann", initials: "LH", color: "#64748b" }]);
  assert.deepEqual(b.tasks.map((t) => t.id), ["t1"]);
  const t1 = b.tasks[0];
  assert.equal(t1.assigneeId, null);
  assert.equal(t1.order, 0);
  assert.deepEqual(t1.checklist, [
    { id: "c1", title: "Punkt", completed: false },
    { id: "c2", title: "ok", completed: true },
  ]);
});

test("hotkeys: nothing fires while an IME composes, Escape included", () => {
  const base = { metaKey: false, ctrlKey: false, altKey: false, target: null, isComposing: true };
  assert.equal(kanbanHotkey({ ...base, key: "Escape" }, { dialogOpen: true, menuOpen: true }), null);
  assert.equal(kanbanHotkey({ ...base, key: "Enter", metaKey: true }, { dialogOpen: true, menuOpen: false }), null);
  assert.equal(kanbanHotkey({ ...base, key: "c" }, { dialogOpen: false, menuOpen: false }), null);
});

test("store: dispose unsubscribes, no-op checklist changes do not save", () => {
  let saves = 0;
  let unsubscribed = false;
  const repo = {
    load: () => ({ board: null, recovered: false }),
    save: () => { saves++; return true; },
    subscribe: () => () => { unsubscribed = true; },
  };
  const store = createKanbanStore(repo, { now: () => NOW, today: () => "2024-06-01" });
  store.getState().hydrate();
  const id = store.getState().board.tasks[0].id;
  const before = store.getState().board;
  store.getState().addChecklistItem(id, "   ");
  store.getState().toggleChecklistItem(id, "does-not-exist");
  assert.equal(saves, 0);
  assert.equal(store.getState().board, before);
  store.getState().addChecklistItem(id, "Neu");
  assert.equal(saves, 1);
  store.getState().dispose();
  assert.equal(unsubscribed, true);
});

test("seed: overdue and upcoming dates are exact calendar offsets in any time zone", () => {
  const prev = process.env.TZ;
  try {
    for (const tz of ["UTC", "Pacific/Kiritimati", "Pacific/Pago_Pago", "Europe/Berlin"]) {
      process.env.TZ = tz;
      const dates = createSeedBoard("2024-03-01").tasks.map((t) => t.dueDate).filter(Boolean).sort();
      assert.deepEqual(dates, ["2024-02-25", "2024-03-01", "2024-03-01", "2024-03-04"], tz);
    }
  } finally {
    if (prev === undefined) delete process.env.TZ;
    else process.env.TZ = prev;
  }
});
