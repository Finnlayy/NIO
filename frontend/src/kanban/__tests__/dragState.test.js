const { test } = require("node:test");
const assert = require("node:assert");
const { createDragState } = require("../kanban/dragState");

test("dragState: begin/over/drop sequence returns the move", () => {
  const ds = createDragState();
  assert.strictEqual(ds.active, false);

  ds.begin("t1", "backlog");
  assert.strictEqual(ds.active, true);
  assert.deepStrictEqual(ds.current, { taskId: "t1", fromStatus: "backlog", overStatus: null, overIndex: null });

  const overRes = ds.over("in_progress", 2);
  assert.deepStrictEqual(overRes, { taskId: "t1", fromStatus: "backlog", overStatus: "in_progress", overIndex: 2 });

  const move = ds.drop();
  assert.deepStrictEqual(move, { taskId: "t1", toStatus: "in_progress", toIndex: 2 });

  assert.strictEqual(ds.active, false);
});

test("dragState: drop without over returns null", () => {
  const ds = createDragState();
  ds.begin("t2", "review");
  const move = ds.drop();
  assert.strictEqual(move, null);
  assert.strictEqual(ds.active, false);
});

test("dragState: cancel returns null and inactive", () => {
  const ds = createDragState();
  ds.begin("t3", "done");
  ds.over("backlog", 0);
  ds.cancel();
  assert.strictEqual(ds.active, false);
  const move = ds.drop();
  assert.strictEqual(move, null);
});

test("dragState: drop after cancel returns null", () => {
  const ds = createDragState();
  ds.begin("t4", "backlog");
  ds.over("in_progress", 1);
  ds.cancel();
  const move = ds.drop();
  assert.strictEqual(move, null);
});
