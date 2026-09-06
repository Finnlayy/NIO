import type { TradePlanData } from "../marketData";
import { fmt } from "../marketData";

export function TradePlan({ data, symbol }: { data: Record<string, unknown>; symbol?: string }) {
  const plan = data.plan as TradePlanData;
  if (!plan) return null;

  const pct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

  return (
    <div className="flex flex-col h-full">
      <button className="self-start px-3 py-1.5 rounded-lg border border-indigo-400/40 text-indigo-300 text-[11px] font-medium hover:bg-indigo-400/10 transition-colors">
        I took this trade
      </button>

      <div className="grid grid-cols-4 gap-2 mt-3 text-center">
        <Stat label="Direction" value="Long" valueClass="text-emerald-400" />
        <Stat label="Risk" value={pct(plan.riskPct)} valueClass="text-rose-400" />
        <Stat label="Reward (T1)" value={pct(plan.rewardPct)} valueClass="text-emerald-400" />
        <Stat label="Risk : reward" value={plan.rr} small />
      </div>

      {/* Plan ladder */}
      <div className="relative flex-1 min-h-[170px] my-3 rounded-lg overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-[46%] bg-emerald-500/[0.06]" />
        <div className="absolute inset-x-0 bottom-0 h-[30%] bg-rose-500/[0.08]" />

        <Ladder y="8%" label="T2" price={plan.t2} plan={plan} color="#34d399" dashed />
        <Ladder y="38%" label="T1" price={plan.t1} plan={plan} color="#34d399" dashed />
        <Ladder y="58%" label="Entry" price={plan.entry} plan={plan} color="#60a5fa" solid dot />
        <Ladder y="92%" label="Stop" price={plan.stop} plan={plan} color="#f87171" dashed />
      </div>

      <div className="space-y-0">
        <Row label="Stop" price={plan.stop} pctValue={plan.riskPct} color="text-rose-400" plan={plan} />
        <Row label="Entry" price={plan.entry} pctValue={0} color="text-blue-400" plan={plan} />
        <Row label="Target 1" price={plan.t1} pctValue={plan.rewardPct} color="text-emerald-400" plan={plan} />
        <Row label="Target 2" price={plan.t2} pctValue={plan.rewardPct * 2} color="text-emerald-400" plan={plan} last />
      </div>
      <p className="text-[10px] text-slate-600 mt-2">Blueprint for {symbol ?? "—"} · simulated levels</p>
    </div>
  );
}

function Ladder({
  y,
  label,
  price,
  plan,
  color,
  dashed,
  solid,
  dot,
}: {
  y: string;
  label: string;
  price: number;
  plan: TradePlanData;
  color: string;
  dashed?: boolean;
  solid?: boolean;
  dot?: boolean;
}) {
  return (
    <div className="absolute inset-x-0 flex items-center" style={{ top: y }}>
      <span
        className="px-1.5 py-0.5 rounded text-[9px] font-bold border shrink-0 z-10"
        style={{ color, borderColor: `${color}66`, background: "rgba(9,11,18,0.9)" }}
      >
        {label}
      </span>
      <span
        className={`flex-1 ${dashed ? "border-t border-dashed" : solid ? "border-t-2" : ""}`}
        style={{ borderColor: `${color}aa` }}
      />
      {dot && <span className="w-2 h-2 rounded-full mr-1" style={{ background: color }} />}
      <span
        className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold shrink-0 z-10"
        style={{ color, border: `1px solid ${color}55`, background: "rgba(9,11,18,0.9)" }}
      >
        {fmt(price, plan.decimals)}
      </span>
    </div>
  );
}

function Row({
  label,
  price,
  pctValue,
  color,
  plan,
  last,
}: {
  label: string;
  price: number;
  pctValue: number;
  color: string;
  plan: TradePlanData;
  last?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between py-2 ${last ? "" : "border-b border-white/[0.06]"}`}>
      <span className={`text-[12px] font-semibold ${color}`}>{label}</span>
      <span className="text-[12px] font-mono text-slate-200 tabular-nums">{fmt(price, plan.decimals)}</span>
      <span className={`text-[11px] font-mono tabular-nums ${color} w-14 text-right`}>
        {pctValue === 0 ? "—" : `${pctValue > 0 ? "+" : ""}${pctValue.toFixed(1)}%`}
      </span>
    </div>
  );
}

function Stat({
  label,
  value,
  valueClass,
  small,
}: {
  label: string;
  value: string;
  valueClass?: string;
  small?: boolean;
}) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-wide text-slate-600">{label}</p>
      <p className={`font-bold mt-0.5 ${small ? "text-[11px]" : "text-[13px]"} ${valueClass ?? "text-slate-100"}`}>
        {value}
      </p>
    </div>
  );
}
