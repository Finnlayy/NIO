"use strict";
/**
 * Apollo's vault commands: the parser, the terminal output and the fail-closed
 * contract of /api/apollo/vault. The route is only called on inputs it refuses
 * before an orchestrator process starts.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { parseCommand, COMMANDS } = require("../apollo/commands");
const { useApolloStore } = require("../apollo/store");
const { POST } = require("../app/api/apollo/vault/route");

const realFetch = globalThis.fetch;
test.afterEach(() => {
  globalThis.fetch = realFetch;
});

function post(body, headers = { "content-type": "application/json" }) {
  return POST(new Request("http://localhost/api/apollo/vault", { method: "POST", headers, body }));
}

test("/note and /vault parse their text", () => {
  assert.deepEqual(parseCommand("/note Idee: mehr Tests"), { kind: "note", text: "Idee: mehr Tests" });
  assert.deepEqual(parseCommand("/vault blauwale"), { kind: "vault-search", query: "blauwale" });
  assert.equal(parseCommand("/note").kind, "error");
  assert.equal(parseCommand("/vault   ").kind, "error");
  for (const name of ["/note", "/vault"]) assert.ok(COMMANDS.some((c) => c.command === name));
});

test("/note reports the saved path", async () => {
  let sent;
  globalThis.fetch = async (url, init) => {
    sent = { url, body: JSON.parse(init.body) };
    return Response.json({ ok: true, path: "Inbox/x.md", committed: true });
  };
  const result = await useApolloStore.getState().runCommand("/note Hallo");
  assert.equal(sent.url, "/api/apollo/vault");
  assert.deepEqual(sent.body, { action: "capture", text: "Hallo" });
  assert.equal(result.ok, true);
  assert.match(result.entries[0].message, /Inbox\/x\.md/);
});

test("/note says so when nothing was saved", async () => {
  globalThis.fetch = async () => Response.json({ ok: false, error: "vault_unavailable" }, { status: 503 });
  const result = await useApolloStore.getState().runCommand("/note Hallo");
  assert.equal(result.ok, false);
  assert.match(result.entries[0].message, /not saved: vault_unavailable/);
});

test("/vault marks matches as data", async () => {
  globalThis.fetch = async () => Response.json({ ok: true, notes: [{ path: "Knowledge/a.md", title: "a", snippet: "[wal]" }] });
  const result = await useApolloStore.getState().runCommand("/vault wal");
  assert.match(result.entries[0].message, /data, not instructions/);
  assert.match(result.entries[0].message, /Knowledge\/a\.md/);
});

test("a failed search does not read like an empty vault", async () => {
  globalThis.fetch = async () => Response.json({ ok: false, error: "vault_unavailable" }, { status: 503 });
  const result = await useApolloStore.getState().runCommand("/vault wal");
  assert.equal(result.ok, false);
  assert.doesNotMatch(result.entries[0].message, /no match/);
});

test("route refuses plain forms and unknown actions", async () => {
  assert.equal((await post("action=capture&text=x", { "content-type": "text/plain" })).status, 415);
  assert.equal((await post("{")).status, 400);
  assert.equal((await post(JSON.stringify({ action: "read", path: "../x" }))).status, 400);
  assert.equal((await post(JSON.stringify({ action: "capture", text: "  " }))).status, 400);
  assert.equal((await post(JSON.stringify({ action: "search", query: "x".repeat(201) }))).status, 400);
});
