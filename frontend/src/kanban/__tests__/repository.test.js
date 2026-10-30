const test = require("node:test");
const assert = require("node:assert/strict");
const { createLocalStorageRepository } = require("../kanban/repository");
const { createSeedBoard } = require("../kanban/seed");

test("repository: load/save round trip", () => {
  const store = new Map();
  const fakeStorage = {
    getItem: (key) => store.get(key) || null,
    setItem: (key, val) => store.set(key, val)
  };

  const repo = createLocalStorageRepository(fakeStorage);

  // Empty
  const res1 = repo.load();
  assert.equal(res1.board, null);
  assert.equal(res1.recovered, false);

  // Save
  const board = createSeedBoard("2024-01-01");
  assert.equal(repo.save(board), true);

  // Load
  const res2 = repo.load();
  assert.equal(res2.recovered, false);
  assert.equal(res2.board.tasks.length, board.tasks.length);
});

test("repository: throws on getItem/setItem -> no throw, save false", () => {
  const fakeStorage = {
    getItem: () => { throw new Error("Private Mode"); },
    setItem: () => { throw new Error("Quota"); }
  };

  const repo = createLocalStorageRepository(fakeStorage);

  const res = repo.load();
  assert.equal(res.board, null);
  assert.equal(res.recovered, false);

  const board = createSeedBoard("2024-01-01");
  assert.equal(repo.save(board), false);
});

test("repository: corrupt payload creates backup key", () => {
  const store = new Map();
  store.set("nio.kanban.v1", "{ bad: json");

  const fakeStorage = {
    getItem: (key) => store.get(key) || null,
    setItem: (key, val) => store.set(key, val)
  };

  const repo = createLocalStorageRepository(fakeStorage);

  const res = repo.load();
  assert.equal(res.board, null);
  assert.equal(res.recovered, true);

  // Check backup
  const backupKey = Array.from(store.keys()).find(k => k.startsWith("nio.kanban.v1.corrupt-"));
  assert.ok(backupKey);
  assert.equal(store.get(backupKey), "{ bad: json");
});

test("repository: subscribe only reacts to its own key", () => {
  let handler = null;
  const fakeWin = {
    addEventListener: (evt, cb) => { handler = cb; },
    removeEventListener: () => { handler = null; }
  };

  const repo = createLocalStorageRepository(null, fakeWin);
  let extBoard = null;
  const unsub = repo.subscribe(b => { extBoard = b; });

  assert.ok(handler);

  // Wrong key
  handler({ key: "other", newValue: "foo" });
  assert.equal(extBoard, null);

  // Right key, valid json
  const board = createSeedBoard("2024-01-01");
  handler({ key: "nio.kanban.v1", newValue: JSON.stringify(board) });
  assert.ok(extBoard);
  assert.equal(extBoard.tasks.length, board.tasks.length);

  // Right key, null (deleted)
  handler({ key: "nio.kanban.v1", newValue: null });
  assert.equal(extBoard, null);

  unsub();
  assert.equal(handler, null);
});
