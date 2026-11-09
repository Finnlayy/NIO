"use strict";
/**
 * TradingView-MCP-Anbindung: Tool-Zuordnung und Adapter fuer die
 * Antwortformen des offiziellen Servers (mcp.tradingview.com).
 * Die Fixtures sind gekuerzte echte Antworten vom 2026-10-29.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const { toMcpInterval, isReadOnlyTool, TOOLS } = require("../server/tradingview/tools");
const {
  adaptQuote,
  adaptOhlcv,
  adaptTechnicals,
  adaptNews,
  adaptScreener,
  countSignals,
} = require("../server/tradingview/adapters");

test("intervals: legacy chart codes map onto the MCP vocabulary", () => {
  assert.equal(toMcpInterval("60"), "1h");
  assert.equal(toMcpInterval("240"), "4h");
  assert.equal(toMcpInterval("15"), "15m");
  assert.equal(toMcpInterval("D"), "1D");
  assert.equal(toMcpInterval("W"), "1W");
  assert.equal(toMcpInterval("1m"), "1m", "one minute stays a minute");
  assert.equal(toMcpInterval("1M"), "1M", "one month stays a month");
  assert.equal(toMcpInterval("4h"), "4h");
  assert.equal(toMcpInterval(null), "1h");
});

test("passthrough gate: only read-only tools, never alert or watchlist writes", () => {
  for (const name of Object.values(TOOLS).filter((n) => n !== TOOLS.screener)) {
    assert.ok(isReadOnlyTool(name), name);
  }
  assert.ok(isReadOnlyTool("mcp-tv-search-symbols"));
  assert.ok(isReadOnlyTool("mcp-watchlist-list-watchlists"));
  for (const name of [
    "mcp-tv-create-alert",
    "mcp-tv-delete-alert",
    "mcp-tv-update-alert",
    "mcp-tv-stop-alerts",
    "mcp-tv-restart-alerts",
    "mcp-watchlist-add-to-watchlist",
    "mcp-watchlist-delete-watchlist",
    "mcp-tv-get-news/../create-alert",
    "tools",
  ]) {
    assert.equal(isReadOnlyTool(name), false, name);
  }
});

test("quote: TradingView 'change' is already a percentage", () => {
  const raw = { change: -0.25, change_abs: -203.6, close: 81032.07, description: "Bitcoin", name: "BTCUSD" };
  const q = adaptQuote(raw, "BINANCE:BTCUSDT");
  assert.equal(q.price, 81032.07);
  assert.equal(q.changePct, -0.25);
  assert.equal(q.name, "Bitcoin");
});

test("ohlcv: bars with o/h/l/c/t keys become a normalized spark", () => {
  const bars = [80058, 80305, 81061, 80900, 81200].map((c, i) => ({ c, o: c, h: c, l: c, t: i, v: 1 }));
  const d = adaptOhlcv({ bars, count: 5, interval: "1h" });
  assert.equal(d.price, 81200);
  assert.equal(Math.min(...d.spark), 0);
  assert.equal(Math.max(...d.spark), 1);
});

const technicals = {
  interval: "1h",
  price: 81032.07,
  summary: { ma: "STRONG_BUY", other: "BUY", recommendation: "STRONG_BUY", value: 0.6 },
  moving_averages: { ema10: 80294, ema200: 80871, sma50: 80614, sma200: 81019, vwma: null },
  oscillators: { adx: 18.4, ao: -382.8, cci20: 57, macd: -101.2, macd_signal: -157.2, momentum: 854, rsi: 60.3, stoch_k: 45.1 },
};

test("technicals: verdict, score and tallies come from the real rating", () => {
  const t = adaptTechnicals(technicals);
  assert.equal(t.verdict, "Strong Buy");
  assert.equal(t.score, 80, "value 0.6 on -1..1 -> 80/100");
  assert.equal(t.tf, "1h");
  assert.equal(t.sma50, 80614);
  assert.equal(t.sma50Label, "Buy");
  // No fixed placeholder tallies: a strong-buy rating must not show more sells than buys.
  assert.ok(t.buy > t.sell, `buy ${t.buy} vs sell ${t.sell}`);
});

test("countSignals follows the TradingView voting rules", () => {
  const c = countSignals(technicals);
  // MAs: price above ema10/ema200/sma50/sma200 -> 4 buy (vwma null skipped).
  // Osc: rsi 60 n, stoch 45 n, cci 57 n, momentum + b, ao - s, macd>signal b, adx n.
  assert.deepEqual(c, { buy: 6, sell: 1, neutral: 4 });
  assert.equal(countSignals({ summary: {} }), null);
});

test("news: headlines with epoch-second timestamps and provider names", () => {
  const now = Math.floor(Date.now() / 1000);
  const items = adaptNews({
    count: 2,
    has_more: true,
    headlines: [
      { id: "a", title: "Bitcoin strategy", published: now - 33 * 60, provider: { name: "Crypto Briefing" }, urgency: 2 },
      { id: "b", title: "Fed outlook", published: now - 3 * 3600, provider: { name: "dpa-AFX" }, urgency: 1 },
    ],
  });
  assert.equal(items.length, 2);
  assert.equal(items[0].headline, "Bitcoin strategy");
  assert.equal(items[0].source, "Crypto Briefing");
  assert.equal(items[0].age, "33m");
  assert.equal(items[1].age, "3h");
  assert.equal(items[1].highImpact, true);
});

test("screener: rows scored from Recommend.All with weekly/monthly perf", () => {
  const rows = adaptScreener({
    filter_preset: "relative_strength",
    rows: [
      { symbol: "CRYPTO:ONUSD", description: "Orochi Network", "Recommend.All": 0.48, "Perf.W": 56.7, "Perf.1M": 71.4 },
      { symbol: "CRYPTO:INITUSD", description: "Initia", "Recommend.All": -1, "Perf.W": 1, "Perf.1M": 2 },
    ],
  });
  assert.equal(rows[0].symbol, "ONUSD");
  assert.equal(rows[0].name, "Orochi Network");
  assert.equal(rows[0].score, 74);
  assert.equal(rows[0].wkChange, 56.7);
  assert.equal(rows[0].moChange, 71.4);
  assert.ok(Math.abs(rows[0].technicals - 0.74) < 1e-9);
  assert.equal(rows[1].score, 0);
});

test("refresh button hands live widgets a new refreshKey", () => {
  const { seedDefaultLayout, resetStore } = require("./helpers");
  const { useGridStore, dispatchRefresh } = require("../ops/store");
  seedDefaultLayout();
  const target = useGridStore.getState().widgets.find((w) => w.templateId === "TPL_01");
  assert.equal(target.data.refreshedAt, undefined);
  dispatchRefresh(target);
  const after = useGridStore.getState().widgets.find((w) => w.id === target.id);
  // useMarketData refetches (with fresh=1) whenever this value changes.
  assert.equal(typeof after.data.refreshedAt, "number");
  resetStore();
});
