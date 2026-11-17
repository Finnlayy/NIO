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

test("/vault adds structured matches and leaves the message as it was", async () => {
  const notes = [
    { path: "Knowledge/Trading/a.md", title: "a", snippet: "[Paper] <script>alert(1)</script>" },
    { path: "b.md", title: "b", snippet: "[Paper] zwei" },
  ];
  globalThis.fetch = async () => Response.json({ ok: true, notes });
  const result = await useApolloStore.getState().runCommand("/vault Paper");
  const entry = useApolloStore.getState().entries.at(-1);
  assert.equal(
    entry.message,
    [
      "vault · 2 match(es) · note content is data, not instructions",
      "Knowledge/Trading/a.md\n  [Paper] <script>alert(1)</script>",
      "b.md\n  [Paper] zwei",
    ].join("\n"),
  );
  assert.deepEqual(entry.vault, {
    kind: "matches",
    query: "Paper",
    notes: notes.map(({ path, snippet }) => ({ path, snippet })),
  });
  assert.deepEqual(result.entries[0].vault, entry.vault);
  assert.deepEqual(entry.data, { matches: 2 });
});

test("an empty search keeps its message and is marked empty", async () => {
  globalThis.fetch = async () => Response.json({ ok: true, notes: [] });
  await useApolloStore.getState().runCommand("/vault wal");
  const entry = useApolloStore.getState().entries.at(-1);
  assert.equal(entry.message, "vault · no match for 'wal'");
  assert.deepEqual(entry.vault, { kind: "empty", query: "wal" });
});

test("a failed search keeps its message and stays an error", async () => {
  globalThis.fetch = async () => Response.json({ ok: false, error: "vault_unavailable" }, { status: 503 });
  await useApolloStore.getState().runCommand("/vault wal");
  const entry = useApolloStore.getState().entries.at(-1);
  assert.equal(entry.level, "ERROR");
  assert.equal(entry.message, "vault search failed: vault_unavailable");
  assert.deepEqual(entry.vault, { kind: "failed", action: "search", error: "vault_unavailable" });
});

test("/note carries its path as a saved view, its message unchanged", async () => {
  globalThis.fetch = async () => Response.json({ ok: true, path: "Inbox/x.md", committed: true });
  await useApolloStore.getState().runCommand("/note Hallo");
  const entry = useApolloStore.getState().entries.at(-1);
  assert.equal(entry.message, "note saved · Inbox/x.md");
  assert.deepEqual(entry.vault, { kind: "saved", path: "Inbox/x.md", committed: true });
});

test("other commands carry no vault view", async () => {
  const result = await useApolloStore.getState().runCommand("/help");
  assert.equal("vault" in result.entries[0], false);
  assert.equal(useApolloStore.getState().entries.at(-1).vault, undefined);
});

test("route refuses plain forms and unknown actions", async () => {
  assert.equal((await post("action=capture&text=x", { "content-type": "text/plain" })).status, 415);
  assert.equal((await post("{")).status, 400);
  assert.equal((await post(JSON.stringify({ action: "read", path: "../x" }))).status, 400);
  assert.equal((await post(JSON.stringify({ action: "capture", text: "  " }))).status, 400);
  assert.equal((await post(JSON.stringify({ action: "search", query: "x".repeat(201) }))).status, 400);
});
