"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const state = require("../telegram/state");

const msg = (id, ts = `2026-01-01T12:00:0${id}.000Z`, peer = 1) => ({ peer, msg_id: id, sender: "s", text: `m${id}`, ts, outgoing: false, is_bot: false });
const sug = (id, status = "pending") => ({ id, status, target_peer: 2, source_peer: 1, text: "t", origin: "rules" });

test("mergeMessages dedupes reload and SSE overlap, oldest first", () => {
  const merged = state.mergeMessages([msg(1), msg(2)], [msg(2), msg(3)]);
  assert.deepEqual(merged.map((m) => m.msg_id), [1, 2, 3]);
});

test("mergeMessages keeps the same id from different chats and caps", () => {
  assert.equal(state.mergeMessages([msg(1)], [msg(1, undefined, 2)]).length, 2);
  const many = Array.from({ length: state.MESSAGE_CAP + 5 }, (_, i) => msg(i, `2026-01-01T12:${String(i % 60).padStart(2, "0")}:00.000Z`));
  assert.equal(state.mergeMessages([], many).length, state.MESSAGE_CAP);
});

test("applyEvent upserts by id and ignores unknown events", () => {
  let data = state.emptyData();
  data = state.applyEvent(data, "suggestion", sug("a"));
  data = state.applyEvent(data, "suggestion", sug("b"));
  data = state.applyEvent(data, "suggestion", sug("a", "sent"));
  assert.deepEqual(data.suggestions.map((s) => [s.id, s.status]), [["b", "pending"], ["a", "sent"]]);
  assert.equal(state.applyEvent(data, "unknown", {}), data);
});

test("kanban_task event links the task to its signal", () => {
  let data = state.applyEvent(state.emptyData(), "signal", { id: "s1", kanban_task_id: null });
  data = state.applyEvent(data, "kanban_task", { signal_id: "s1", task_id: "t1" });
  assert.equal(data.signals[0].kanban_task_id, "t1");
});

test("open and sent lists split by status", () => {
  const rows = [sug("a"), sug("b", "failed"), sug("c", "sending"), sug("d", "sent"), sug("e", "dismissed")];
  assert.deepEqual(state.openSuggestions(rows).map((s) => s.id), ["a", "b", "c"]);
  assert.deepEqual(state.recentSent(rows).map((s) => s.id), ["d"]);
});

test("helpers: names, allowlist, quota", () => {
  assert.equal(state.peerName([{ id: 1, name: "Glint" }], 1), "Glint");
  assert.equal(state.peerName([], 7), "7");
  assert.equal(state.sendAllowed({ store: [2], env: [] }, 2), true);
  assert.equal(state.sendAllowed({ store: [], env: [3] }, 3), true);
  assert.equal(state.sendAllowed({ store: ["@bot"], env: [] }, 2), false);
  const status = { send_quota: [{ target: 2, used: 7, limit: 6 }] };
  assert.equal(state.quotaLeft(state.quotaFor(status, 2)), 0);
  assert.equal(state.quotaFor(status, 9), null);
  assert.equal(state.quotaFor(null, 2), null);
});

test("connectionView covers every failure mode", () => {
  assert.equal(state.connectionView(null, "not_running").tone, "off");
  assert.match(state.connectionView(null, "no_token").hint, /NIO_KANBAN_API_TOKEN/);
  assert.match(state.connectionView(null, "backend_down").hint, /kanban serve/);
  assert.equal(state.connectionView({ state: "authorized" }, null).tone, "ok");
  assert.match(state.connectionView({ state: "disconnected" }, null).hint, /telegram login/);
  assert.equal(state.connectionView({ state: "unconfigured" }, null).tone, "off");
});

test("formatWait and formatTime", () => {
  assert.equal(state.formatWait(30), "30 s");
  assert.equal(state.formatWait(300), "5 min");
  assert.equal(state.formatTime("kaputt"), "kaputt");
});
