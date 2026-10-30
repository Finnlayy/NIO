const assert = require("node:assert");
const test = require("node:test");
const { kanbanStore } = require("../kanban/useKanbanStore.js");
const { localToday } = require("../kanban/board-logic.js");
const { kanbanHotkey } = require("../kanban/hotkeys.js");

test("Kanban flow: create, edit, delete, undo", () => {
  const store = kanbanStore.getState();
  kanbanStore.setState({ board: { version: 1, tasks: [], labels: [], members: [] }, lastRemoved: null });

  store.addTask({
    title: "Test Task",
    description: "",
    labelIds: [],
    assigneeId: null,
    dueDate: null,
    status: "backlog",
    checklist: []
  });

  let board = kanbanStore.getState().board;
  assert.equal(board.tasks.length, 1);
  const task = board.tasks[0];
  assert.equal(task.title, "Test Task");
  assert.equal(task.status, "backlog");

  store.addChecklistItem(task.id, "First item");
  store.addChecklistItem(task.id, "Second item");

  board = kanbanStore.getState().board;
  let updatedTask = board.tasks.find(t => t.id === task.id);
  assert.equal(updatedTask.checklist.length, 2);

  store.toggleChecklistItem(task.id, updatedTask.checklist[0].id);
  board = kanbanStore.getState().board;
  updatedTask = board.tasks.find(t => t.id === task.id);
  assert.equal(updatedTask.checklist[0].completed, true);
  assert.equal(updatedTask.checklist[1].completed, false);

  store.removeTask(task.id);
  board = kanbanStore.getState().board;
  assert.equal(board.tasks.length, 0);
  assert.ok(kanbanStore.getState().lastRemoved, "lastRemoved should be populated");

  kanbanStore.getState().undoRemove();
  board = kanbanStore.getState().board;
  assert.equal(board.tasks.length, 1);
  const restoredTask = board.tasks[0];
  assert.equal(restoredTask.title, "Test Task");
  assert.equal(restoredTask.status, "backlog");
  assert.equal(kanbanStore.getState().lastRemoved, null, "lastRemoved should be cleared");
});
