"use strict";
/**
 * Cycle 3 — Sparkline gradient id scoping (style isolation).
 *
 * The SVG id namespace is document-wide. Keying the gradient id off the
 * color made every same-color sparkline share one id: a style-scope leak
 * across widget instances (and a broken fill once the first instance
 * unmounts). With useId(), each instance owns its gradient.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { React, renderToStaticMarkup, mount, collectByType, resetStore } = require("./helpers");
const { Sparkline, upBar, downBar } = require("../ops/widgets/bits");
const { EnvelopeChart } = require("../ops/widgets/EnvelopeChart");

function gradientIds(html) {
  return (html.match(/<linearGradient id="([^"]*)"/g) ?? []).map((s) => s.match(/id="([^"]*)"/)[1]);
}

function urlRefs(html) {
  return (html.match(/url\(#([^)]*)\)/g) ?? []).map((s) => s.replace(/^url\(#/, "").replace(/\)$/, ""));
}

test("two same-color sparklines in one document own distinct gradients", () => {
  const values = [0.2, 0.4, 0.3, 0.7, 0.6];
  const html = renderToStaticMarkup(
    React.createElement(
      "div",
      null,
      React.createElement(Sparkline, { values, color: upBar }),
      React.createElement(Sparkline, { values, color: upBar }),
    ),
  );
  const ids = gradientIds(html);
  assert.equal(ids.length, 2, "one gradient per instance");
  assert.notEqual(ids[0], ids[1], "same color must NOT share a document id");
  const refs = urlRefs(html);
  assert.equal(refs.length, 2, "one fill reference per instance");
  for (const ref of refs) {
    assert.ok(ids.includes(ref), `url(#${ref}) resolves to a defined gradient`);
  }
});

test("gradient id is stable across re-renders (paint reference preserved)", () => {
  const values = [0.2, 0.4, 0.3, 0.7, 0.6];
  const m = mount();
  // Call Sparkline directly (as the renderer would) so its hooks run.
  const first = collectByType(m.render(() => Sparkline({ values })), "linearGradient");
  const second = collectByType(m.render(() => Sparkline({ values })), "linearGradient");
  assert.equal(first.length, 1);
  assert.equal(second.length, 1);
  assert.equal(second[0].props.id, first[0].props.id, "id must not churn on re-render");
});

test("sparkline renders polyline + gradient fill with the given color", () => {
  const values = [0.2, 0.4, 0.3, 0.7, 0.6];
  const html = renderToStaticMarkup(React.createElement(Sparkline, { values, color: downBar, height: 170 }));
  const id = gradientIds(html)[0];
  assert.ok(id, "gradient defined");
  assert.ok(html.includes(`fill="url(#${id})"`), "polygon fill references own gradient");
  assert.ok(html.includes(`stroke="${downBar}"`), "stroke uses the given color");
  const pts = (html.match(/<polyline points="([^"]*)"/) ?? [])[1] ?? "";
  assert.equal(pts.trim().split(" ").length, values.length, "one point per value");
});

test("integration: two Envelope Charts on the page do not leak gradient ids", () => {
  resetStore();
  const data = {
    symbol: "ZECUSDT",
    venue: "BINANCE",
    price: 813.9,
    changePct: 1.2, // both charts render the same (up) color
    spark: [0.2, 0.4, 0.3, 0.7, 0.6, 0.8],
    marketCap: "13.8B",
    volume: "700M",
    tfStats: [],
  };
  const html = renderToStaticMarkup(
    React.createElement(
      "div",
      null,
      React.createElement(EnvelopeChart, { data, symbol: "ZECUSDT" }),
      React.createElement(EnvelopeChart, { data, symbol: "ZECUSDT" }),
    ),
  );
  const ids = gradientIds(html);
  assert.equal(ids.length, 2, "one gradient per chart");
  assert.notEqual(ids[0], ids[1], "widget instances must not share gradient ids");
  resetStore();
});
