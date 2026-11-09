"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { guardRequest, proxyTelegram, WRITE_HEADER } = require("../telegram/proxy");

const base = {
  method: "GET",
  segments: ["status"],
  host: "localhost:4001",
  origin: null,
  fetchSite: "same-origin",
  writeHeader: null,
  extraHosts: [],
};

function refused(over, status) {
  const result = guardRequest({ ...base, ...over });
  assert.equal(result.ok, false);
  assert.equal(result.status, status);
}

test("guard: same-origin read and marked write pass", () => {
  assert.deepEqual(guardRequest(base), { ok: true });
  assert.deepEqual(
    guardRequest({ ...base, method: "POST", segments: ["suggestions", "sug--100-1-0", "approve"], writeHeader: "1", origin: "http://localhost:4001" }),
    { ok: true },
  );
  assert.deepEqual(guardRequest({ ...base, method: "DELETE", segments: ["monitored", "-1001"], writeHeader: "1" }), { ok: true });
  assert.deepEqual(guardRequest({ ...base, host: "[::1]:4001" }), { ok: true });
});

test("guard: DNS rebinding host is refused unless configured", () => {
  refused({ host: "evil.example:4001" }, 403);
  refused({ host: null }, 403);
  assert.deepEqual(guardRequest({ ...base, host: "nio.lan:4001", extraHosts: ["nio.lan"] }), { ok: true });
});

test("guard: cross-site browser requests are refused", () => {
  refused({ fetchSite: "cross-site" }, 403);
  refused({ fetchSite: "same-site" }, 403);
  refused({ origin: "http://evil.example" }, 403);
  refused({ origin: "not a url" }, 403);
  refused({ method: "POST", segments: ["suggestions", "x", "approve"] }, 403);
});

test("guard: unknown routes and traversal never reach the API", () => {
  refused({ segments: ["login"] }, 404);
  refused({ segments: [] }, 404);
  refused({ segments: ["status", ".."] }, 404);
  refused({ segments: ["monitored", "..", "..", "kanban", "tasks"] }, 404);
  refused({ segments: ["monitored", "a/b"] }, 404);
});

function request(path, init = {}) {
  const headers = new Headers({ host: "localhost:4001", "sec-fetch-site": "same-origin", ...init.headers });
  return { method: init.method ?? "GET", url: `http://localhost:4001/api/telegram/${path}`, headers, signal: undefined, text: async () => init.body ?? "" };
}

const env = { NIO_KANBAN_API_TOKEN: "op-secret", NIO_KANBAN_API_URL: "http://api.local:8740/" };

test("proxy: adds the bearer server-side and drops upstream headers", async () => {
  let seen;
  const res = await proxyTelegram(request("suggestions?status=pending"), ["suggestions"], env, async (url, init) => {
    seen = { url, init };
    return new Response("[]", { headers: { "content-type": "application/json", "set-cookie": "a=b" } });
  });
  assert.equal(seen.url, "http://api.local:8740/api/v1/telegram/suggestions?status=pending");
  assert.equal(seen.init.headers.Authorization, "Bearer op-secret");
  assert.equal(seen.init.redirect, "manual");
  assert.equal(res.headers.get("set-cookie"), null);
  assert.equal(await res.text(), "[]");
  assert.ok(!JSON.stringify([...res.headers]).includes("op-secret"));
});

test("proxy: never forwards a client Authorization header", async () => {
  let seen;
  await proxyTelegram(request("status", { headers: { authorization: "Bearer stolen" } }), ["status"], env, async (_u, init) => {
    seen = init;
    return new Response("{}");
  });
  assert.equal(seen.headers.Authorization, "Bearer op-secret");
});

test("proxy: passes Retry-After through on 429", async () => {
  const req = request("suggestions/x/approve", { method: "POST", headers: { [WRITE_HEADER]: "1" }, body: "{}" });
  const res = await proxyTelegram(req, ["suggestions", "x", "approve"], env, async () => new Response('{"detail":"x"}', { status: 429, headers: { "retry-after": "12" } }));
  assert.equal(res.status, 429);
  assert.equal(res.headers.get("retry-after"), "12");
});

test("proxy: missing token, dead backend, redirect and big body", async () => {
  const noFetch = async () => assert.fail("no upstream call expected");
  assert.equal((await proxyTelegram(request("status"), ["status"], {}, noFetch)).status, 503);
  const down = await proxyTelegram(request("status"), ["status"], env, async () => {
    throw new Error("refused");
  });
  assert.equal(down.status, 502);
  assert.equal((await down.json()).code, "backend_down");
  const moved = await proxyTelegram(request("status"), ["status"], env, async () => new Response(null, { status: 302, headers: { location: "http://evil.example" } }));
  assert.equal(moved.status, 502);
  const big = request("ask", { method: "POST", headers: { [WRITE_HEADER]: "1" }, body: "x".repeat(70 * 1024) });
  assert.equal((await proxyTelegram(big, ["ask"], env, noFetch)).status, 413);
});

test("proxy: refused requests never touch the API", async () => {
  const res = await proxyTelegram(request("status", { headers: { "sec-fetch-site": "cross-site" } }), ["status"], env, async () => assert.fail("called"));
  assert.equal(res.status, 403);
});
