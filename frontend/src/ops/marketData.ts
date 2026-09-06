/* ================================================================== */
/* Deterministic mock market data — stands in for MCP telemetry feeds  */
/* ================================================================== */

/* Mulberry32 — seedable PRNG so SSR and first client render agree */
export function seededRandom(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface Ticker {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  decimals: number;
}

export const tickers: Ticker[] = [
  { symbol: "BTCUSDT", name: "Bitcoin", price: 77406, changePct: -0.05, decimals: 2 },
  { symbol: "ETHUSDT", name: "Ethereum", price: 2394.2, changePct: -1.02, decimals: 2 },
  { symbol: "XRPUSDT", name: "XRP", price: 1.3383, changePct: -1.0, decimals: 4 },
  { symbol: "ZECUSDT", name: "Zcash", price: 813.9, changePct: -1.92, decimals: 2 },
  { symbol: "MAGMAUSDT.P", name: "Magma", price: 0.5429, changePct: 24.17, decimals: 4 },
  { symbol: "ACEUSDT", name: "MEXC:ACEUSDT", price: 0.1905, changePct: -11.73, decimals: 4 },
  { symbol: "BNBUSDT", name: "BNB", price: 772.98, changePct: 7.43, decimals: 2 },
  { symbol: "SOLUSDT", name: "Solana", price: 107.48, changePct: 1.4, decimals: 2 },
  { symbol: "DOGEUSDT", name: "Dogecoin", price: 0.0876, changePct: 3.3, decimals: 4 },
  { symbol: "ADAUSDT", name: "Cardano", price: 0.2178, changePct: 3.08, decimals: 4 },
  { symbol: "AVAXUSDT", name: "Avalanche", price: 18.45, changePct: 2.45, decimals: 2 },
  { symbol: "NEARUSDT", name: "Near Protocol", price: 13.2, changePct: 13.02, decimals: 2 },
  { symbol: "LTCUSDT", name: "Litecoin", price: 82.13, changePct: 8.13, decimals: 2 },
  { symbol: "DOTUSDT", name: "Polkadot", price: 6.84, changePct: 6.84, decimals: 2 },
];

export function fmt(price: number, decimals: number) {
  return price.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/* Gauge verdicts — value in 0..100, lower = sell */
export interface GaugeData {
  score: number; // 0..100 mapped strong-sell -> strong-buy
  verdict: string;
  sell: number;
  neutral: number;
  buy: number;
  oscillatorLabel: "Sell" | "Neutral" | "Buy" | "Strong sell" | "Strong buy";
  maLabel: "Sell" | "Neutral" | "Buy";
  rsi: number;
  rsiLabel: string;
  macd: number;
  macdLabel: string;
  sma50: number;
  sma50Label: string;
  sma200: number;
  sma200Label: string;
  tf: "1D" | "4h" | "1h" | "15m";
}

export function gaugeFor(symbol: string, seedOffset = 0): GaugeData {
  const rnd = seededRandom(symbol.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0) + seedOffset);
  const t = tickers.find((x) => x.symbol === symbol);
  const score = Math.round(15 + rnd() * 80);
  const verdict = score < 25 ? "Strong Sell" : score < 42 ? "Sell" : score < 58 ? "Neutral" : score < 75 ? "Buy" : "Strong Buy";
  const buy = Math.round(rnd() * 8);
  const sell = Math.round(rnd() * 18);
  const neutral = Math.max(1, 26 - buy - sell);
  const price = t?.price ?? 100;
  const decimals = t?.decimals ?? 2;
  const rsi = Math.round((25 + rnd() * 45) * 100) / 100;
  return {
    score,
    verdict,
    sell,
    neutral,
    buy,
    oscillatorLabel: score < 30 ? "Strong sell" : score < 45 ? "Sell" : score > 70 ? "Buy" : "Neutral",
    maLabel: score < 45 ? "Sell" : score > 65 ? "Buy" : "Neutral",
    rsi,
    rsiLabel: rsi < 35 ? "Oversold" : rsi > 65 ? "Overbought" : "Neutral",
    macd: Math.round((rnd() - 0.5) * 4 * 100) / 100,
    macdLabel: rnd() > 0.5 ? "Buy" : "Sell",
    sma50: Math.round(price * (0.98 + rnd() * 0.03) * 100) / 100,
    sma50Label: rnd() > 0.5 ? "Buy" : "Sell",
    sma200: Math.round(price * (0.95 + rnd() * 0.04) * 10 ** decimals) / 10 ** decimals,
    sma200Label: rnd() > 0.5 ? "Buy" : "Sell",
    tf: "1h",
  };
}

export interface KeyLevel {
  label: string;
  kind: "resistance" | "support" | "poc" | "user" | "now";
  price: number;
  distancePct: number;
  width: number; // 0..1 horizontal extent of the level band
}

export function keyLevelsFor(symbol: string): KeyLevel[] {
  const t = tickers.find((x) => x.symbol === symbol);
  const price = t?.price ?? 100;
  const decimals = t?.decimals ?? 2;
  const rnd = seededRandom(symbol.length * 77 + Math.round(price));
  const levels: KeyLevel[] = [];
  const defs: Array<[string, KeyLevel["kind"], number]> = [
    ["Fib 50%", "resistance", 0.016],
    ["Swing high", "resistance", 0.012],
    ["Fib 61.8%", "resistance", 0.009],
    ["Fib 78.6%", "resistance", 0.004],
    ["Swing high", "resistance", 0.002],
    ["Now", "now", 0],
    ["YOURS · T1", "user", -0.006],
    ["Fib 100%", "support", -0.02],
    ["Trendline", "support", -0.012],
    ["Swing low", "support", -0.018],
    ["Swing low", "support", -0.027],
    ["YOURS · entry", "user", -0.04],
  ];
  for (const [label, kind, dist] of defs) {
    levels.push({
      label,
      kind,
      price: Math.round(price * (1 + dist) * 10 ** decimals) / 10 ** decimals,
      distancePct: Math.round(dist * 1000) / 10,
      width: kind === "now" ? 1 : 0.12 + rnd() * 0.6,
    });
  }
  return levels;
}

export function sparklineFor(symbol: string, points = 48, drift = 0): number[] {
  const t = tickers.find((x) => x.symbol === symbol);
  const rnd = seededRandom(symbol.length * 131 + 7);
  const out: number[] = [];
  let v = 0.5;
  for (let i = 0; i < points; i++) {
    v += (rnd() - 0.48) * 0.14 + drift * 0.004;
    v = Math.min(0.98, Math.max(0.02, v));
    out.push(v);
  }
  void t;
  return out;
}

export interface TradePlanData {
  direction: "Long" | "Short";
  riskPct: number;
  rewardPct: number;
  rr: string;
  entry: number;
  stop: number;
  t1: number;
  t2: number;
  decimals: number;
}

export function tradePlanFor(symbol: string): TradePlanData {
  const t = tickers.find((x) => x.symbol === symbol);
  const price = t?.price ?? 79764;
  const decimals = t?.decimals ?? 2;
  const factor = 10 ** decimals;
  const r = (d: number) => Math.round(price * (1 + d) * factor) / factor;
  return {
    direction: "Long",
    riskPct: -0.4,
    rewardPct: 0.4,
    rr: "T1 1:1 · T2 1:1.9",
    entry: r(-0.0006),
    stop: r(-0.0048),
    t1: r(0.0035),
    t2: r(0.0076),
    decimals,
  };
}

export interface PatternSetup {
  symbol: string;
  pattern: "Bull flag" | "Bear flag" | "Ascending triangle" | "Falling wedge";
  trigger: number;
  atrStatus: string;
  bullish: boolean;
  decimals: number;
}

export function patternSetups(): PatternSetup[] {
  return [
    { symbol: "BTCUSDT", pattern: "Bull flag", trigger: 82300, atrStatus: "1 ATR", bullish: true, decimals: 2 },
    { symbol: "ETHUSDT", pattern: "Bull flag", trigger: 2546.66, atrStatus: "0.9 ATR", bullish: true, decimals: 2 },
    { symbol: "SOLUSDT", pattern: "Bull flag", trigger: 107.48, atrStatus: "0.8 ATR", bullish: true, decimals: 2 },
    { symbol: "XRPUSDT", pattern: "Bear flag", trigger: 1.31, atrStatus: "1.3 ATR", bullish: false, decimals: 2 },
  ];
}

export interface NewsItem {
  headline: string;
  source: string;
  age: string;
  sentiment: "POS" | "NEG" | "NEU";
  highImpact: boolean;
}

const headlinePool: Record<string, Array<[string, string, NewsItem["sentiment"], boolean]>> = {
  BTCUSDT: [
    ["Bitcoin ETF inflows hit record as spot demand climbs", "Binance News", "POS", true],
    ["Whale exchange deposits rise; short-term leverage flushed", "Santiment", "NEU", false],
    ["BTC options skew turns neutral ahead of CPI print", "CoinDesk", "NEG", true],
  ],
  ETHUSDT: [
    ["Ethereum staking ratio reaches new all-time high", "TradingView", "POS", true],
    ["Gas fees slide to multi-month lows as activity cools", "Glassnode", "NEU", false],
    ["ETH/BTC downtrend persists despite spot inflows", "Etherscan", "NEG", false],
  ],
  XRPUSDT: [
    ["Appeal ruling timeline narrows; volume compresses", "XRPL Monitor", "NEU", true],
    ["Cross-border corridor volume prints monthly high", "Ripple Insights", "POS", false],
  ],
  default: [
    ["Funding rates flip positive across majors", "Coinglass", "POS", false],
    ["Liquidity map thins above Asian session highs", "Binance News", "NEG", true],
    ["Stablecoin supply ratio ticks up — sideline cash building", "Santiment", "POS", false],
    ["Large limit walls appear near round-number levels", "TradingView", "NEU", false],
  ],
};

export function newsFor(symbol: string): NewsItem[] {
  const pool = [...(headlinePool[symbol] ?? []), ...headlinePool.default];
  const ages = ["9h", "13h", "15h", "2h", "21h", "1h"];
  return pool.slice(0, 6).map(([headline, source, sentiment, highImpact], i) => ({
    headline,
    source,
    age: ages[i % ages.length],
    sentiment,
    highImpact,
  }));
}

export interface RankRow {
  rank: number;
  symbol: string;
  name: string;
  score: number;
  technicals: number;
  wkChange: number;
  moChange: number;
  volume: string;
}

export function compositeRanks(): RankRow[] {
  const base: Array<[string, string, number, number, number, number, string]> = [
    ["GTUSD", "GateToken", 74, 0.6, 14.4, 38.4, "5/20"],
    ["BNBUSDT", "BNB", 73, 0.6, 11.2, 29.6, "5/20"],
    ["LTCUSDT", "Litecoin", 73, 0.6, 10.2, 20.0, "5/20"],
    ["ASTERUSDT", "Aster", 71, 0.6, 17.4, 35.3, "5/20"],
    ["PONS2USDT", "Pons", 70, 1.0, 479.6, 643.5, "5/20"],
    ["ICPUSDT", "Internet Computer", 70, 0.6, 9.0, 24.8, "5/20"],
    ["BTCUSDT", "Bitcoin", 69, 0.35, 2.4, 23.4, "5/20"],
    ["CAKEUSDT", "PancakeSwap", 67, 0.6, 29.7, 58.0, "5/20"],
    ["PYTHUSDT", "Pyth Network", 66, 0.44, 14.4, 39.1, "5/20"],
    ["MNTUSDT", "Mantle", 66, 0.41, 14.5, 43.0, "5/20"],
  ];
  return base.map(([symbol, name, score, technicals, wkChange, moChange, volume], i) => ({
    rank: i + 1,
    symbol,
    name,
    score,
    technicals,
    wkChange,
    moChange,
    volume,
  }));
}

export interface CvdCell {
  delta: number; // -1..1 (sell -> buy)
  label: string;
}

export function cvdGrid(): { bins: CvdCell[]; buyPct: number; sellPct: number } {
  const rnd = seededRandom(20260905);
  const labels = ["08", "10", "12", "14", "16", "18", "20", "22", "00", "02", "04", "06"];
  const bins = labels.map((label) => ({
    delta: Math.round((rnd() * 2 - 1) * 100) / 100,
    label,
  }));
  const buys = bins.filter((b) => b.delta > 0).length;
  return { bins, buyPct: Math.round((buys / bins.length) * 100), sellPct: 100 - Math.round((buys / bins.length) * 100) };
}

/* Master-Twin orchestration suggestions (the "geopolitical shock" style reads) */
export const orchestratorReads = [
  "Mixed: BTC/ETH/XRP/ZEC respect bands, MAGMA mid-range, ACE at low. No clean directional edge.",
  "Risk-on tone across crypto: breadth tiles all green, led by NEAR (+13%) and LTC (+8%).",
  "No confirmed breakouts — four patterns still forming; bull flags on BTC, ETH, SOL. XRP is the lone bearish setup.",
  "ACE flush extends: technicals strong-sell, price -11.7%. Watch for mean-reversion into the value area.",
  "Funding positive + stablecoin ratio rising — sideline liquidity building into the weekend open.",
];
