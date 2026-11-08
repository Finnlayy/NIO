"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const { browserRecognition, recognitionError, startBrowserDictation } = require("../apollo/browserSpeech");
const { joinDictation } = require("../apollo/dictation");

function fixture() {
  let instance;
  class Recognition {
    constructor() { instance = this; }
    start() { this.started = true; }
    stop() { this.stopped = true; this.onend(); }
    abort() { this.aborted = true; this.onend(); }
  }
  const texts = [], errors = [];
  let ended = 0;
  const session = startBrowserDictation(Recognition, "de-DE", {
    onText: (text) => texts.push(text),
    onError: (error) => errors.push(error),
    onEnd: () => ended++,
  });
  return { instance, texts, errors, session, ended: () => ended };
}
const result = (text, isFinal = true) => ({ isFinal, 0: { transcript: text } });

test("browser recognition is SSR-safe", () => {
  assert.equal(browserRecognition(), undefined);
});

test("browser speech is bounded and returns final text only on end", () => {
  const f = fixture();
  assert.equal(f.instance.started, true);
  assert.equal(f.instance.lang, "de-DE");
  assert.equal(f.instance.continuous, false);
  assert.equal(f.instance.interimResults, false);
  f.instance.onresult({ resultIndex: 0, results: [result("draft", false)] });
  assert.deepEqual(f.texts, []);
  f.instance.onresult({ resultIndex: 0, results: [result(" Apollo ")] });
  f.instance.onresult({ resultIndex: 1, results: [result("Apollo"), result("Status")] });
  f.session.stop();
  assert.deepEqual(f.texts, ["Apollo Status"]);
  assert.equal(f.ended(), 1);
});

test("duplicate recognition results are not appended twice", () => {
  const f = fixture();
  const event = { resultIndex: 0, results: [result("hello")] };
  f.instance.onresult(event);
  f.instance.onresult(event);
  f.session.stop();
  f.instance.onend();
  assert.deepEqual(f.texts, ["hello"]);
  assert.equal(f.ended(), 1);
});

test("closing or cancelling dictation discards late browser results", () => {
  const f = fixture();
  f.instance.onresult({ resultIndex: 0, results: [result("do not send")] });
  f.session.cancel();
  f.instance.onresult({ resultIndex: 0, results: [result("late")] });
  f.instance.onend();
  assert.equal(f.instance.aborted, true);
  assert.deepEqual(f.texts, []);
  assert.deepEqual(f.errors, []);
  assert.equal(f.ended(), 0);
});

test("recognition errors never yield a partial transcript", () => {
  const f = fixture();
  f.instance.onresult({ resultIndex: 0, results: [result("partial")] });
  f.instance.onerror({ error: "network" });
  f.session.stop();
  assert.deepEqual(f.texts, []);
  assert.match(f.errors[0], /could not connect/);
  assert.equal(f.ended(), 1);
});

test("silent recognition is actionable, not an invented command", () => {
  const f = fixture();
  f.session.stop();
  assert.deepEqual(f.texts, []);
  assert.match(f.errors[0], /No speech recognized/);
});

test("browser microphone failures explain permissions and iframe workaround", () => {
  assert.match(recognitionError("not-allowed"), /new tab.*microphone access/);
  assert.match(recognitionError("audio-capture"), /No microphone/);
  assert.match(recognitionError("unknown"), /type your command/);
});

test("browser transcripts retain the typed-only approval boundary", () => {
  const f = fixture();
  f.instance.onresult({ resultIndex: 0, results: [result("slash approve 42")] });
  f.session.stop();
  assert.equal(joinDictation("", f.texts[0]), null);
});

test("browser session stops at its time limit", async () => {
  let instance;
  let ended = false;
  class Recognition {
    constructor() { instance = this; }
    start() {}
    stop() { this.onend(); }
    abort() {}
  }
  startBrowserDictation(Recognition, "en-US", {
    onText() { assert.fail("no transcript expected"); },
    onError() {}, onEnd() { ended = true; },
  }, 5);
  await new Promise((resolve) => setTimeout(resolve, 25));
  assert.equal(ended, true);
  assert.equal(instance.lang, "en-US");
});
