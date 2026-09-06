import type { CvdCell } from "../marketData";
import { Insight } from "./bits";

function cellStyle(delta: number) {
  const intensity = Math.min(1, Math.abs(delta));
  if (delta > 0) return { background: `rgba(52,211,153,${0.12 + intensity * 0.5})` };
  return { background: `rgba(248,113,113,${0.12 + intensity * 0.5})` };
}

export function CvdHeatmap({ data }: { data: Record<string, unknown> }) {
  const bins = (data.bins as CvdCell[]) ?? [];
  const buyPct = data.buyPct as number;
  const sellPct = data.sellPct as number;

  const imbalance = buyPct > sellPct ? "buy-side pressure dominant" : "sell-side pressure dominant";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 mb-2.5">
        <span className="text-[11px] text-slate-400">
          Buy pressure <b className="text-emerald-400 tabular-nums">{buyPct}%</b>
        </span>
        <div className="flex-1 h-1.5 rounded-full overflow-hidden flex">
          <div style={{ width: `${buyPct}%`, background: "#34d399" }} />
          <div style={{ width: `${sellPct}%`, background: "#f87171" }} />
        </div>
        <span className="text-[11px] text-slate-400">
          <b className="text-rose-400 tabular-nums">{sellPct}%</b> Sell
        </span>
      </div>

      <div className="grid grid-cols-12 gap-1">
        {bins.map((bin, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div
              className="w-full h-14 rounded-md grid place-items-center transition-all"
              style={cellStyle(bin.delta)}
              title={`${bin.label}:00 · CVD ${bin.delta > 0 ? "+" : ""}${bin.delta.toFixed(2)}`}
            >
              <span className="text-[9px] font-mono text-white/70">
                {bin.delta > 0 ? "▲" : "▼"}
              </span>
            </div>
            <span className="text-[8px] text-slate-600 font-mono">{bin.label}</span>
          </div>
        ))}
      </div>

      <Insight>
        Session cumulative-volume-delta: {imbalance}. Aggressive flow clusters around the
        session open bins; thin participation mid-session. Hydrated by master-twin liquidity radar.
      </Insight>
    </div>
  );
}
