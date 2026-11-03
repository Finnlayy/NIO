"use strict";
/** Mocked contract tests, NOT evidence of successful external provider access. */
const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { NextRequest } = require("next/server");
const { GET, POST } = require("../app/api/apollo/route");
const { POST: probe } = require("../app/api/apollo/providers/route");
const { secretEnvironment } = require("../server/secretManager");
const { useApolloStore } = require("../apollo/store");
const originalEnv = { ...process.env }, originalFetch = globalThis.fetch;
let tmp;
test.beforeEach(() => {
  process.env = { NIO_REPO_ROOT: path.resolve(__dirname, "../../.."), PATH: originalEnv.PATH };
  globalThis.nioProviderHealth?.clear();
  globalThis.nioProviderProbeAt = undefined;
});
test.afterEach(() => {
  process.env = { ...originalEnv };
  globalThis.fetch = originalFetch;
  if (tmp) { fs.rmSync(tmp, { recursive: true, force: true }); tmp = undefined; }
});
function ask(extra = {}) {
  return POST(new NextRequest("http://localhost/api/apollo", { method: "POST", body: JSON.stringify({ messages: [{ role: "user", content: "OK?" }], ...extra }) }));
}
function secretFile(data, mode = 0o600) {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "nio-secrets-test-"));
  const file = path.join(tmp, "secrets.json");
  fs.writeFileSync(file, JSON.stringify(data), { mode });
  process.env.NIO_SECRET_FILE = file;
  return file;
}

test("missing credentials never produce a request, readiness or a simulation", async () => {
  globalThis.fetch = async () => assert.fail("no credential means no outbound request");
  const status = await (await GET()).json();
  assert.equal(status.configured, false);
  assert.equal(status.ready, false);
  assert.ok(status.providers.every((p) => p.status === "missing_secret"));
  const result = await ask();
  assert.equal(result.status, 503);
  assert.equal((await result.json()).error, "no_provider_configured");
  assert.equal((await probe()).status, 503);
});

test("all registry credentials, not just three hard-coded variables, count as configured", async () => {
  for (const key of ["GOOGLE_API_KEY", "MISTRAL_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN"]) {
    process.env[key] = "contract-test-credential";
    const data = await (await GET()).json();
    assert.equal(data.configured, true, key);
    assert.equal(data.ready, false);
    delete process.env[key];
  }
});

test("secret presence alone is unchecked; actual completion earns ready; rotation invalidates it", async () => {
  process.env.GROQ_API_KEY = "contract-test-credential";
  assert.equal((await (await GET()).json()).providers.find((p) => p.id === "groq").status, "unchecked");
  globalThis.fetch = async () => Response.json({ choices: [{ message: { content: "OK" } }] });
  assert.equal((await ask({ providerId: "groq" })).status, 200);
  assert.equal((await (await GET()).json()).providers.find((p) => p.id === "groq").status, "ready");
  process.env.GROQ_API_KEY = "rotated-contract-credential";
  assert.equal((await (await GET()).json()).providers.find((p) => p.id === "groq").status, "unchecked");
});

test("authentication, quota, network and invalid JSON failures remain visible", async () => {
  process.env.GROQ_API_KEY = "contract-test-credential";
  for (const [http, expected] of [[401, "auth_failed"], [403, "auth_failed"], [429, "rate_limited"], [500, "upstream_error"]]) {
    globalThis.fetch = async () => new Response("sensitive upstream error", { status: http });
    const response = await ask({ providerId: "groq" });
    assert.equal(response.status, 502);
    const data = await response.json();
    assert.equal(data.error, expected);
    assert.equal(data.text, "");
    assert.equal(data.detail, undefined);
  }
  globalThis.fetch = async () => new Response("<html>not a model</html>");
  assert.equal((await (await ask({ providerId: "groq" })).json()).error, "invalid_response");
  globalThis.fetch = async () => { throw new Error("secret-containing network detail"); };
  assert.equal((await (await ask({ providerId: "groq" })).json()).error, "network_error");
});

test("server mount works, environment wins, and metadata never exposes the key", async () => {
  secretFile({ MISTRAL_API_KEY: "mounted-contract-credential" });
  assert.equal((await secretEnvironment()).MISTRAL_API_KEY, "mounted-contract-credential");
  process.env.MISTRAL_API_KEY = "environment-contract-credential";
  assert.equal((await secretEnvironment()).MISTRAL_API_KEY, "environment-contract-credential");
  const data = await (await GET()).json();
  assert.equal(data.configured, true);
  assert.ok(!JSON.stringify(data).includes("contract-credential"));
});

test("unsafe permissions, symlinks and malformed secret stores fail closed without parser excerpts", async () => {
  const file = secretFile({ GROQ_API_KEY: "contract-test-credential" }, 0o644);
  await assert.rejects(secretEnvironment(), /secret_store_unavailable_or_invalid/);
  fs.chmodSync(file, 0o600);
  fs.writeFileSync(file, '{"GROQ_API_KEY":"contract-test-credential" BROKEN');
  const data = await (await GET()).json();
  assert.equal(data.error, "secret_store_unavailable_or_invalid");
  assert.ok(!JSON.stringify(data).includes("contract-test"));
  const link = path.join(tmp, "link.json");
  fs.symlinkSync(file, link);
  process.env.NIO_SECRET_FILE = link;
  await assert.rejects(secretEnvironment(), /secret_store_unavailable_or_invalid/);
});

test("probe makes exactly one small request per configured/modelled provider, never GET /models", async () => {
  process.env.GROQ_API_KEY = "groq-contract";
  process.env.GOOGLE_API_KEY = "google-contract";
  process.env.HF_TOKEN = "hf-contract"; // model intentionally absent
  const calls = [];
  globalThis.fetch = async (url, init) => { calls.push({ url: String(url), body: JSON.parse(init.body), init }); return Response.json({ choices: [{ message: { content: "OK" } }] }); };
  assert.equal((await probe()).status, 200);
  await probe();
  assert.equal(calls.length, 2);
  assert.ok(calls.every((c) => c.body.max_tokens === 16 && c.init.redirect === "error" && !c.url.includes("/models")));
});

test("native Anthropic authentication and result format are handled server-side", async () => {
  process.env.ANTHROPIC_API_KEY = "anthropic-contract";
  process.env.ANTHROPIC_MODEL = "operator-selected-model";
  globalThis.fetch = async (url, init) => {
    assert.equal(init.headers["x-api-key"], "anthropic-contract");
    assert.equal(init.headers.authorization, undefined);
    const body = JSON.parse(init.body);
    assert.equal(body.model, "operator-selected-model");
    assert.ok(body.messages.every((m) => m.role !== "system"));
    return Response.json({ content: [{ type: "text", text: "OK anthropic-contract" }] });
  };
  const data = await (await ask({ providerId: "anthropic" })).json();
  assert.equal(data.ok, true);
  assert.equal(data.text, "OK [REDACTED]");
});

test("Apollo store leaves a real endpoint failure as ERROR/FAILED, never an assistant SIM", async () => {
  globalThis.fetch = async () => Response.json({ ok: false, error: "auth_failed" }, { status: 502 });
  useApolloStore.setState({ busy: false, entries: [] });
  await useApolloStore.getState().prompt("One cheap test");
  const state = useApolloStore.getState();
  assert.equal(state.busy, false);
  assert.equal(state.orbState, "ERROR");
  assert.equal(state.task.steps[0].status, "FAILED");
  assert.ok(state.entries.some((entry) => entry.level === "ERROR" && entry.message.includes("auth_failed")));
  assert.ok(!state.entries.some((entry) => entry.simulated || (entry.origin === "APOLLO" && entry.level === "CHAT")));
});
