import { Sparkline, Pct, LiveBadge, FeedBadge } from "./bits";
import { toTvSymbol, useMarketData, useEngineTelemetry } from "../hooks/useMarketData";

interface TfStat {
  tf: string;
  pct: number;
}

export function EnvelopeChart({ data, symbol }: { data: Record<string, unknown>; symbol?: string }) {
  const simSpark = (data.spark as number[]) ?? [];
  const simPrice = (data.price as number) ?? 0;
  const simChange = (data.changePct as number) ?? 0;

  const { data: ohlcv, source } = useMarketData(
    "ohlcv",
    { symbol: toTvSymbol(symbol), interval: "60", limit: "80" },
    { spark: simSpark, price: simPrice, changePct: simChange },
    120_000,
  );

  /* Engine telemetry (gravity potential + regime) over the UDS event bus.
     Price/OHLC still come from the tvremix proxy — two independent feeds, two
     independent badges, so a dead bus is never masked by a healthy price feed. */
  const { telemetry, connection } = useEngineTelemetry();
  const feedLive = connection === "CONNECTED_LIVE";
  const gravity = feedLive ? telemetry.gravity : null;
  const regime = feedLive ? telemetry.regime : null;
  const micro = feedLive ? telemetry.microstructure : null;

  const spark = ohlcv.spark ?? simSpark;
  const marketCap = data.marketCap as string;
  const volume = data.volume as string;
  const tfStats = (data.tfStats as TfStat[]) ?? [];
  const price = ohlcv.price ?? simPrice;
  const changePct = ohlcv.changePct ?? simChange;
  const venue = (data.venue as string) ?? "BINANCE";
  const decimals = price > 100 ? 2 : 4;
  const downTrend = changePct < 0;

  return (
    <div className="flex flex-col h-full gap-2">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-[11px] text-slate-500">
            {String(data.symbol ?? symbol ?? "—")} · {venue}
          </p>
          <p className="text-2xl font-bold text-white tabular-nums mt-0.5">
            {price.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}{" "}
            <span className="text-sm font-normal text-slate-400">USD</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Pct value={changePct} />
          <div className="flex items-center gap-1">
            <LiveBadge source={source} />
            <FeedBadge connection={connection} />
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-[150px] -mx-1">
        <Sparkline values={spark} color={downTrend ? "#e5484d" : "#2fae87"} height={170} />
      </div>

      <div className="grid grid-cols-6 gap-1 text-center">
        {tfStats.map((s) => (
          <div key={s.tf} className="rounded-md bg-white/[0.03] border border-white/[0.05] py-1.5">
            <p className="text-[9px] uppercase tracking-wide text-slate-600">{s.tf}</p>
            <p className={`text-[10px] font-mono ${s.pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {s.pct >= 0 ? "+" : ""}
              {s.pct.toFixed(1)}%
            </p>
          </div>
        ))}
      </div>

      {/* Engine read: gravity potential and regime, straight off the bus.
          Rendered only while a tick arrived inside the staleness window —
          fail-closed means no frozen number is shown as if it were current. */}
      <div className="grid grid-cols-4 gap-1 text-center border-t border-white/[0.06] pt-2.5 mt-1">
        {[
          { label: "V total", value: gravity ? gravity.v_total.toFixed(3) : "—" },
          { label: "L2 depth", value: gravity ? gravity.l2_depth.toFixed(2) : "—" },
          { label: "Imbalance", value: micro ? micro.imbalance_ratio.toFixed(3) : "—" },
          { label: "Confidence", value: regime ? `${(regime.confidence * 100).toFixed(0)}%` : "—" },
        ].map((cell) => (
          <div key={cell.label} className="rounded-md bg-white/[0.03] border border-white/[0.05] py-1.5">
            <p className="text-[9px] uppercase tracking-wide text-slate-600">{cell.label}</p>
            <p className={`text-[10px] font-mono ${feedLive ? "text-white" : "text-slate-600"}`}>
              {cell.value}
            </p>
          </div>
        ))}
      </div>

      {regime && regime.is_forbidden_zone > 0 && (
        <p className="text-[10px] font-medium text-rose-300 border border-rose-400/30 bg-rose-400/10 rounded px-2 py-1">
          Verbotene Zone (Axiom 1) — kein Trade in dieses Niveau.
        </p>
      )}

      <div className="grid grid-cols-2 gap-2 border-t border-white/[0.06] pt-2.5 mt-1">
        <div>
          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">Market cap</p>
          <p className="text-sm font-semibold text-white tabular-nums">{marketCap}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.12em] text-slate-600">Volume</p>
          <p className="text-sm font-semibold text-white tabular-nums">{volume}</p>
        </div>
      </div>
    </div>
  );
}
