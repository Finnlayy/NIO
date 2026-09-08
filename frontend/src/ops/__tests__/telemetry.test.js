"use strict";
/**
 * P1 — engine telemetry over the UDS event bus.
 *
 * The wire contract, the fail-closed state machine and the widget mapping are
 * pure functions precisely so they can be asserted here without a socket, a
 * browser or a clock. The last test drives the real CvdHeatmap component
 * through the hook to prove the fail-closed default is what actually renders.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { mount, renderToStaticMarkup, widgetTemplates } = require("./helpers");
const {
  STALE_AFTER_MS,
  EMPTY_TELEMETRY,
  backoffDelayMs,
  nextFeedConnection,
  nextTelemetry,
  parseTelemetryRecord,
} = require("../ops/hooks/useMarketData");
const { cvdFromTelemetry, CvdHeatmap } = require("../ops/widgets/CvdHeatmap");

const MICRO = { imbalance_ratio: 0.24, depth_2pct: 0.61, footprint_delta: [0.1, -0.2, 0.3] };
const GRAVITY = { l2_depth: 0.61, l3_iceberg: 0.18, polymarket_prob: 0.5, v_total: 0.4155 };
const REGIME = { cluster_id: 0, confidence: 0.24, is_forbidden_zone: 0 };

function record(kind, payload, symbol = "BTCUSDT") {
  return { kind, symbol, clock_s: 1.5, payload };
}

test("wire contract: three valid payloads are accepted", () => {
  assert.ok(parseTelemetryRecord(record("microstructure_tick", MICRO)));
  assert.ok(parseTelemetryRecord(record("gravity_tick", GRAVITY)));
  assert.ok(parseTelemetryRecord(record("regime_tick", REGIME)));
});

test("wire contract: a missing field is rejected, not defaulted", () => {
  const { v_total, ...partial } = GRAVITY;
  assert.equal(parseTelemetryRecord(record("gravity_tick", partial)), null);
  const { footprint_delta, ...noVector } = MICRO;
  assert.equal(parseTelemetryRecord(record("microstructure_tick", noVector)), null);
});

test("wire contract: NaN, Infinity, strings and booleans are rejected", () => {
  for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, "0.5", true, null]) {
    assert.equal(
      parseTelemetryRecord(record("gravity_tick", { ...GRAVITY, v_total: bad })),
      null,
      `v_total=${String(bad)} must not pass`,
    );
  }
  assert.equal(
    parseTelemetryRecord(record("microstructure_tick", { ...MICRO, footprint_delta: [] })),
    null,
    "an empty vector carries no information",
  );
  assert.equal(
    parseTelemetryRecord(record("microstructure_tick", { ...MICRO, footprint_delta: [0.1, "x"] })),
    null,
  );
});

test("wire contract: unknown kinds and non-objects are rejected", () => {
  assert.equal(parseTelemetryRecord({ kind: "execution_complete", payload: GRAVITY }), null);
  assert.equal(parseTelemetryRecord(null), null);
  assert.equal(parseTelemetryRecord("nope"), null);
  assert.equal(parseTelemetryRecord({ kind: "gravity_tick" }), null, "missing payload");
});

test("fold keeps the other kinds and stamps the arrival time", () => {
  let snap = EMPTY_TELEMETRY;
  assert.equal(snap.receivedAt, 0);
  snap = nextTelemetry(snap, record("gravity_tick", GRAVITY), 1000);
  assert.deepEqual(snap.gravity, GRAVITY);
  assert.equal(snap.microstructure, null);
  assert.equal(snap.receivedAt, 1000);
  snap = nextTelemetry(snap, record("microstructure_tick", MICRO), 2000);
  assert.deepEqual(snap.gravity, GRAVITY, "an earlier kind must survive a later one");
  assert.deepEqual(snap.microstructure, MICRO);
  assert.equal(snap.receivedAt, 2000);
  snap = nextTelemetry(snap, record("regime_tick", REGIME), 3000);
  assert.deepEqual(snap.regime, REGIME);
});

test("state machine: no transport means DISCONNECTED, whatever arrived before", () => {
  const at = Date.now();
  assert.equal(nextFeedConnection("CONNECTED_LIVE", { transportOpen: false, lastTickAt: at }, at), "DISCONNECTED");
});

test("state machine: a tick inside the window is CONNECTED_LIVE", () => {
  const at = 10_000;
  assert.equal(
    nextFeedConnection("DISCONNECTED", { transportOpen: true, lastTickAt: at - 100 }, at),
    "CONNECTED_LIVE",
  );
});

test("state machine: silence beyond 3000 ms degrades to STALE_CACHE_DEGRADED", () => {
  assert.equal(STALE_AFTER_MS, 3000, "must match the brief and the server-side STALE_AFTER_MS");
  const last = 10_000;
  assert.equal(
    nextFeedConnection("CONNECTED_LIVE", { transportOpen: true, lastTickAt: last }, last + STALE_AFTER_MS),
    "CONNECTED_LIVE",
    "exactly at the boundary is still live",
  );
  assert.equal(
    nextFeedConnection("CONNECTED_LIVE", { transportOpen: true, lastTickAt: last }, last + STALE_AFTER_MS + 1),
    "STALE_CACHE_DEGRADED",
  );
});

test("state machine: an open transport with no tick yet keeps its state", () => {
  // `hello` and `ping` are transport signals; only a real tick may go live.
  assert.equal(nextFeedConnection("DISCONNECTED", { transportOpen: true, lastTickAt: 0 }, 5000), "DISCONNECTED");
});

test("state machine: the stale window is configurable", () => {
  const last = 10_000;
  assert.equal(
    nextFeedConnection("CONNECTED_LIVE", { transportOpen: true, lastTickAt: last }, last + 1500, 1000),
    "STALE_CACHE_DEGRADED",
  );
});

test("backoff doubles and is capped, never negative", () => {
  assert.equal(backoffDelayMs(0), 1000);
  assert.equal(backoffDelayMs(1), 2000);
  assert.equal(backoffDelayMs(2), 4000);
  assert.equal(backoffDelayMs(5), 30_000);
  assert.equal(backoffDelayMs(50), 30_000, "capped");
  assert.equal(backoffDelayMs(-3), 1000, "negative attempts clamp to the first step");
});

test("cvd mapping: engine footprint becomes the grid, pressure comes from sign counts", () => {
  const out = cvdFromTelemetry(MICRO, ["08", "10", "12"]);
  assert.equal(out.bins.length, 3);
  assert.deepEqual(out.bins[1], { delta: -0.2, label: "10" });
  assert.equal(out.buyPct, 67, "two of three bins are positive");
  assert.equal(out.sellPct, 33);
  assert.equal(out.imbalanceRatio, MICRO.imbalance_ratio);
  assert.equal(out.depthPct, MICRO.depth_2pct);
});

test("cvd mapping: labels fall back to zero-padded indexes", () => {
  const out = cvdFromTelemetry(MICRO);
  assert.deepEqual(out.bins.map((b) => b.label), ["00", "01", "02"]);
});

test("CvdHeatmap fails closed: without a live tick it shows the template and says so", () => {
  const template = widgetTemplates.find((t) => t.id === "TPL_06");
  assert.equal(template.key, "orderflow-cvd-heatmap");
  // Through the hook, not bare SSR: the widget subscribes to the bus, so the
  // fail-closed default is a property of the mounted component.
  const m = mount();
  const html = renderToStaticMarkup(m.render(() => CvdHeatmap({ data: template.dataFactory() })));
  assert.match(html, /data-feed-state="DISCONNECTED"/);
  assert.match(html, /Disconnected/);
  assert.match(html, /nicht der Markt/, "must not present the mock as market data");
});

test("CvdHeatmap renders every engine bin when mounted through the hook", () => {
  const template = widgetTemplates.find((t) => t.id === "TPL_06");
  const m = mount();
  const element = m.render(() => CvdHeatmap({ data: template.dataFactory() }));
  const html = renderToStaticMarkup(element);
  // 12 template bins ⇒ 12 cells; the badge must be present exactly once.
  assert.equal((html.match(/data-feed-state=/g) || []).length, 1);
  assert.equal((html.match(/CVD /g) || []).length, 12);
  assert.match(html, /transition-colors/);
  assert.doesNotMatch(html, /transition-all/);
});
