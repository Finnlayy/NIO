"use strict";
/**
 * Cycle 2 — MCP console: subscription isolation, memoized log rows,
 * frame-coalesced bottom scroll.
 *
 * Verifies: a closed console performs zero log work per event; an open
 * console re-renders exactly one row per appended event (memo skip for
 * the rest); the scroll request coalesces per animation frame.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const {
  React,
  renderToStaticMarkup,
  mount,
  shallowEqual,
  useGridStore,
  resetStore,
  collectByType,
  hasText,
} = require("./helpers");
const { McpConsole, McpConsoleLog, ConsoleEventCount, LogRow } = require("../ops/McpConsole");
const { emitMcp } = require("../ops/store");
const { LogScroller } = require("../ops/consoleScroll");

test("LogRow is a memoized boundary", () => {
  assert.equal(LogRow.$$typeof, Symbol.for("react.memo"), "rows must be React.memo-wrapped");
});

test("closed console subscribes to nothing log-related", () => {
  resetStore();
  const m = mount();
  m.render(McpConsole);
  assert.ok(
    !m.lastSnapshots.includes(useGridStore.getState().mcpLog),
    "no mcpLog subscription while closed",
  );

  emitMcp("ui/update_widget_state", "test", { instanceId: "x", data: { a: 1 } });
  const tree = m.render(McpConsole);
  assert.ok(
    !m.lastSnapshots.includes(useGridStore.getState().mcpLog),
    "still no mcpLog subscription after an event lands while closed",
  );
  assert.ok(!hasText(tree, "MCP Event Bus"), "no console chrome while closed");
  resetStore();
});

test("open console renders one row per event, keyed and identity-stable", () => {
  resetStore();
  emitMcp("ui/hydrate_widget_template", "master-twin", { templateKey: "quantum-envelope-chart" });
  emitMcp("ui/hydrate_widget_template", "master-twin", { templateKey: "orderflow-cvd-heatmap" });
  emitMcp("ui/remove_widget", "ui-canvas", { instanceId: "ghost" });
  const log = useGridStore.getState().mcpLog;
  useGridStore.getState().setConsoleOpen(true);

  const m = mount();
  const tree = m.render(McpConsole);
  assert.ok(hasText(tree, "MCP Event Bus"), "console chrome present");
  // Rows live one level down (McpConsoleLog body) — render that subtree.
  const rows = collectByType(m.render(McpConsoleLog), LogRow);
  assert.equal(rows.length, 3);
  // React coerces numeric keys to strings.
  assert.deepEqual(rows.map((r) => r.key), log.map((e) => String(e.id)));
  rows.forEach((row, i) => assert.equal(row.props.event, log[i], "row gets the immutable event object"));

  const countEl = mount().render(ConsoleEventCount);
  const countChildren = Array.isArray(countEl.props.children) ? countEl.props.children : [countEl.props.children];
  assert.ok(countChildren.some((c) => c === 3), "event count shows 3");
  resetStore();
});

test("appending one event churns exactly one row", () => {
  resetStore();
  for (let i = 0; i < 3; i++) emitMcp("ui/update_widget_state", "test", { i });
  const m = mount();
  const before = collectByType(m.render(McpConsoleLog), LogRow);
  assert.equal(before.length, 3);

  emitMcp("ui/update_widget_state", "test", { i: 99 });
  const after = collectByType(m.render(McpConsoleLog), LogRow);
  assert.equal(after.length, 4, "new row appended");

  const changed = [];
  for (let i = 0; i < before.length; i++) {
    if (!shallowEqual(before[i].props, after[i].props)) changed.push(i);
  }
  assert.deepEqual(changed, [], "existing rows keep identical props (memo skip)");
  const last = useGridStore.getState().mcpLog.at(-1);
  assert.equal(after[after.length - 1].props.event, last, "new row carries the new event");
  resetStore();
});

test("log row renders timestamp, source, method and params JSON with tone class", () => {
  resetStore();
  emitMcp("ui/hydrate_widget_template", "master-twin", { templateKey: "vault-earn-arbitrage", span: 6 });
  const event = useGridStore.getState().mcpLog.at(-1);
  const html = renderToStaticMarkup(React.createElement(LogRow, { event }));
  assert.ok(html.includes(event.timestamp), "timestamp");
  assert.ok(html.includes("master-twin"), "source");
  assert.ok(html.includes("ui/hydrate_widget_template"), "method");
  // React escapes quotes in text nodes.
  assert.ok(html.includes("&quot;templateKey&quot;:&quot;vault-earn-arbitrage&quot;"), "params JSON");
  assert.ok(html.includes("text-cyan-300"), "hydrate tone");
  resetStore();
});

test("LogScroller coalesces same-frame requests into one scroll", () => {
  const queue = [];
  const scroller = new LogScroller((cb) => queue.push(cb));
  const el = {
    calls: 0,
    opts: null,
    scrollIntoView(opts) {
      this.calls++;
      this.opts = opts;
    },
  };

  scroller.request(el);
  scroller.request(el); // burst: two events in one frame
  assert.equal(queue.length, 1, "second same-frame request is collapsed");
  queue.shift()(); // animation frame fires
  assert.equal(el.calls, 1, "exactly one scroll per frame");
  assert.deepEqual(el.opts, { behavior: "smooth", block: "end" });

  scroller.request(el); // next frame — a new scroll is scheduled
  assert.equal(queue.length, 1);
  queue.shift()();
  assert.equal(el.calls, 2);
  assert.equal(queue.length, 0, "no stray scheduled frames");
});
