"use strict";
/**
 * The HUD names who really answered. Only the display moves: the router, and
 * so the model the next request asks for, keeps its catalog choice.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { useApolloStore, selectActiveModel, selectFailoverModel, selectShownModel } = require("../apollo/store");

const store = useApolloStore;
const realFetch = globalThis.fetch;
const clean = store.getState();

test.afterEach(() => {
  globalThis.fetch = realFetch;
  store.setState({ config: clean.config, router: clean.router, answered: null, busy: false });
});

function withEndpoint(url) {
  const config = store.getState().config;
  store.setState({
    config: { ...config, freeLLMRouting: { ...config.freeLLMRouting, endpointUrl: url } },
  });
}

async function turn(prompt) {
  await store.getState().prompt(prompt);
  while (store.getState().busy) await new Promise((resolve) => setTimeout(resolve, 25));
}

const catalogName = () => selectActiveModel(store.getState()).name;

/** Fake Kanban proxy: one board, one chat task that finishes as `finished`. */
function kanban(finished) {
  return async (url, init) => {
    if (url !== "/api/apollo/kanban") return realFetch(url, init);
    const { path, method } = JSON.parse(init.body);
    if (path === "/api/v1/kanban/boards") return Response.json(method === "GET" ? [] : { id: "b1" });
    if (method === "POST") return Response.json({ id: "t1", board_id: "b1", status: "pending" });
    return Response.json([{ id: "t1", board_id: "b1", ...finished }]);
  };
}

test("a live answer puts the reported model in the HUD, not in the router", async () => {
  withEndpoint("http://localhost:9/v1");
  globalThis.fetch = kanban({
    status: "completed",
    result_payload: { text: "antwort", model: "gemma-live", provider: "pool.local" },
  });
  const routed = catalogName();
  await turn("hallo");
  const shown = selectShownModel(store.getState());
  assert.equal(shown.name, "gemma-live");
  assert.equal(shown.provider, "pool.local");
  assert.equal(catalogName(), routed);
});

test("the shown model is stable between store updates", () => {
  store.setState({ answered: { id: "answered", name: "x", provider: "", failoverCount: 0 } });
  withEndpoint("http://localhost:9/v1");
  assert.equal(selectShownModel(store.getState()), selectShownModel(store.getState()));
});

test("before any answer the catalog name stands", () => {
  store.setState({ answered: null });
  assert.equal(selectShownModel(store.getState()).name, catalogName());
});

test("an answer without a reported model names nothing it does not know", async () => {
  withEndpoint("http://localhost:9/v1");
  store.setState({ answered: { id: "answered", name: "old", provider: "", failoverCount: 0 } });
  globalThis.fetch = kanban({ status: "completed", result_payload: { text: "antwort" } });
  await turn("hallo");
  assert.equal(store.getState().answered, null);
  assert.equal(selectShownModel(store.getState()).name, catalogName());
});

test("a failed live turn clears the last live model", async () => {
  withEndpoint("http://localhost:9/v1");
  store.setState({ answered: { id: "answered", name: "old", provider: "", failoverCount: 0 } });
  globalThis.fetch = kanban({ status: "blocked", block_reason: "down" });
  await turn("hallo");
  assert.equal(store.getState().answered, null);
  assert.equal(selectShownModel(store.getState()).name, catalogName());
});

test("the failover banner ignores an answer from before the swap", () => {
  withEndpoint("http://localhost:9/v1");
  store.setState({ answered: { id: "answered", name: "old", provider: "", failoverCount: 0 } });
  assert.equal(store.getState().simulateFailover("test"), true);
  assert.equal(selectShownModel(store.getState()).name, "old");
  assert.equal(selectFailoverModel(store.getState()).name, catalogName());
});
