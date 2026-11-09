"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const market = require("../ops/hooks/useMarketData");
const { MarketUnavailable } = require("../ops/widgets/bits");
const widgets = [
  require("../ops/widgets/NewsSentiment").NewsSentiment,
  require("../ops/widgets/TechnicalGauge").TechnicalGauge,
  require("../ops/widgets/EnvelopeChart").EnvelopeChart,
  require("../ops/widgets/CompositeRankings").CompositeRankings,
  require("../ops/widgets/MarketBreadthRadar").MarketBreadthRadar,
];

test("a failed market request renders an error in every live widget, not its fixture", () => {
  const original = market.useMarketData;
  market.useMarketData = (_tool, _query, fixture) => ({ data: fixture, source: "error" });
  try {
    for (const Widget of widgets) {
      const html = renderToStaticMarkup(React.createElement(Widget, { data: { price: 987654321, verdict: "Invented recommendation", items: [] } }));
      assert.match(html, /role="alert"/);
      assert.match(html, /Keine Simulation als Ersatz/);
      assert.doesNotMatch(html, /987654321|Invented recommendation|<polyline/);
    }
  } finally { market.useMarketData = original; }
});

test("market loading and failure have different accessible states", () => {
  assert.match(renderToStaticMarkup(React.createElement(MarketUnavailable, { source: "loading" })), /role="status"/);
  assert.match(renderToStaticMarkup(React.createElement(MarketUnavailable, { source: "error" })), /role="alert"/);
});
