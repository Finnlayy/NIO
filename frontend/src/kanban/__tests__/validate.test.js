const test = require("node:test");
const assert = require("node:assert/strict");
const { parseStoredBoard } = require("../kanban/validate");
const { BOARD_SCHEMA_VERSION } = require("../kanban/types");
const { createSeedBoard } = require("../kanban/seed");

test("validate: null/empty -> board:null, recovered:false", () => {
  assert.deepEqual(parseStoredBoard(null), { board: null, recovered: false });
  assert.deepEqual(parseStoredBoard(""), { board: null, recovered: false });
  assert.deepEqual(parseStoredBoard("   "), { board: null, recovered: false });
});

test("validate: invalid JSON -> board:null, recovered:true", () => {
  const res = parseStoredBoard("{ bad: json");
  assert.equal(res.board, null);
  assert.equal(res.recovered, true);
  assert.equal(res.reason, "Invalid JSON");
});

test("validate: wrong version -> board:null, recovered:true", () => {
  const data = { version: 999, tasks: [], labels: [], members: [] };
  const res = parseStoredBoard(JSON.stringify(data));
  assert.equal(res.board, null);
  assert.equal(res.recovered, true);
});

test("validate: valid payload -> no recovery", () => {
  const board = createSeedBoard("2024-01-01");
  const res = parseStoredBoard(JSON.stringify(board));
  assert.equal(res.recovered, false);
  assert.deepEqual(res.board.tasks.length, board.tasks.length);
});

test("validate: repairs", () => {
  const board = createSeedBoard("2024-01-01");
  
  // Create a mess
  board.tasks[0].status = "unknown_status"; // -> backlog
  board.tasks[0].labelIds.push("missing_lbl"); // -> filtered out
  board.tasks[0].assigneeId = "missing_mem"; // -> null
  board.tasks[0].dueDate = "not-a-date"; // -> null
  board.tasks[0].checklist.push({ id: "123", title: "  ", completed: false }); // empty title -> dropped
  
  // duplicate id
  board.tasks.push({ ...board.tasks[1] }); // id is same as tasks[1] -> dropped

  // missing string id
  board.tasks.push({ title: "No ID", status: "backlog" }); // -> dropped
  
  const res = parseStoredBoard(JSON.stringify(board));
  
  assert.equal(res.recovered, true);
  assert.notEqual(res.board, null);
  
  const t0 = res.board.tasks.find(t => t.id === board.tasks[0].id);
  assert.equal(t0.status, "backlog");
  assert.equal(t0.labelIds.includes("missing_lbl"), false);
  assert.equal(t0.assigneeId, null);
  assert.equal(t0.dueDate, null);
  assert.equal(t0.checklist.length, board.tasks[0].checklist.length - 1); // dropped the empty one
  
  // Duplicate dropped (original seed length)
  // Wait, seed has 10 tasks. We added duplicate (dropped), added no-id (dropped).
  assert.equal(res.board.tasks.length, 10);
});
