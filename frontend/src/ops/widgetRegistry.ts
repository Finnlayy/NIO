import type { WidgetTemplate } from "./types";
import {
  cvdGrid,
  compositeRanks,
  gaugeFor,
  keyLevelsFor,
  newsFor,
  patternSetups,
  sparklineFor,
  tickers,
  tradePlanFor,
} from "./marketData";
import { networkEdges, networkNodes } from "@/data/network";

/* ================================================================== */
/* Widget Template Gallery                                             */
/* Declarative blueprints — each is JSON-serializable and can be       */
/* dispatched by the NIO Master Twin via ui/hydrate_widget_template.   */
/* ================================================================== */

export const widgetTemplates: WidgetTemplate[] = [
  {
    id: "TPL_01",
    key: "market-breadth-radar",
    title: "Market Breadth Radar",
    tagline: "Sector heatmap · top movers · narrative read",
    category: "Market",
    defaultSpan: 6,
    defaultHeight: "tall",
    dataFactory: () => ({
      tickers,
      advancers: tickers.filter((t) => t.changePct > 0).length,
      decliners: tickers.filter((t) => t.changePct < 0).length,
      leaders: [...tickers].sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct)).slice(0, 6),
      insight:
        "Risk-on tone across crypto: breadth tiles mostly green, led by NEAR Protocol (+13.02%) and Litecoin (+8.13%). MAGMA is the standout (+24%) while ACE is the drag (-11.73%).",
    }),
  },
  {
    id: "TPL_02",
    /* dataFactory is bootstrap/fallback only. At runtime EnvelopeChart layers two
       live feeds over it: OHLCV via useMarketData (tvremix proxy) and the engine
       read (V_total, L2 depth, imbalance, confidence, forbidden zone) via
       useEngineTelemetry on the UDS bus. While the bus is STALE/DISCONNECTED the
       engine cells render "—" rather than a frozen number. */
    key: "quantum-envelope-chart",
    title: "Envelope Chart",
    tagline: "Price area · timeframe bands · key stats",
    category: "Market",
    defaultSymbol: "ZECUSDT",
    defaultSpan: 2,
    defaultHeight: "tall",
    dataFactory: () => ({
      symbol: "ZECUSDT",
      venue: "BINANCE",
      price: tickers.find((t) => t.symbol === "ZECUSDT")?.price ?? 0,
      changePct: tickers.find((t) => t.symbol === "ZECUSDT")?.changePct ?? 0,
      spark: sparklineFor("ZECUSDT", 52, 0.18),
      marketCap: "13.8B",
      volume: "700M",
      tfStats: [
        { tf: "1D", pct: -4.93 },
        { tf: "5D", pct: -0.65 },
        { tf: "1M", pct: 88.89 },
        { tf: "6M", pct: 260.36 },
        { tf: "YTD", pct: 59.55 },
        { tf: "1Y", pct: 1913.32 },
      ],
    }),
  },
  {
    id: "TPL_03",
    key: "gpm-incubation-arena",
    title: "Pattern Scanner",
    tagline: "Forming setups · trigger distance · ATR status",
    category: "Market",
    defaultSpan: 3,
    defaultHeight: "compact",
    dataFactory: () => {
      const patterns = patternSetups();
      return {
        patterns,
        forming: patterns.length,
        broken: 0,
        bullish: patterns.filter((p) => p.bullish).length,
        bearish: patterns.filter((p) => !p.bullish).length,
        insight:
          "No confirmed breakouts — all four patterns are still forming. BTC, ETH and SOL show bull flags with triggers just above price; XRP is the lone bearish setup, invalidated above 1.5286.",
      };
    },
  },
  {
    id: "TPL_04",
    key: "macro-catalyst-timeline",
    title: "News & Sentiment",
    tagline: "Headline stream · sentiment split · impact flags",
    category: "Market",
    defaultSymbol: "BTCUSDT",
    defaultSpan: 3,
    defaultHeight: "tall",
    dataFactory: () => ({
      items: newsFor("BTCUSDT"),
      positive: 44,
      neutral: 28,
      negative: 28,
      verdict: "Mixed",
    }),
  },
  {
    id: "TPL_05",
    key: "limb-mindmap-node",
    title: "Limb Mesh",
    tagline: "NIO nodes · specialist limbs · live link state",
    category: "System",
    defaultSpan: 3,
    defaultHeight: "tall",
    dataFactory: () => ({
      nodes: networkNodes.map((n) => ({ id: n.id, label: n.label, kind: n.kind, color: n.color })),
      edges: networkEdges,
    }),
  },
  {
    id: "TPL_06",
    key: "orderflow-cvd-heatmap",
    title: "Orderflow CVD Heatmap",
    tagline: "Cumulative volume delta · session bins · pressure read",
    category: "Data",
    defaultSpan: 3,
    defaultHeight: "compact",
    /* cvdGrid() is the bootstrap shape (12 bins) used before the first tick and
       whenever the feed is not CONNECTED_LIVE. Live, CvdHeatmap replaces it with
       MicrostructurePayload.footprint_delta from the engine — same 12 bins, so
       the grid never changes size between mock and live. */
    dataFactory: () => cvdGrid(),
  },
  {
    id: "TPL_07",
    key: "vault-earn-arbitrage",
    title: "Trade Plan",
    tagline: "Entry · stop · targets · risk/reward blueprint",
    category: "Execution",
    defaultSymbol: "BTCUSDT",
    defaultSpan: 3,
    defaultHeight: "tall",
    dataFactory: () => ({ plan: tradePlanFor("BTCUSDT") }),
  },
  {
    id: "TPL_08",
    key: "custom-dynamic-table",
    title: "Key Levels Table",
    tagline: "Dynamic level rows · distance · user levels",
    category: "Data",
    defaultSymbol: "ZECUSDT",
    defaultSpan: 3,
    defaultHeight: "tall",
    dataFactory: () => ({ levels: keyLevelsFor("ZECUSDT") }),
  },
  {
    id: "TPL_09",
    key: "technical-signal-gauge",
    title: "Technical Gauge",
    tagline: "Oscillators vs moving averages · RSI/MACD/SMA",
    category: "Market",
    defaultSymbol: "ZECUSDT",
    defaultSpan: 2,
    defaultHeight: "tall",
    dataFactory: () => ({ gauge: gaugeFor("ZECUSDT") }),
  },
  {
    id: "TPL_10",
    key: "composite-score-ranking",
    title: "Composite Rankings",
    tagline: "Setups ranked by momentum · levels · volume score",
    category: "Data",
    defaultSpan: 6,
    defaultHeight: "compact",
    dataFactory: () => ({ rows: compositeRanks() }),
  },
];

export const templateByKey = (key: string) =>
  widgetTemplates.find((t) => t.key === key) ??
  widgetTemplates.find((t) => t.id === key);

export const templateById = (id: WidgetTemplate["id"]) =>
  widgetTemplates.find((t) => t.id === id);
