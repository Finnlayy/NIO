"use strict";
/**
 * /api/ops against the real file shapes: the limbs map of limbs/registry.json,
 * run state as limbs/agent_base.py writes it, and the Kanban API's lists. Each
 * source fails on its own, and nothing sensitive leaves the route.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { GET } = require("../app/api/ops/route");

const realFetch = globalThis.fetch;
const realCwd = process.cwd();
const realEnv = { ...process.env };
let root;

test.beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "nio-ops-"));
  fs.mkdirSync(path.join(root, "frontend"));
  fs.mkdirSync(path.join(root, "limbs"));
  fs.writeFileSync(
    path.join(root, "limbs", "registry.json"),
    JSON.stringify({
      limbs: {
        echo: { status: "active", runtime: "python3", entrypoint: "limbs/echo_limb.py", env_allow: ["GEHEIM"] },
        openmanus: { status: "planned", runtime: "python3" },
      },
    }),
  );
  process.chdir(path.join(root, "frontend"));
  process.env.NIO_KANBAN_API_TOKEN = "operator-token";
  delete process.env.NIO_KANBAN_API_HOST;
  delete process.env.NIO_KANBAN_API_PORT;
});

test.afterEach(() => {
  process.chdir(realCwd);
  process.env = { ...realEnv };
  globalThis.fetch = realFetch;
  fs.rmSync(root, { recursive: true, force: true });
});

function writeRun(id, state) {
  const dir = path.join(root, "runtime", "agents", id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "state.json"), JSON.stringify(state));
}

function kanbanOk(calls = []) {
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    if (String(url).endsWith("/api/v1/kanban/tasks")) {
      return Response.json([
        { id: "t1", title: "Titel", status: "ready", assigned_worker_uid: "w1", description: "intern", result_payload: { proposed_soul: "x" } },
      ]);
    }
    if (String(url).endsWith("/api/v1/workers")) {
      return Response.json([{ uid: "w1", name: "Worker", status: "idle", soul_md: "runtime: command", skills: ["a"] }]);
    }
    return new Response("nope", { status: 404 });
  };
}

async function read() {
  const response = await GET();
  assert.equal(response.status, 200);
  return { raw: await response.clone().text(), body: await response.json() };
}

test("reads the Kanban API on its real routes with the server token", async () => {
  const calls = [];
  kanbanOk(calls);
  const { body } = await read();
  assert.deepEqual(calls.map((c) => c.url).sort(), [
    "http://127.0.0.1:8740/api/v1/kanban/tasks",
    "http://127.0.0.1:8740/api/v1/workers",
  ]);
  for (const call of calls) {
    assert.equal(call.init.headers.authorization, "Bearer operator-token");
    assert.ok(call.init.signal, "fetch needs a timeout");
  }
  assert.deepEqual(body.kanban.tasks, [{ id: "t1", title: "Titel", status: "ready", assigned_worker_uid: "w1" }]);
  assert.deepEqual(body.kanban.workers, [{ uid: "w1", name: "Worker", status: "idle" }]);
});

test("the limbs map becomes a list with only the needed fields", async () => {
  kanbanOk();
  const { body } = await read();
  assert.deepEqual(body.limbs, [
    { name: "echo", status: "active", runtime: "python3" },
    { name: "openmanus", status: "planned", runtime: "python3" },
  ]);
});

test("runs come from state.json, newest first and capped", async () => {
  kanbanOk();
  for (let i = 0; i < 7; i += 1) {
    writeRun(`run_${i}`, { run_id: `run_${i}`, agent: "openmanus", state: "running", created_at: `2026-11-0${i + 1}T00:00:00Z`, prompt: "geheim" });
  }
  const { body } = await read();
  assert.equal(body.runs.length, 5);
  assert.deepEqual(body.runs[0], { run_id: "run_6", agent: "openmanus", state: "running", created_at: "2026-11-07T00:00:00Z" });
});

test("nothing sensitive leaves the route", async () => {
  kanbanOk();
  writeRun("run_1", { run_id: "run_1", agent: "a", state: "failed", created_at: "x", prompt: "geheim-prompt", output: "geheim-output" });
  const { raw } = await read();
  for (const word of ["result_payload", "proposed_soul", "soul_md", "runtime: command", "description", "intern", "geheim", "operator-token", "env_allow", "entrypoint"]) {
    assert.ok(!raw.includes(word), `${word} leaked`);
  }
});

test("a missing token flags only Kanban", async () => {
  delete process.env.NIO_KANBAN_API_TOKEN;
  globalThis.fetch = async () => assert.fail("no request without a token");
  const { body } = await read();
  assert.deepEqual(body.errors, { kanban: true, limbs: false, runs: false });
  assert.equal(body.limbs.length, 2);
});

test("a Kanban outage flags only Kanban", async () => {
  globalThis.fetch = async () => {
    throw new Error("connection refused");
  };
  const { body } = await read();
  assert.deepEqual(body.errors, { kanban: true, limbs: false, runs: false });
});

test("a broken registry flags only limbs", async () => {
  kanbanOk();
  fs.writeFileSync(path.join(root, "limbs", "registry.json"), "kein json");
  const { body } = await read();
  assert.deepEqual(body.errors, { kanban: false, limbs: true, runs: false });
  assert.equal(body.kanban.tasks.length, 1);
});

test("no runs yet is not an error, and a half-written run is skipped", async () => {
  kanbanOk();
  assert.deepEqual((await read()).body.errors.runs, false);
  writeRun("run_ok", { run_id: "run_ok", agent: "a", state: "running", created_at: "2026-11-01T00:00:00Z" });
  fs.mkdirSync(path.join(root, "runtime", "agents", "run_half"));
  const { body } = await read();
  assert.deepEqual(body.runs.map((r) => r.run_id), ["run_ok"]);
  assert.equal(body.errors.runs, false);
});
