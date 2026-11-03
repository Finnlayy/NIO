"use strict";
/**
 * Apollo's Kanban commands against a faked API: tasks land on the Apollo board,
 * failures stay failures, and nothing is approved without a concrete intent.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { parseCommand } = require("../apollo/commands");
const { useApolloStore } = require("../apollo/store");

const realFetch = globalThis.fetch;
let calls;

function fakeKanban({ boards = [{ id: "b_1", name: "Apollo" }], ok = true } = {}) {
  calls = [];
  globalThis.fetch = async (url, init = {}) => {
    const body = init.body ? JSON.parse(init.body) : undefined;
    calls.push({ url, body });
    if (!ok) return Response.json({ ok: false, error: "NIO_KANBAN_API_TOKEN ist nicht gesetzt" }, { status: 503 });
    if (url === "/api/ops") return Response.json({ runs: [{ run_id: "run_1", agent: "demo", state: "running", created_at: "x" }], errors: {} });
    if (body?.path === "/api/v1/kanban/boards" && body.method === "GET") return Response.json(boards);
    if (body?.path === "/api/v1/kanban/boards") return Response.json({ id: "b_new", name: "Apollo" });
    if (body?.path === "/api/v1/workers") return Response.json([{ uid: "w1", name: "Scout", status: "idle" }]);
    return Response.json({ id: "t_1" });
  };
}

function taskPosts() {
  return calls.filter((call) => call.body?.path === "/api/v1/kanban/tasks");
}

test.afterEach(() => {
  globalThis.fetch = realFetch;
});

test("/spawn creates a task and needs no PIN", async () => {
  fakeKanban();
  const result = await useApolloStore.getState().runCommand("/spawn inference kanban-probe");
  assert.equal(result.ok, true);
  assert.equal(taskPosts()[0].body.payload.board_id, "b_1");
  assert.ok(calls.every((call) => !call.url.includes("/secure")));
});

test("a missing Apollo board is created once", async () => {
  fakeKanban({ boards: [{ id: "b_9", name: "other" }] });
  const [nodeId] = useApolloStore.getState().nodes.map((node) => node.id);
  await useApolloStore.getState().runCommand(`/dispatch ${nodeId} {"a":1}`);
  assert.equal(calls.filter((call) => call.body?.path === "/api/v1/kanban/boards" && call.body.method === "POST").length, 1);
  assert.equal(taskPosts()[0].body.payload.board_id, "b_new");
});

test("a Kanban failure stays a failure and spawns no node", async () => {
  fakeKanban({ ok: false });
  const before = useApolloStore.getState().nodes.length;
  const result = await useApolloStore.getState().runCommand("/spawn inference kanban-offline");
  assert.equal(result.ok, false);
  assert.equal(useApolloStore.getState().nodes.length, before);
  assert.match(result.entries.at(-1).message, /Failed/);
});

test("/approve and /deny send nothing while no intent is pending", async () => {
  fakeKanban();
  assert.deepEqual(parseCommand("/approve 1234"), { kind: "approve" });
  for (const command of ["/approve", "/deny"]) {
    const result = await useApolloStore.getState().runCommand(command);
    assert.equal(result.ok, false);
    assert.match(result.entries.at(-1).message, /No pending approval/);
  }
  assert.equal(calls.length, 0);
});

test("/runs and /agent show real rows", async () => {
  fakeKanban();
  const runs = await useApolloStore.getState().runCommand("/runs");
  assert.match(runs.entries.at(-1).message, /run_1 · demo · running/);
  const agents = await useApolloStore.getState().runCommand("/agent");
  assert.match(agents.entries.at(-1).message, /w1 · Scout · idle/);
});

test("/runs reports an unreadable store instead of no runs", async () => {
  globalThis.fetch = async () => Response.json({ runs: [], errors: { runs: true } });
  const result = await useApolloStore.getState().runCommand("/runs");
  assert.equal(result.ok, false);
  assert.match(result.entries.at(-1).message, /Run list failed/);
});
