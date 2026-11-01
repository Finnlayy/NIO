"use strict";
/**
 * Regression cover for the UI test run of 2026-10-30: shared telemetry stream,
 * saved layouts, gallery cap, saved Apollo settings and dispatch by short id.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { subscribeEngineFeed } = require("../ops/hooks/useMarketData");
const { parseLayout, serializeLayout } = require("../ops/layout");
const {
  MAX_PER_TEMPLATE,
  dispatchHydrateTemplate,
  restoreWidgets,
  useGridStore,
} = require("../ops/store");
const { parseApollo, serializeApollo } = require("../apollo/persistence");
const { DEFAULT_CONFIG, useApolloStore } = require("../apollo/store");

class FakeEventSource {
  static opened = [];
  constructor(url) {
    this.url = url;
    this.closed = false;
    FakeEventSource.opened.push(this);
  }
  addEventListener() {}
  close() {
    this.closed = true;
  }
}

test("all widgets share one stream, closed with the last subscriber", () => {
  FakeEventSource.opened = [];
  globalThis.EventSource = FakeEventSource;
  const leave = Array.from({ length: 8 }, () => subscribeEngineFeed("/stream", 3000, Infinity, () => {}));
  assert.equal(FakeEventSource.opened.length, 1);
  leave.slice(1).forEach((unsubscribe) => unsubscribe());
  assert.equal(FakeEventSource.opened[0].closed, false);
  leave[0]();
  assert.equal(FakeEventSource.opened[0].closed, true);
  delete globalThis.EventSource;
});

test("gallery stops adding copies at the limit", () => {
  useGridStore.setState({ widgets: [] });
  for (let i = 0; i < MAX_PER_TEMPLATE + 2; i++) dispatchHydrateTemplate("TPL_02");
  assert.equal(useGridStore.getState().widgets.length, MAX_PER_TEMPLATE);
  useGridStore.setState({ widgets: [] });
});

test("layout round trip keeps the arrangement and rebuilds data", () => {
  useGridStore.setState({ widgets: [] });
  dispatchHydrateTemplate("TPL_07");
  const [widget] = useGridStore.getState().widgets;
  useGridStore.getState().setTaken(widget.id, "2026-10-30T12:00:00.000Z");
  useGridStore.getState().cycleHeight(widget.id);
  const saved = parseLayout(serializeLayout(useGridStore.getState().widgets));
  restoreWidgets(saved);
  const [restored] = useGridStore.getState().widgets;
  assert.equal(restored.templateId, "TPL_07");
  assert.equal(restored.takenAt, "2026-10-30T12:00:00.000Z");
  assert.equal(restored.height, widget.height === "tall" ? "compact" : "tall");
  assert.ok(Object.keys(restored.data).length > 0);
  useGridStore.setState({ widgets: [] });
});

test("broken or stale saved layouts never reach the canvas", () => {
  assert.equal(parseLayout(null), null);
  assert.equal(parseLayout("{not json"), null);
  assert.equal(parseLayout('{"a":1}'), null);
  assert.deepEqual(parseLayout('[{"templateId":"TPL_99","title":"x"},null]'), []);
});

test("saved Apollo settings survive, malformed fields fall back", () => {
  const config = structuredClone(DEFAULT_CONFIG);
  config.primaryModel = "Ollama / GGUF";
  config.temperature = 1.1;
  config.freeLLMRouting.providers[0].status = "STANDBY";
  const node = { id: "node-x", label: "X", category: "MEMORY", position: { x: 0, y: 0 }, state: "STREAMING" };
  const raw = serializeApollo(config, [node], new Set());
  assert.ok(!raw.includes("fallbackChain"));
  const saved = parseApollo(raw, DEFAULT_CONFIG);
  assert.equal(saved.config.primaryModel, "Ollama / GGUF");
  assert.equal(saved.config.freeLLMRouting.providers[0].status, "STANDBY");
  assert.equal(saved.config.freeLLMRouting.fallbackChain.length, DEFAULT_CONFIG.freeLLMRouting.fallbackChain.length);
  assert.equal(saved.nodes[0].state, "IDLE");

  const broken = parseApollo('{"config":{"temperature":"hot","freeLLMRouting":5},"nodes":[{"id":"n","category":"NOPE"}]}', DEFAULT_CONFIG);
  assert.equal(broken.config.temperature, DEFAULT_CONFIG.temperature);
  assert.deepEqual(broken.config.freeLLMRouting.weights, DEFAULT_CONFIG.freeLLMRouting.weights);
  assert.deepEqual(broken.nodes, []);
  assert.equal(parseApollo("nope", DEFAULT_CONFIG), null);
});

test("dispatch accepts the chip's short id and lists valid ids otherwise", () => {
  assert.equal(useApolloStore.getState().dispatch("router", {}), true);
  assert.equal(useApolloStore.getState().dispatch("nope", {}), false);
  const last = useApolloStore.getState().entries.at(-1);
  assert.match(last.detail, /node-router/);
});

test("reset returns to shipped settings even with mutation revoked", () => {
  useApolloStore.setState((s) => ({ config: { ...s.config, allowAppMutation: false, primaryModel: "Custom ONNX" } }));
  useApolloStore.getState().resetConfig();
  const state = useApolloStore.getState();
  assert.equal(state.config.allowAppMutation, true);
  assert.equal(state.config.primaryModel, DEFAULT_CONFIG.primaryModel);
  assert.equal(state.router.primaryModel, DEFAULT_CONFIG.primaryModel);
});
