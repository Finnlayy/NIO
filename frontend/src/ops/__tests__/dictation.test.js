"use strict";
/**
 * Speech input of the Apollo terminal: pure helpers, the client error mapping
 * and the fail-closed contract of /api/apollo/transcribe.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const {
  appendTranscript,
  joinDictation,
  microphoneError,
  pickRecorderMime,
  probeEngine,
  speechStatus,
  transcribeAudio,
} = require("../apollo/dictation");
const { GET, POST } = require("../app/api/apollo/transcribe/route");
const { useApolloStore } = require("../apollo/store");

const realFetch = globalThis.fetch;
test.afterEach(() => {
  globalThis.fetch = realFetch;
  delete process.env.STT_ENDPOINT_URL;
});

function audioRequest(extra = {}) {
  const body = new FormData();
  body.set("file", new Blob(["audio"], { type: "audio/webm" }), "dictation");
  for (const [key, value] of Object.entries(extra)) body.set(key, value);
  return new Request("http://localhost/api/apollo/transcribe", { method: "POST", body });
}

test("transcripts join the draft with exactly one space", () => {
  assert.equal(appendTranscript("", " hallo "), "hallo");
  assert.equal(appendTranscript("/spawn", "inference"), "/spawn inference");
  assert.equal(appendTranscript("/spawn ", "inference"), "/spawn inference");
  assert.equal(appendTranscript("/spawn", "   "), "/spawn");
});

test("recorder takes the first format the browser supports", () => {
  assert.equal(pickRecorderMime((mime) => mime === "audio/mp4"), "audio/mp4");
  assert.equal(pickRecorderMime(() => true), "audio/webm;codecs=opus");
  assert.equal(pickRecorderMime(() => false), undefined);
});

test("microphone failures read as their cause", () => {
  const named = (name) => Object.assign(new Error("x"), { name });
  assert.match(microphoneError(named("NotAllowedError")), /blocked/);
  assert.match(microphoneError(named("NotFoundError")), /no microphone/);
  assert.match(microphoneError("anything"), /failed/);
});

test("a stopped engine reaches the operator as such", async () => {
  globalThis.fetch = async () => Response.json({ ok: false, error: "stt_unavailable" }, { status: 503 });
  await assert.rejects(transcribeAudio(new Blob(["a"])), /speech engine is not running/);
});

test("route forwards audio to the server-side endpoint only", async () => {
  process.env.STT_ENDPOINT_URL = "http://stt.test/v1/audio/transcriptions";
  let called;
  globalThis.fetch = async (url, init) => {
    called = { url, body: init.body };
    return Response.json({ text: "  Apollo, Status  " });
  };
  const response = await POST(audioRequest({ endpointUrl: "http://evil.test/" }));
  const result = await response.json();
  assert.equal(called.url, "http://stt.test/v1/audio/transcriptions");
  assert.equal(called.body.get("language"), "de");
  assert.match(called.body.get("prompt"), /Apollo/);
  assert.equal(called.body.get("endpointUrl"), null);
  assert.deepEqual([result.ok, result.text], [true, "Apollo, Status"]);
});

test("route rejects a request without audio", async () => {
  const response = await POST(new Request("http://localhost/x", { method: "POST", body: new FormData() }));
  assert.equal(response.status, 400);
});

test("route rejects oversized audio before the engine sees it", async () => {
  globalThis.fetch = async () => assert.fail("engine must not be called");
  const headers = { "content-length": String(20_000_000) };
  const response = await POST(new Request("http://localhost/x", { method: "POST", headers, body: "x" }));
  assert.equal(response.status, 413);
});

test("route never invents a transcript when the engine fails", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("fetch failed");
  };
  assert.equal((await POST(audioRequest())).status, 503);

  globalThis.fetch = async () => new Response("<html>", { status: 200 });
  const notStt = await POST(audioRequest());
  assert.equal(notStt.status, 502);
  assert.equal((await notStt.json()).text, undefined);

  globalThis.fetch = async () => new Response("boom", { status: 500 });
  assert.equal((await POST(audioRequest())).status, 502);
});

test("a dictation never produces an approval", () => {
  assert.equal(joinDictation("", "/approve 42"), null);
  assert.equal(joinDictation("", "Slash Deny 42"), null);
  assert.equal(joinDictation("/approve", "42"), null);
  assert.equal(joinDictation("", "approve the plan"), null);
  assert.equal(joinDictation("bitte", "den Plan prüfen"), "bitte den Plan prüfen");
});

test("status follows recorder first, then engine health", () => {
  assert.equal(speechStatus("recording", "offline"), "listening");
  assert.equal(speechStatus("transcribing", "ready"), "transcribing");
  assert.equal(speechStatus("idle", "offline"), "offline");
  assert.equal(speechStatus("idle", "ready"), "idle");
  assert.equal(speechStatus("idle", "unknown"), "idle");
});

test("probe reports a stopped engine as offline", async () => {
  globalThis.fetch = async () => Response.json({ ok: false }, { status: 503 });
  assert.equal(await probeEngine(), "offline");
  globalThis.fetch = async () => Response.json({ ok: true });
  assert.equal(await probeEngine(), "ready");
});

test("route probes only the health path of the configured engine", async () => {
  process.env.STT_ENDPOINT_URL = "http://stt.test/v1/audio/transcriptions";
  let url;
  globalThis.fetch = async (target) => {
    url = String(target);
    return new Response("OK");
  };
  assert.equal((await GET()).status, 200);
  assert.equal(url, "http://stt.test/health");

  globalThis.fetch = async () => {
    throw new TypeError("fetch failed");
  };
  assert.equal((await GET()).status, 503);
});

test("orb listens only while idle and hands back afterwards", () => {
  const store = useApolloStore;
  store.setState({ orbState: "IDLE", speech: "idle" });
  store.getState().setSpeech("listening");
  assert.equal(store.getState().orbState, "LISTENING");
  store.getState().setSpeech("transcribing");
  assert.equal(store.getState().orbState, "IDLE");

  store.setState({ orbState: "THINKING" });
  store.getState().setSpeech("listening");
  assert.equal(store.getState().orbState, "THINKING");
  store.getState().setSpeech("offline");
  assert.equal(store.getState().orbState, "THINKING");
  assert.equal(store.getState().speech, "offline");
  store.setState({ orbState: "IDLE", speech: "idle" });
});
