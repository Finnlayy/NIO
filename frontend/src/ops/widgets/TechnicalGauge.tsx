import type { GaugeData } from "../marketData";
import { toTvSymbol, useMarketData } from "../hooks/useMarketData";
import { LiveBadge } from "./bits";

function verdictColor(v: string) {
  if (v.includes("Strong Buy") || v === "Buy") return "#34d399";
  if (v.includes("Strong Sell") || v === "Sell") return "#f87171";
  return "#fbbf24";
}
function labelColor(v: string) {
  if (v.includes("Buy") && !v.includes("sell")) return "text-emerald-400";
  if (v.includes("Sell") || v.includes("sell")) return "text-rose-400";
  return "text-amber-300";
}

export function TechnicalGauge({ data, symbol }: { data: Record<string, unknown>; symbol?: string }) {
  const sim = (data.gauge as GaugeData) ?? null;
  const { data: live, source } = useMarketData(
    "technicals",
    { symbol: toTvSymbol(symbol), interval: "60" },
    sim,
    180_000,
  );
  const g = live;
  if (!g) return null;
  const color = verdictColor(g.verdict);

  // Semicircle: angle from 180° (strong sell) to 0° (strong buy)
  const angle = 180 - (g.score / 100) * 180;
  const needleX = 50 + 34 * Math.cos((angle * Math.PI) / 180);
  const needleY = 50 - 34 * Math.sin((angle * Math.PI) / 180);

  return (
    <div className="flex flex-col h-full">
      <div className="relative">
        <svg viewBox="0 0 100 58" className="w-full max-w-[260px] mx-auto block">
          {/* track */}
          <path d="M 14 50 A 36 36 0 0 1 86 50" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" strokeLinecap="round" />
          {/* value arc: from strong-sell (180°) up to needle */}
          <path
            d="M 14 50 A 36 36 0 0 1 86 50"
            fill="none"
            stroke={color}
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray="113"
            strokeDashoffset={113 * (1 - g.score / 100)}
            opacity="0.9"
          />
          <line x1="50" y1="50" x2={needleX} y2={needleY} stroke="#e2e8f0" strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="50" cy="50" r="2.4" fill="#e2e8f0" />
          <text x="14" y="58" fontSize="6" fill="#64748b" textAnchor="middle">Strong sell</text>
          <text x="32" y="26" fontSize="6" fill="#64748b" textAnchor="middle">Sell</text>
          <text x="50" y="13" fontSize="6" fill="#64748b" textAnchor="middle">Neutral</text>
          <text x="68" y="26" fontSize="6" fill="#64748b" textAnchor="middle">Buy</text>
          <text x="86" y="58" fontSize="6" fill="#64748b" textAnchor="middle">Strong buy</text>
        </svg>
        <p className="flex items-center justify-center gap-2 text-sm font-bold -mt-2">
          <span className={labelColor(g.verdict)}>{g.verdict}</span>
          <LiveBadge source={source} />
        </p>
      </div>

      <div className="flex items-center justify-center gap-5 text-center mt-1">
        <Score n={g.sell} label="Sell" tone="sell" />
        <Score n={g.neutral} label="Neutral" tone="neutral" />
        <Score n={g.buy} label="Buy" tone="buy" />
      </div>

      {/* Summary bars */}
      <div className="mt-3 space-y-2">
        <BarLine label="Oscillators" value={g.oscillatorLabel} score={g.score} />
        <BarLine label="Moving averages" value={g.maLabel} score={g.score} />
      </div>

      <dl className="mt-3 space-y-2 text-[11px]">
        <IndicatorRow name="RSI (14)" value={g.rsi.toFixed(2)} verdict={g.rsiLabel} />
        <IndicatorRow name="MACD Level (12,26)" value={g.macd.toFixed(2)} verdict={g.macdLabel} />
        <IndicatorRow name="SMA (50)" value={g.sma50.toLocaleString()} verdict={g.sma50Label} />
        <IndicatorRow name="SMA (200)" value={g.sma200.toLocaleString()} verdict={g.sma200Label} />
      </dl>

      <div className="mt-auto pt-3 grid grid-cols-3 gap-1.5 text-center">
        {(["1D", "4h", "1h"] as const).map((tf) => (
          <button
            key={tf}
            className={`rounded-md py-1.5 text-[10px] font-medium border transition-colors ${
              g.tf === tf
                ? "bg-white/[0.09] border-white/20 text-white"
                : "border-white/[0.07] text-slate-500 hover:text-slate-300"
            }`}
          >
            {tf}
          </button>
        ))}
      </div>
    </div>
  );
}

function Score({ n, label, tone }: { n: number; label: string; tone: "sell" | "neutral" | "buy" }) {
  const cls = tone === "sell" ? "text-rose-400" : tone === "buy" ? "text-emerald-400" : "text-slate-200";
  return (
    <div>
      <p className={`text-xl font-bold tabular-nums ${cls}`}>{n}</p>
      <p className="text-[9px] uppercase tracking-wide text-slate-600">{label}</p>
    </div>
  );
}

function BarLine({ label, value, score }: { label: string; value: string; score: number }) {
  const pct = score;
  const vCls = labelColor(value);
  return (
    <div>
      <div className="flex justify-between text-[10px] mb-1">
        <span className="text-slate-500">{label}</span>
        <span className={vCls}>{value}</span>
      </div>
      <div className="h-1 rounded-full bg-white/[0.06] relative">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, #f59e0b, #34d399)",
          }}
        />
      </div>
    </div>
  );
}

function IndicatorRow({ name, value, verdict }: { name: string; value: string; verdict: string }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.05] pb-1.5">
      <dt className="text-slate-500">{name}</dt>
      <dd className="flex items-center gap-3">
        <span className="text-slate-300 font-mono tabular-nums">{value}</span>
        <span className={`w-12 text-right ${labelColor(verdict)}`}>{verdict}</span>
      </dd>
    </div>
  );
}
