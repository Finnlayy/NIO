/* ------------------------------------------------------------------ */
/* Adapters — normalize raw TradingView MCP output into widget shapes. */
/* Defensive by design: the exact JSON varies; we extract defensively  */
/* and fall back to null so the client can keep simulated data.        */
/* ------------------------------------------------------------------ */

type Raw = any;

function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = parseFloat(v.replace(/[,$%\s]/g, ""));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function str(v: unknown): string | null {
  if (typeof v === "string" && v.trim()) return v;
  return null;
}

function findField(obj: Raw, keys: string[]): unknown {
  if (!obj || typeof obj !== "object") return undefined;
  for (const k of keys) {
    if (k in obj && obj[k] !== undefined && obj[k] !== null) return obj[k];
    // case-insensitive
    const hit = Object.keys(obj).find((rk) => rk.toLowerCase() === k.toLowerCase());
    if (hit && obj[hit] !== undefined && obj[hit] !== null) return obj[hit];
  }
  return undefined;
}

function asArray(v: unknown): Raw[] {
  if (Array.isArray(v)) return v;
  if (v && typeof v === "object" && Array.isArray((v as Raw).data)) return (v as Raw).data;
  return [];
}

/* --------------------------- Quotes ------------------------------ */

export interface LiveQuote {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  decimals: number;
}

export function adaptQuote(raw: Raw, fallbackSymbol: string): LiveQuote | null {
  const q = raw?.quote ?? raw?.snapshot ?? raw?.data ?? raw;
  const price =
    num(findField(q, ["close", "price", "last", "lp", "regularMarketPrice", "current_price"])) ??
    num(findField(q, ["last_price"]));
  if (price === null) return null;

  const changePct =
    num(
      findField(q, [
        "changePct",
        "change_pct",
        "chp",
        "percent_change",
        "regularMarketChangePercent",
        "change_percent",
        "change",
      ]),
    ) ??
    num(findField(q, ["changePercent"])) ??
    0;

  const name =
    str(findField(q, ["description", "name", "shortName", "longName", "symbol_name"])) ??
    fallbackSymbol;

  return {
    symbol: fallbackSymbol,
    name,
    price,
    changePct,
    decimals: price > 1000 ? 2 : price > 1 ? 2 : 4,
  };
}

/* --------------------------- OHLCV ------------------------------- */

export interface LiveOhlcv {
  spark: number[];
  price: number;
  changePct: number;
}

export function adaptOhlcv(raw: Raw): LiveOhlcv | null {
  const bars = asArray(raw?.bars ?? raw?.ohlcv ?? raw?.candles ?? raw?.data ?? raw);
  const closes = bars
    .map((b) =>
      num(
        findField(b, [
          "close",
          "c",
          "closePrice",
          "price",
        ]),
      ),
    )
    .filter((v): v is number => v !== null);

  if (closes.length < 5) return null;

  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const spark = closes.map((c) => (c - min) / range);
  const price = closes[closes.length - 1];
  const first = closes[0];
  const changePct = ((price - first) / first) * 100;

  return { spark, price, changePct };
}

/* ------------------------- Technicals ---------------------------- */

export interface LiveTechnical {
  score: number;
  verdict: string;
  sell: number;
  neutral: number;
  buy: number;
  rsi: number;
  macd: number;
  sma50: number;
  sma200: number;
  rsiLabel: string;
  macdLabel: string;
  sma50Label: string;
  sma200Label: string;
  oscillatorLabel: string;
  maLabel: string;
  tf: string;
}

const VERDICT_ORDER = ["strong sell", "sell", "neutral", "buy", "strong buy"];

export function adaptTechnicals(raw: Raw): LiveTechnical | null {
  const t = raw?.technicals ?? raw?.summary ?? raw?.data ?? raw;

  const rating =
    str(
      findField(t, [
        "recommendation",
        "summary",
        "overall",
        "rating",
        "signal",
        "verdict",
      ]),
    )
      ?.toLowerCase()
      .replace(/_/g, " ")
      .trim() ?? "neutral";

  const score =
    (() => {
      const s = num(findField(t, ["score", "confluence", "confluence_score", "rating_score"]));
      if (s !== null && s >= 0 && s <= 100) return Math.round(s);
      // TradingView rating value: -1 (strong sell) .. +1 (strong buy).
      const v = num(findField(t, ["value", "Recommend.All"]));
      if (v !== null && v >= -1 && v <= 1) return Math.round((v + 1) * 50);
      const idx = VERDICT_ORDER.findIndex((v) => rating.includes(v));
      return idx >= 0 ? Math.round(((idx + 0.5) / VERDICT_ORDER.length) * 100) : 50;
    })();

  const counts = (() => {
    const buy =
      num(findField(t, ["buyCount", "buy", "buy_count", "recommendBuy"])) ??
      num((raw?.counts ?? raw?.ratings ?? {})?.buy);
    const sell =
      num(findField(t, ["sellCount", "sell", "sell_count", "recommendSell"])) ??
      num((raw?.counts ?? raw?.ratings ?? {})?.sell);
    const neutral =
      num(findField(t, ["neutralCount", "neutral", "neutral_count", "recommendNeutral"])) ??
      num((raw?.counts ?? raw?.ratings ?? {})?.neutral);
    if (buy !== null && sell !== null && neutral !== null) return { buy, sell, neutral };
    // No tallies upstream: derive them from the raw indicator values.
    return countSignals(raw) ?? { buy: buy ?? 0, sell: sell ?? 0, neutral: neutral ?? 0 };
  })();

  const ind = raw?.indicators ?? raw?.oscillators ?? t?.indicators ?? {};
  const rsi = num(findField(ind, ["rsi", "RSI", "rsi14"])) ?? num(findField(t, ["rsi"])) ?? 50;
  const macd = num(findField(ind, ["macd", "MACD", "macdLevel"])) ?? 0;
  const ma = raw?.moving_averages ?? ind;
  const sma50 = num(findField(ma, ["sma50", "SMA50", "sma_50"])) ?? 0;
  const sma200 = num(findField(ma, ["sma200", "SMA200", "sma_200"])) ?? 0;

  const price = num(raw?.price);
  const vsPrice = (ma: number) => (!price || !ma ? "Neutral" : price > ma ? "Buy" : price < ma ? "Sell" : "Neutral");
  const lbl = (v: number | null) =>
    v === null ? "Neutral" : v < 0 ? "Sell" : v > 0 ? "Buy" : "Neutral";

  return {
    score,
    verdict: rating.replace(/\b\w/g, (c) => c.toUpperCase()),
    sell: counts.sell,
    neutral: counts.neutral,
    buy: counts.buy,
    rsi,
    macd,
    sma50,
    sma200,
    rsiLabel: rsi < 35 ? "Oversold" : rsi > 65 ? "Overbought" : "Neutral",
    macdLabel: lbl(macd),
    sma50Label: vsPrice(sma50),
    sma200Label: vsPrice(sma200),
    oscillatorLabel: score < 30 ? "Strong sell" : score < 45 ? "Sell" : score > 70 ? "Buy" : "Neutral",
    maLabel: score < 45 ? "Sell" : score > 65 ? "Buy" : "Neutral",
    tf: str(raw?.interval) ?? "1h",
  };
}

/**
 * Buy/sell/neutral tally from TradingView's raw indicators, following the
 * rules of its technical rating: a moving average votes buy when price is
 * above it; oscillators vote by their usual thresholds.
 */
export function countSignals(raw: Raw): { buy: number; sell: number; neutral: number } | null {
  const price = num(raw?.price);
  const ma = raw?.moving_averages;
  const osc = raw?.oscillators;
  if (!price || (!ma && !osc)) return null;
  const votes: number[] = [];
  for (const value of Object.values(ma ?? {})) {
    const v = num(value);
    if (v !== null) votes.push(price > v ? 1 : price < v ? -1 : 0);
  }
  const o = (key: string) => num(osc?.[key]);
  const band = (v: number | null, lo: number, hi: number) => (v === null ? null : v < lo ? 1 : v > hi ? -1 : 0);
  const sign = (v: number | null) => (v === null ? null : Math.sign(v));
  const macd = o("macd");
  const signal = o("macd_signal");
  for (const vote of [
    band(o("rsi"), 30, 70),
    band(o("stoch_k"), 20, 80),
    band(o("cci20"), -100, 100),
    sign(o("momentum")),
    sign(o("ao")),
    macd !== null && signal !== null ? Math.sign(macd - signal) : null,
    o("adx") !== null ? 0 : null,
  ]) {
    if (vote !== null) votes.push(vote);
  }
  if (!votes.length) return null;
  return {
    buy: votes.filter((v) => v > 0).length,
    sell: votes.filter((v) => v < 0).length,
    neutral: votes.filter((v) => v === 0).length,
  };
}

/* ---------------------------- News ------------------------------- */

export interface LiveNews {
  headline: string;
  source: string;
  age: string;
  sentiment: "POS" | "NEG" | "NEU";
  highImpact: boolean;
}

export function adaptNews(raw: Raw): LiveNews[] | null {
  const items = asArray(raw?.headlines ?? raw?.news ?? raw?.stories ?? raw?.articles ?? raw?.data ?? raw);
  const out: LiveNews[] = items.slice(0, 8).map((n) => {
    const sentiment =
      str(findField(n, ["sentiment", "sentimentLabel", "tone"]))?.toUpperCase().slice(0, 3) ??
      "NEU";
    const publishedRaw = findField(n, ["published", "time", "date", "publishedAt"]);
    // Epoch seconds (TradingView) or an ISO string.
    const published =
      typeof publishedRaw === "number" ? new Date(publishedRaw * 1000).toISOString() : (str(publishedRaw) ?? "");
    return {
      headline:
        str(findField(n, ["title", "headline", "name", "story"])) ?? "Untitled",
      source:
        str(findField(n, ["source", "publisher", "domain"])) ?? str(n?.provider?.name) ?? "TradingView",
      age: relativeAge(published) || "—",
      sentiment: ["POS", "NEG", "NEU"].includes(sentiment)
        ? (sentiment as LiveNews["sentiment"])
        : "NEU",
      highImpact: Boolean(findField(n, ["highImpact", "important", "breaking"])) || n?.urgency === 1,
    };
  });
  return out.length ? out : null;
}

function relativeAge(iso: string): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso.includes("h") ? iso : null;
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 60) return `${mins}m`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h`;
  return `${Math.round(mins / (60 * 24))}d`;
}

/* --------------------------- Screener ---------------------------- */

export interface LiveRank {
  rank: number;
  symbol: string;
  name: string;
  score: number;
  wkChange: number;
  moChange: number;
  technicals: number;
  volume: string;
}

export function adaptScreener(raw: Raw): LiveRank[] | null {
  const rows = asArray(raw?.rows ?? raw?.results ?? raw?.screener ?? raw?.data ?? raw);
  const out: LiveRank[] = rows
    .map((r, i) => {
      const rating = num(findField(r, ["Recommend.All"]));
      const score =
        num(findField(r, ["compositeScore", "score", "rank_score", "setupScore"])) ??
        (rating !== null ? (rating + 1) * 50 : null);
      if (score === null) return null;
      return {
        rank: i + 1,
        symbol:
          str(findField(r, ["symbol", "ticker", "name"]))?.split(":").pop() ?? `SYM${i}`,
        name: str(findField(r, ["description", "name", "company"])) ?? "",
        score: Math.round(score),
        wkChange: num(findField(r, ["change_1w", "week", "perf_week", "WK", "perf_w", "Perf.W"])) ?? 0,
        moChange: num(findField(r, ["change_1m", "month", "perf_month", "MO", "perf_m", "Perf.1M"])) ?? 0,
        technicals:
          num(findField(r, ["technicals", "tech_score", "recommend_score"])) ??
          (rating !== null ? (rating + 1) / 2 : 0.5),
        volume: "5/20",
      };
    })
    .filter((r): r is LiveRank => r !== null)
    .slice(0, 10);
  return out.length ? out : null;
}
