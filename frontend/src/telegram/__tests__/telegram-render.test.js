"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const P = require("../telegram/Panels");
const { emptyData } = require("../telegram/state");

const noop = () => {};
const actions = { setMonitored: noop, setAllowed: noop, setPairing: noop, approve: noop, dismiss: noop, retry: noop, decide: noop, gather: noop, ask: async () => null, clearError: noop };
const FEED = -100;
const BOT = 20;

const status = {
  state: "authorized",
  me: { id: 1, name: "Finn", username: "finn" },
  flood_wait_until: null,
  gather: { running: true, last_tick: null, interval_s: 300 },
  symbols: { count: 4, source: "live", loaded_at: null, quotes_count: 2 },
  llm_configured: false,
  kanban_enabled: true,
  send_rate_per_hour: 6,
  send_quota: [{ target: BOT, used: 2, limit: 6 }],
};

function data(over = {}) {
  return {
    ...emptyData(),
    status,
    dialogs: [
      { id: FEED, name: "Glint", kind: "channel", is_bot: false, unread: 0 },
      { id: BOT, name: "Glint Bot", kind: "user", is_bot: true, unread: 0 },
    ],
    monitored: [FEED],
    pairings: [{ source: FEED, target: BOT }],
    allowlist: { store: [BOT], env: [] },
    ...over,
  };
}

const suggestion = (over = {}) => ({ id: "s", source_peer: FEED, target_peer: BOT, text: "/glint BTC BULLISH 10.0", based_on_msg_id: 1, origin: "rules", status: "pending", created_at: "", decided_at: null, error: null, ...over });
const card = (s, d = data(), busy = false) =>
  renderToStaticMarkup(React.createElement("ul", null, React.createElement(P.SuggestionCard, { suggestion: s, data: d, busy, actions })));

test("suggestion names the target and remaining quota on the button", () => {
  const html = card(suggestion());
  assert.match(html, /An Glint Bot senden/);
  assert.match(html, /noch 4 von 6 pro Stunde/);
  assert.match(html, /Regel/);
});

test("LLM text carries a warning", () => {
  assert.match(card(suggestion({ origin: "llm" })), /vor dem Senden prüfen/);
  assert.doesNotMatch(card(suggestion()), /vor dem Senden prüfen/);
});

test("send is disabled without allowance or quota, and while busy", () => {
  const button = (html) => html.match(/<button[^>]*>(?:(?!<\/button>).)*senden/)[0];
  assert.match(button(card(suggestion(), data({ allowlist: { store: [], env: [] } }))), / disabled=""/);
  const full = { ...status, send_quota: [{ target: BOT, used: 6, limit: 6 }] };
  assert.match(button(card(suggestion(), data({ status: full }))), / disabled=""/);
  assert.match(button(card(suggestion(), data(), true)), / disabled=""/);
  assert.doesNotMatch(button(card(suggestion())), / disabled=""/);
});

test("states: failed offers reopen, sending offers nothing", () => {
  const failed = card(suggestion({ status: "failed", error: "Zustellung unklar" }));
  assert.match(failed, /Zustellung unklar/);
  assert.match(failed, /Wieder öffnen/);
  assert.doesNotMatch(failed, /senden<\/button>/);
  const sending = card(suggestion({ status: "sending" }));
  assert.match(sending, /Wird gesendet/);
  assert.doesNotMatch(sending, /<button/);
});

test("feed text is escaped, never rendered as markup", () => {
  const html = card(suggestion({ text: '<img src=x onerror="alert(1)">' }));
  assert.doesNotMatch(html, /<img/);
  const feed = renderToStaticMarkup(
    React.createElement(P.FeedPanel, { messages: [{ peer: FEED, msg_id: 1, sender: "<b>x</b>", text: "<script>1</script>", ts: "2026-01-01T12:00:00.000Z", outgoing: false, is_bot: false }], dialogs: [], monitored: [] }),
  );
  assert.doesNotMatch(feed, /<script>|<b>x/);
  assert.match(feed, /role="log"/);
});

test("chat row: toggles expose state, pairing warns on a blocked target", () => {
  const row = (d) => renderToStaticMarkup(React.createElement("ul", null, React.createElement(P.ChatRow, { dialog: d.dialogs[0], data: d, busy: new Set(), actions })));
  const html = row(data());
  assert.match(html, /aria-label="Glint mitlesen"/);
  assert.match(html, /aria-pressed="true"/);
  assert.match(html, /Vorschläge an/);
  assert.match(row(data({ allowlist: { store: [], env: [] } })), /keine Sendeerlaubnis/);
  assert.doesNotMatch(row(data({ monitored: [] })), /Vorschläge an/);
});

test("env allowlist entries cannot be toggled off", () => {
  const d = data({ allowlist: { store: [], env: [BOT] } });
  const dialog = d.dialogs[1];
  const html = renderToStaticMarkup(React.createElement("ul", null, React.createElement(P.ChatRow, { dialog, data: d, busy: new Set(), actions })));
  assert.match(html, /aria-label="Senden an Glint Bot erlauben"[^>]* disabled=""|disabled=""[^>]*aria-label="Senden an Glint Bot erlauben"/);
});

test("setup hint explains CLI login and hides when connected", () => {
  const hint = (s, code) => renderToStaticMarkup(React.createElement(P.SetupHint, { status: s, errorCode: code }));
  assert.equal(hint(status, null), "");
  assert.match(hint(null, "not_running"), /telegram login/);
  assert.match(hint({ ...status, state: "disconnected" }, null), /Login nur per CLI/);
});

test("status bar shows flood wait", () => {
  const html = renderToStaticMarkup(React.createElement(P.StatusBar, { status: { ...status, flood_wait_until: "2026-01-01T12:00:00.000Z" }, errorCode: null, live: true }));
  assert.match(html, /Telegram bremst/);
  assert.match(html, /role="status"/);
});

test("signals show the created Kanban task", () => {
  const html = renderToStaticMarkup(
    React.createElement(P.SignalsPanel, { signals: [{ id: "x", symbol: "BTC", direction: "bullish", strength: 8, peer: FEED, msg_id: 1, evidence: "e", created_at: "2026-01-01T12:00:00.000Z", kanban_task_id: "task-1" }], dialogs: [] }),
  );
  assert.match(html, /Task task-1/);
  assert.match(html, /Bullish/);
});

test("approvals offer both decisions; error banner is an alert", () => {
  const html = renderToStaticMarkup(React.createElement(P.ApprovalsPanel, { approvals: [{ id: "a", title: "Deploy?", detail: "", status: "pending" }], busy: new Set(), actions }));
  assert.match(html, /Freigeben/);
  assert.match(html, /Ablehnen/);
  assert.equal(renderToStaticMarkup(React.createElement(P.ErrorBanner, { message: null, onClose: noop })), "");
  assert.match(renderToStaticMarkup(React.createElement(P.ErrorBanner, { message: "x", onClose: noop })), /role="alert"/);
});
