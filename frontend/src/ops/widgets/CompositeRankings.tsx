import type { RankRow } from "../marketData";
import { Insight, LiveBadge } from "./bits";
import { useMarketData } from "../hooks/useMarketData";

export function CompositeRankings({ data }: { data: Record<string, unknown> }) {
  const simRows = (data.rows as RankRow[]) ?? [];
  const { data: rows, source } = useMarketData<RankRow[]>(
    "screener",
    { market: "crypto", limit: "10" },
    simRows,
    300_000,
  );

  return (
    <div className="flex flex-col h-full">
      <p className="text-[11px] text-slate-500 mb-2 flex items-center gap-2">
        Ranked by composite score · momentum + levels + volume
        <LiveBadge source={source} />
      </p>
      <div className="space-y-1">
        {rows.map((row) => (
          <div key={row.symbol} className="flex items-center gap-3 py-1 group">
            <span className="w-5 text-[11px] text-slate-600 text-right tabular-nums shrink-0">{row.rank}</span>
            <div className="w-24 shrink-0">
              <p className="text-[12px] font-semibold text-slate-100 font-mono leading-tight">{row.symbol}</p>
              <p className="text-[10px] text-slate-500 leading-tight truncate">{row.name}</p>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] text-slate-500 truncate">
                {row.technicals >= 1
                  ? "Strong buy technicals"
                  : row.technicals >= 0.5
                    ? "Strong Buy technicals"
                    : row.technicals > 0
                      ? "Buy technicals"
                      : "Setup"}
                {row.wkChange ? ` · ${row.wkChange > 0 ? "+" : ""}${row.wkChange.toFixed(1)}% wk, ${row.moChange > 0 ? "+" : ""}${row.moChange.toFixed(1)}% mo` : ""}
              </p>
              <p className="text-[9px] text-slate-600">Weakest: Volume {row.volume}</p>
              <div className="h-1 rounded-full bg-white/[0.06] mt-0.5 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${row.score}%`,
                    background: "linear-gradient(90deg, #0d9488, #2fae87)",
                  }}
                />
              </div>
            </div>
            <span className="w-8 text-right text-[13px] font-bold text-slate-100 tabular-nums shrink-0">{row.score}</span>
          </div>
        ))}
      </div>
      <Insight>
        From a scan of the top 100 coins by market rank: every top name shares the same volume drag
        (0.0–0.3x average participation). Momentum carries the score; volume is the weak axis.
      </Insight>
    </div>
  );
}
