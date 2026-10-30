const test = require("node:test");
const assert = require("node:assert/strict");
const { 
  localToday, 
  isOverdue, 
  newId, 
  moveTask, 
  filterTasks, 
  normalizeOrders, 
  addTask, 
  updateTask, 
  removeTask, 
  restoreTask,
  addChecklistItem,
  toggleChecklistItem,
  renameChecklistItem,
  removeChecklistItem,
  checklistProgress,
  columnCounts
} = require("../kanban/board-logic");
const { createSeedBoard } = require("../kanban/seed");

test("board-logic: localToday format", () => {
  const d = new Date(2025, 4, 2); // Month is 0-indexed, so 4 is May
  assert.equal(localToday(d), "2025-05-02");
});

test("board-logic: isOverdue string comparison", () => {
  const today = "2024-05-15";
  const overdueTask = { dueDate: "2024-05-14", status: "in_progress" };
  const dueTodayTask = { dueDate: "2024-05-15", status: "backlog" };
  const futureTask = { dueDate: "2024-05-16", status: "backlog" };
  const doneTask = { dueDate: "2024-05-14", status: "done" };
  const nullTask = { dueDate: null, status: "in_progress" };

  assert.equal(isOverdue(overdueTask, today), true);
  assert.equal(isOverdue(dueTodayTask, today), false);
  assert.equal(isOverdue(futureTask, today), false);
  assert.equal(isOverdue(doneTask, today), false);
  assert.equal(isOverdue(nullTask, today), false);
});

test("board-logic: newId fallback when crypto.randomUUID is undefined", () => {
  const originalCrypto = globalThis.crypto;
  // Temporarily remove crypto.randomUUID
  if (globalThis.crypto) {
    globalThis.crypto.randomUUID = undefined;
  }
  
  const id1 = newId();
  const id2 = newId("test");
  
  assert.ok(id1.startsWith("t-"));
  assert.ok(id2.startsWith("test-"));
  assert.notEqual(id1, id2);
  
  // Restore
  globalThis.crypto = originalCrypto;
});

test("board-logic: filterTasks AND/ANY semantics incl. '__unassigned__'", () => {
  const t1 = { id: "1", labelIds: ["lbl1"], assigneeId: "mem1" };
  const t2 = { id: "2", labelIds: ["lbl1", "lbl2"], assigneeId: null };
  const t3 = { id: "3", labelIds: ["lbl3"], assigneeId: "mem2" };
  const tasks = [t1, t2, t3];

  // No filter
  assert.equal(filterTasks(tasks, { labelIds: [], assigneeIds: [] }).length, 3);
  
  // Label ANY
  let res = filterTasks(tasks, { labelIds: ["lbl1"], assigneeIds: [] });
  assert.equal(res.length, 2);
  assert.deepEqual(res.map(t => t.id), ["1", "2"]);

  // Label ANY + Assignee AND
  res = filterTasks(tasks, { labelIds: ["lbl1"], assigneeIds: ["mem1"] });
  assert.equal(res.length, 1);
  assert.equal(res[0].id, "1");

  // Unassigned
  res = filterTasks(tasks, { labelIds: [], assigneeIds: ["__unassigned__"] });
  assert.equal(res.length, 1);
  assert.equal(res[0].id, "2");
});

test("board-logic: columnCounts visible/total", () => {
  const board = createSeedBoard("2024-01-01");
  const counts = columnCounts(board, { labelIds: [], assigneeIds: [] });
  // All visible
  assert.equal(counts.backlog.visible, counts.backlog.total);
  
  // With filter
  const filter = { labelIds: ["lbl-1"], assigneeIds: [] }; // Frontend label
  const filteredCounts = columnCounts(board, filter);
  
  // in_progress has 2 items in seed data: 
  // seed-1 has lbl-1, lbl-4 -> matches
  // seed-4 has lbl-1, lbl-2 -> matches
  // So visible == total for in_progress with this filter.
  // Let's use a filter that matches only one of them. "lbl-2" matches seed-4 but not seed-1.
  const filter2 = { labelIds: ["lbl-2"], assigneeIds: [] };
  const filteredCounts2 = columnCounts(board, filter2);
  
  assert.ok(filteredCounts2.in_progress.visible < filteredCounts2.in_progress.total);
  assert.ok(filteredCounts2.in_progress.total > 0);
});

test("board-logic: normalizeOrders repairs duplicates/gaps deterministically", () => {
  const tasks = [
    { id: "3", status: "backlog", order: 5, createdAt: "2024" },
    { id: "1", status: "backlog", order: 5, createdAt: "2023" }, // duplicate order, older createdAt
    { id: "2", status: "backlog", order: 10, createdAt: "2024" } // gap
  ];
  const normalized = normalizeOrders(tasks);
  
  // Sort should be: 1 (order 5, 2023), 3 (order 5, 2024), 2 (order 10)
  assert.equal(normalized.length, 3);
  const backlog = normalized.filter(t => t.status === "backlog");
  assert.deepEqual(backlog.map(t => t.id), ["1", "3", "2"]);
  assert.deepEqual(backlog.map(t => t.order), [0, 1, 2]);
});

test("board-logic: add/update/remove/restore", () => {
  let board = createSeedBoard("2024-01-01");
  
  // Add
  board = addTask(board, { status: "backlog", title: " New Task   ", description: "", labelIds: [], assigneeId: null, dueDate: null, checklist: [] }, "2024-01-01T10:00:00Z");
  const newTask = board.tasks[board.tasks.length - 1];
  assert.equal(newTask.title, "New Task"); // Trimmed
  assert.equal(newTask.status, "backlog");
  
  // Update
  assert.throws(() => updateTask(board, newTask.id, { title: "   " }, "2024-01-01T10:01:00Z"), /empty/);
  
  board = updateTask(board, newTask.id, { description: "Updated" }, "2024-01-01T10:01:00Z");
  let updatedTask = board.tasks.find(t => t.id === newTask.id);
  assert.equal(updatedTask.description, "Updated");
  
  // Remove
  const { board: bRemoved, removed } = removeTask(board, newTask.id);
  assert.equal(bRemoved.tasks.some(t => t.id === newTask.id), false);
  assert.ok(removed !== null);
  
  // Restore
  const bRestored = restoreTask(bRemoved, removed);
  assert.equal(bRestored.tasks.some(t => t.id === newTask.id), true);
});

test("board-logic: checklist ops + progress", () => {
  let task = { id: "t1", checklist: [] };
  
  task = addChecklistItem(task, "  Item 1 ");
  assert.equal(task.checklist.length, 1);
  assert.equal(task.checklist[0].title, "Item 1");
  
  const cid = task.checklist[0].id;
  task = toggleChecklistItem(task, cid);
  assert.equal(task.checklist[0].completed, true);
  
  let p = checklistProgress(task);
  assert.equal(p.done, 1);
  assert.equal(p.total, 1);
  
  task = renameChecklistItem(task, cid, "Renamed");
  assert.equal(task.checklist[0].title, "Renamed");
  
  task = removeChecklistItem(task, cid);
  assert.equal(task.checklist.length, 0);
  
  // Empty rename -> remove
  task = addChecklistItem(task, "Item 2");
  const cid2 = task.checklist[0].id;
  task = renameChecklistItem(task, cid2, "   ");
  assert.equal(task.checklist.length, 0);
});

test("board-logic: moveTask across columns, index clamping, dense orders, immutability", () => {
  let board = createSeedBoard("2024-01-01");
  const initialStr = JSON.stringify(board);
  
  const backlog = board.tasks.filter(t => t.status === "backlog").sort((a,b) => a.order - b.order);
  const done = board.tasks.filter(t => t.status === "done").sort((a,b) => a.order - b.order);
  const tToMove = backlog[0];
  
  const visibleIds = done.map(t => t.id); // No filter applied in this simple test
  
  // Move to done, top position
  const bNext = moveTask(board, tToMove.id, "done", 0, visibleIds, "2024-01-01T12:00:00Z");
  
  // Immutability check
  assert.equal(JSON.stringify(board), initialStr);
  
  const doneNext = bNext.tasks.filter(t => t.status === "done").sort((a,b) => a.order - b.order);
  assert.equal(doneNext[0].id, tToMove.id);
  assert.equal(doneNext[0].order, 0);
  assert.equal(doneNext[1].id, done[0].id);
  assert.equal(doneNext[1].order, 1);
  assert.equal(doneNext[0].updatedAt, "2024-01-01T12:00:00Z");
  
  // Move to same pos -> no-op
  const bSame = moveTask(bNext, tToMove.id, "done", 0, visibleIds, "2024-01-01T12:01:00Z");
  assert.equal(bSame, bNext);
  
  // Clamping test: large index
  const bClamp = moveTask(bNext, tToMove.id, "done", 999, doneNext.map(t => t.id), "2024-01-01T12:02:00Z");
  const doneClamp = bClamp.tasks.filter(t => t.status === "done").sort((a,b) => a.order - b.order);
  assert.equal(doneClamp[doneClamp.length - 1].id, tToMove.id);
});
