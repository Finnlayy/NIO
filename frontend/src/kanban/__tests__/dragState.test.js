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

test("dropSlot: dragging downwards within a column lands exactly where dropped", () => {
  const { dropSlot } = require("../kanban/dragState");
  const { moveTask, columnTasks } = require("../kanban/board-logic");
  const mk = (id, order) => ({ id, title: id, description: "", labelIds: [], assigneeId: null, dueDate: null,
    checklist: [], status: "backlog", order, createdAt: "x", updatedAt: "x" });
  const board = { version: 1, tasks: [mk("a", 0), mk("b", 1), mk("c", 2), mk("d", 3)], labels: [], members: [] };
  const visible = ["a", "b", "c", "d"];
  const order = (b) => columnTasks(b, "backlog").map((t) => t.id).join("");
  // Drop "a" in the gap before "d" (rendered index 3) → a ends up between c and d.
  assert.equal(order(moveTask(board, "a", "backlog", dropSlot(visible, "a", 3), visible, "now")), "bcad");
  // Drop "d" before "b" (rendered index 1) → upwards needs no shift.
  assert.equal(order(moveTask(board, "d", "backlog", dropSlot(visible, "d", 1), visible, "now")), "adbc");
  // Drop "b" at the very end (rendered index 4).
  assert.equal(order(moveTask(board, "b", "backlog", dropSlot(visible, "b", 4), visible, "now")), "acdb");
  // From another column the index is used as-is.
  assert.equal(dropSlot(visible, "x", 2), 2);
});
