import type { PatternSetup } from "../marketData";
import { Insight, upBar, downBar } from "./bits";

function FlagIcon({ bullish }: { bullish: boolean }) {
  return (
    <span
      className="w-9 h-7 rounded-md grid place-items-center shrink-0"
      style={{ background: bullish ? "rgba(52,211,153,0.12)" : "rgba(248,113,113,0.12)" }}
    >
      <svg viewBox="0 0 24 16" className="w-6 h-4">
        <path
          d={bullish ? "M2 14 L6 6 L12 9 L18 3 L20 5 L13 11 L7 8 Z" : "M2 2 L6 10 L12 7 L18 13 L20 11 L13 5 L7 8 Z"}
          fill="none"
          stroke={bullish ? upBar : downBar}
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export function PatternScanner({ data }: { data: Record<string, unknown> }) {
  const patterns = (data.patterns as PatternSetup[]) ?? [];
  const bullish = data.bullish as number;
  const bearish = data.bearish as number;
  const insight = data.insight as string;
  const total = bullish + bearish || 1;

  return (
    <div className="flex flex-col h-full">
      <p className="text-lg font-bold text-white">{patterns.length} forming, none broken yet</p>

      {/* bull/bear progress */}
      <div className="flex h-1.5 rounded-full overflow-hidden mt-2.5">
        <div style={{ width: `${(bullish / total) * 100}%`, background: upBar }} />
        <div style={{ width: `${(bearish / total) * 100}%`, background: downBar }} />
      </div>
      <p className="flex items-center gap-3 mt-1.5 text-[10px]">
        <span className="flex items-center gap-1 text-slate-500">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: upBar }} />
          Bullish {bullish}
        </span>
        <span className="flex items-center gap-1 text-slate-500">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: downBar }} />
          Bearish {bearish}
        </span>
      </p>

      <p className="text-[10px] uppercase tracking-[0.14em] text-slate-600 mt-3 mb-1.5">
        Approaching trigger · {patterns.length}
      </p>

      <div className="space-y-0">
        {patterns.map((p) => (
          <div
            key={p.symbol}
            className="flex items-center gap-3 py-2.5 border-b border-white/[0.05] last:border-0"
          >
            <span className="w-16 text-[12px] font-semibold text-slate-200 font-mono shrink-0">
              {p.symbol.replace("USDT", "")}
            </span>
            <FlagIcon bullish={p.bullish} />
            <span className="text-[12px] text-slate-300 flex-1">{p.pattern}</span>
            <span className="text-[12px] font-mono text-slate-200 tabular-nums">
              {p.trigger.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </span>
            <span className="w-14 text-right text-[10px] text-slate-500 shrink-0">{p.atrStatus}</span>
          </div>
        ))}
      </div>

      <Insight>{insight}</Insight>
    </div>
  );
}
