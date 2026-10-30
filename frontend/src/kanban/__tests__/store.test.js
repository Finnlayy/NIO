const test = require("node:test");
const assert = require("node:assert/strict");
const { createKanbanStore } = require("../kanban/store");

test("store: before hydrate, actions do not call repo.save", () => {
  let saveCount = 0;
  const repo = {
    load: () => ({ board: null, recovered: false }),
    save: () => { saveCount++; return true; },
    subscribe: () => () => {}
  };
  
  const store = createKanbanStore(repo, { now: () => "2024-01-01T00:00:00Z", today: () => "2024-01-01" });
  
  store.getState().addTask({ title: "Task 1", status: "backlog", description: "", labelIds: [], assigneeId: null, dueDate: null, checklist: [] });
  assert.equal(saveCount, 0);
  assert.equal(store.getState().hydrated, false);
});

test("store: after hydrate actions call save", () => {
  let saveCount = 0;
  let savedBoard = null;
  const repo = {
    load: () => ({ board: null, recovered: false }),
    save: (b) => { saveCount++; savedBoard = b; return true; },
    subscribe: () => () => {}
  };
  
  const store = createKanbanStore(repo, { now: () => "2024-01-01T00:00:00Z", today: () => "2024-01-01" });
  store.getState().hydrate();
  
  store.getState().addTask({ title: "Task 1", status: "backlog", description: "", labelIds: [], assigneeId: null, dueDate: null, checklist: [] });
  assert.equal(saveCount, 1);
  assert.equal(store.getState().hydrated, true);
  assert.ok(savedBoard.tasks.some(t => t.title === "Task 1"));
});

test("store: external change replaces board", () => {
  let onExt = null;
  const repo = {
    load: () => ({ board: null, recovered: false }),
    save: () => true,
    subscribe: (cb) => { onExt = cb; return () => {}; }
  };
  
  const store = createKanbanStore(repo, { now: () => "2024-01-01T00:00:00Z", today: () => "2024-01-01" });
  store.getState().hydrate();
  
  assert.ok(onExt);
  
  const b2 = { version: 1, tasks: [], labels: [], members: [] };
  onExt(b2);
  
  assert.equal(store.getState().board, b2);
});

test("store: undoRemove restores", () => {
  const repo = {
    load: () => ({ board: null, recovered: false }),
    save: () => true,
    subscribe: () => () => {}
  };
  const store = createKanbanStore(repo, { now: () => "2024-01-01T00:00:00Z", today: () => "2024-01-01" });
  
  const st = store.getState();
  const idToRemove = st.board.tasks[0].id;
  
  st.removeTask(idToRemove);
  
  assert.equal(store.getState().board.tasks.find(t => t.id === idToRemove), undefined);
  assert.ok(store.getState().lastRemoved !== null);
  
  store.getState().undoRemove();
  assert.ok(store.getState().board.tasks.find(t => t.id === idToRemove));
  assert.equal(store.getState().lastRemoved, null);
});

test("store: saveFailed reflects repo", () => {
  let shouldFail = false;
  const repo = {
    load: () => ({ board: null, recovered: false }),
    save: () => !shouldFail,
    subscribe: () => () => {}
  };
  
  const store = createKanbanStore(repo, { now: () => "2024-01-01T00:00:00Z", today: () => "2024-01-01" });
  store.getState().hydrate();
  
  shouldFail = true;
  store.getState().addTask({ title: "Task 1", status: "backlog", description: "", labelIds: [], assigneeId: null, dueDate: null, checklist: [] });
  assert.equal(store.getState().saveFailed, true);
  
  shouldFail = false;
  store.getState().addTask({ title: "Task 2", status: "backlog", description: "", labelIds: [], assigneeId: null, dueDate: null, checklist: [] });
  assert.equal(store.getState().saveFailed, false);
});
