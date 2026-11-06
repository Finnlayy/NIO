"use strict";
/**
 * The /api guard, the Apollo proxy's key handling and the sandbox jail, each
 * through the real handler. A forbidden call must never reach fetch or a binary.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { NextRequest } = require("next/server");
const { proxy, config } = require("../proxy");

const realFetch = globalThis.fetch;
const realEnv = { ...process.env };
test.afterEach(() => {
  globalThis.fetch = realFetch;
  process.env = { ...realEnv };
});

function guard(host, origin) {
  const headers = { host };
  if (origin !== undefined) headers.origin = origin;
  return proxy(new NextRequest("http://localhost:4001/api/apollo", { headers })).status;
}

test("guard covers every API route", () => {
  assert.equal(config.matcher, "/api/:path*");
});

test("guard refuses DNS rebinding with matching Origin and Host", () => {
  assert.equal(guard("evil.example:4001", "http://evil.example:4001"), 403);
  assert.equal(guard("evil.example:4001"), 403);
  assert.equal(guard("localhost.evil.example:4001"), 403);
  assert.equal(guard("localhost:4001@evil.example"), 403);
  assert.equal(guard(""), 403);
});

test("guard requires Origin for writes, not for reads", () => {
  const write = (method, origin) => {
    const headers = { host: "localhost:4001" };
    if (origin !== undefined) headers.origin = origin;
    return proxy(new NextRequest("http://localhost:4001/api/apollo/kanban", { method, headers })).status;
  };
  assert.equal(write("POST"), 403);
  assert.equal(write("DELETE"), 403);
  assert.equal(write("POST", "http://localhost:4001"), 200);
  assert.equal(write("GET"), 200);
});

test("guard refuses other origins, including another local port", () => {
  assert.equal(guard("localhost:4001", "http://localhost:5000"), 403);
  assert.equal(guard("localhost:4001", "https://evil.example"), 403);
  assert.equal(guard("localhost:4001", "null"), 403);
});

test("guard lets this machine through", () => {
  assert.notEqual(guard("127.0.0.1:4001", "http://127.0.0.1:4001"), 403);
  assert.notEqual(guard("localhost:4001"), 403);
  assert.notEqual(guard("[::1]:4001", "http://[::1]:4001"), 403);
});

function askApollo(endpointUrl) {
  const { POST } = require("../app/api/apollo/route");
  return POST(
    new NextRequest("http://localhost:4001/api/apollo", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ endpointUrl, messages: [{ role: "user", content: "hi" }] }),
    }),
  );
}

function recordFetch() {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    return Response.json({ choices: [{ message: { content: "ok" } }] });
  };
  return calls;
}

test("the gateway key goes only to the local gateway by default", async () => {
  process.env.FREELLMAPI_KEY = "gateway-key";
  delete process.env.FREELLMAPI_HOST;
  const calls = recordFetch();
  for (const url of ["http://127.0.0.1:3001/v1/chat/completions", "http://localhost:3001/v1/chat/completions"]) {
    assert.equal((await askApollo(url)).status, 200);
  }
  assert.equal(calls.length, 2);
  for (const call of calls) assert.equal(call.init.headers.authorization, "Bearer gateway-key");
});

test("a configured gateway host replaces the default", async () => {
  process.env.FREELLMAPI_KEY = "gateway-key";
  process.env.FREELLMAPI_HOST = "gateway.local:9000";
  const calls = recordFetch();
  assert.equal((await askApollo("http://127.0.0.1:3001/v1/x")).status, 403);
  assert.equal((await askApollo("http://gateway.local:9000/v1/x")).status, 200);
  assert.equal(calls.length, 1);
});

test("foreign targets get 403 and nothing is forwarded", async () => {
  process.env.FREELLMAPI_KEY = "gateway-key";
  process.env.OPENROUTER_API_KEY = "router-key";
  const calls = recordFetch();
  for (const url of [
    "https://evil.example/v1/chat/completions",
    "https://openrouter.evil.example/v1/chat/completions",
    "https://openrouter.ai.evil.example/v1/chat/completions",
    "http://openrouter.ai/v1/chat/completions",
  ]) {
    assert.equal((await askApollo(url)).status, 403, url);
  }
  assert.equal(calls.length, 0);
});

test("a provider key goes only to its own host", async () => {
  process.env.OPENROUTER_API_KEY = "router-key";
  process.env.GROQ_API_KEY = "groq-key";
  process.env.FREELLMAPI_KEY = "gateway-key";
  const calls = recordFetch();
  assert.equal((await askApollo("https://openrouter.ai/api/v1/chat/completions")).status, 200);
  assert.equal(calls[0].init.headers.authorization, "Bearer router-key");
});

test("upstream redirects are never followed", async () => {
  process.env.FREELLMAPI_KEY = "gateway-key";
  const calls = recordFetch();
  await askApollo("http://127.0.0.1:3001/v1/x");
  assert.equal(calls[0].init.redirect, "error");
});

async function sandbox(command) {
  const { POST } = require("../app/api/sandbox/route");
  const response = await POST(
    new NextRequest("http://localhost:4001/api/sandbox", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ command }),
    }),
  );
  return { status: response.status, body: await response.json() };
}

test("sandbox refuses every way out of the jail", async () => {
  for (const command of [
    "cat /etc/passwd",
    "cat ../README.md",
    "head --files0-from=/etc/passwd",
    "head --files0-from=list",
    "wc --files0=/etc/passwd",
    "date -f/etc/passwd",
    "date -uf/etc/passwd",
    "date --file=/etc/passwd",
    "ls -d/etc",
  ]) {
    const { status, body } = await sandbox(command);
    assert.equal(status, 400, command);
    assert.equal(body.ok, false, command);
  }
});

test("sandbox refuses a symlink that leaves the jail", async () => {
  const fs = require("node:fs");
  const path = require("node:path");
  await sandbox("pwd");
  const link = path.join(require("node:os").tmpdir(), "nio-sandbox", "escape-link");
  fs.rmSync(link, { force: true });
  fs.symlinkSync("/etc/passwd", link);
  try {
    assert.equal((await sandbox("cat escape-link")).status, 400);
  } finally {
    fs.rmSync(link, { force: true });
  }
});

test("sandbox keeps working inside the jail", async () => {
  assert.equal((await sandbox("cat README.txt")).status, 200);
  assert.equal((await sandbox("head -n 1 README.txt")).status, 200);
  assert.equal((await sandbox("date +%Y/%m")).status, 200);
  assert.equal((await sandbox("echo /etc/passwd")).body.stdout.trim(), "/etc/passwd");
});
