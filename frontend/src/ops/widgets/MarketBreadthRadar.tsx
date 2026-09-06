import { tickers, fmt, type Ticker } from "../marketData";
import { useMarketData } from "../hooks/useMarketData";
import { Pct, Insight, LiveBadge } from "./bits";

/* Treemap-style breadth grid: tile area ~ market weight proxy, color = change */
function tileWeight(t: Ticker) {
  const bySymbol: Record<string, number> = {
    BTCUSDT: 34, ETHUSDT: 22, BNBUSDT: 14, SOLUSDT: 10, LTCUSDT: 7,
    XRPUSDT: 6, NEARUSDT: 5, DOGEUSDT: 4, ADAUSDT: 4, AVAXUSDT: 4,
    ZECUSDT: 4, MAGMAUSDT_P: 3, ACEUSDT: 3, DOTUSDT: 4,
  };
  return bySymbol[t.symbol.replace(/[.-]/g, "_")] ?? 4;
}

function tileColor(changePct: number) {
  if (changePct >= 10) return "rgba(16,185,129,0.55)";
  if (changePct >= 3) return "rgba(16,185,129,0.4)";
  if (changePct >= 0.5) return "rgba(16,185,129,0.24)";
  if (changePct > -0.5) return "rgba(64,70,92,0.5)";
  if (changePct > -3) return "rgba(229,72,77,0.24)";
  return "rgba(229,72,77,0.45)";
}

interface LiveQuoteMap {
  byBase: Record<string, { price: number; changePct: number }>;
}

export function MarketBreadthRadar({ data }: { data: Record<string, unknown> }) {
  const simTape = (data.tickers as Ticker[]) ?? tickers;
  const insight = data.insight as string;

  // Live breadth quotes (batched, server-cached). Merge over the simulated
  // tape by base symbol (e.g. BINANCE:BTCUSDT -> BTC) so price + change reflect
  // live data while sim-only symbols keep rendering.
  const { data: live, source } = useMarketData<LiveQuoteMap>(
    "quotes",
    {},
    { byBase: {} },
    180_000,
  );

  const tape: Ticker[] = simTape.map((t) => {
    const base = t.symbol.replace("USDT", "").replace(/\.P$/, "");
    const liveQuote = live?.byBase?.[base];
    if (liveQuote) {
      return {
        ...t,
        price: liveQuote.price,
        changePct: liveQuote.changePct,
        decimals: liveQuote.price > 1 ? 2 : 4,
      };
    }
    return t;
  });

  const leaders = [...tape].sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct)).slice(0, 6);
  const advancers = tape.filter((t) => t.changePct > 0).length;
  const decliners = tape.filter((t) => t.changePct < 0).length;

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Breadth summary */}
      <div className="flex items-center gap-3 text-[11px]">
        <span className="text-slate-400">
          <b className="text-emerald-400 tabular-nums">{advancers}</b> up ·{" "}
          <b className="text-rose-400 tabular-nums">{decliners}</b> down
        </span>
        <LiveBadge source={source} />
      </div>

      {/* Ticker tape */}
      <div className="overflow-hidden rounded-lg border border-white/[0.06] bg-black/25">
        <div className="flex gap-6 px-3 py-1.5 whitespace-nowrap animate-[ticker_32s_linear_infinite] hover:[animation-play-state:paused]">
          {[...tape, ...tape].map((t, i) => (
            <span key={`${t.symbol}-${i}`} className="inline-flex items-center gap-1.5 text-[11px] font-mono shrink-0">
              <span className="text-slate-400">{t.symbol.replace("USDT", "")}</span>
              <span className="text-slate-300">{fmt(t.price, t.decimals)}</span>
              <Pct value={t.changePct} />
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_220px] gap-3 flex-1 min-h-0">
        {/* Treemap */}
        <div className="grid grid-cols-4 auto-rows-[64px] gap-1.5">
          {[...tape]
            .sort((a, b) => tileWeight(b) - tileWeight(a))
            .map((t) => (
              <div
                key={t.symbol}
                className="rounded-lg p-2 flex flex-col justify-between min-w-0"
                style={{
                  background: tileColor(t.changePct),
                  gridColumn: tileWeight(t) >= 20 ? "span 2" : undefined,
                  gridRow: tileWeight(t) >= 20 ? "span 2" : undefined,
                }}
                title={`${t.name} · ${fmt(t.price, t.decimals)}`}
              >
                <p className="text-[11px] font-semibold text-white/90 truncate">
                  {t.symbol.replace("USDT", "").replace(".P", "")}
                </p>
                <Pct value={t.changePct} />
              </div>
            ))}
        </div>

        {/* Leaders rail */}
        <div className="rounded-lg border border-white/[0.06] bg-black/20 p-2.5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500 mb-2">Largest moves</p>
          <div className="space-y-1.5">
            {leaders?.map((t) => (
              <div key={t.symbol} className="flex items-center justify-between text-[11px] gap-2">
                <span className="text-slate-300 font-mono truncate">{t.symbol.replace("USDT", "")}</span>
                <Pct value={t.changePct} />
              </div>
            ))}
          </div>
          <p className="text-[10px] text-slate-600 mt-3 leading-relaxed">
            Not investment advice. {source === "live" ? "Live TradingView feed via tvremix." : "Simulated telemetry (live feed unavailable)."}
          </p>
        </div>
      </div>

      <Insight>{insight}</Insight>
    </div>
  );
}
