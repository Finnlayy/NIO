import { useId } from "react";
import type { ReactNode } from "react";
import type { DataSource } from "../hooks/useMarketData";

export const up = "text-emerald-400";
export const down = "text-rose-400";
export const upBar = "#2fae87";
export const downBar = "#e5484d";

/** Small pill showing whether a widget's data is live (tvremix) or simulated. */
export function LiveBadge({ source }: { source: DataSource }) {
  if (source === "loading") return null;
  const live = source === "live";
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wide border ${
        live
          ? "text-emerald-300 border-emerald-400/30 bg-emerald-400/10"
          : "text-slate-500 border-white/10 bg-white/[0.04]"
      }`}
      title={live ? "Live data via tvremix MCP" : "Simulated data (live feed unavailable)"}
    >
      <span className={`w-1 h-1 rounded-full ${live ? "bg-emerald-400 pulse-dot" : "bg-slate-600"}`} />
      {live ? "Live" : "Sim"}
    </span>
  );
}

export function Pct({ value, signed = true }: { value: number; signed?: boolean }) {
  const cls = value >= 0 ? up : down;
  const text = `${signed && value > 0 ? "+" : ""}${value.toFixed(2)}%`;
  return <span className={`font-mono font-medium ${cls}`}>{text}</span>;
}

export function Insight({ children }: { children: ReactNode }) {
  return (
    <p className="text-[11px] leading-relaxed text-slate-400 border-t border-white/[0.06] pt-2.5 mt-3 flex gap-2">
      <span className="text-blue-400 shrink-0">✦</span>
      <span>{children}</span>
    </p>
  );
}

export function Sparkline({
  values,
  color = upBar,
  height = 180,
  fill = true,
}: {
  values: number[];
  color?: string;
  height?: number;
  fill?: boolean;
}) {
  /* Component-scoped gradient id (useId): the SVG id namespace is
     document-wide, so keying the id off the *color* made every same-color
     sparkline on the page share one gradient — a style-scope leak between
     widget instances (and a paint break if the first instance unmounts).
     useId is unique per instance and stable across re-renders/hydration. */
  const gradientId = `spark-${useId()}`;
  const w = 320;
  const h = 100;
  const step = w / Math.max(1, values.length - 1);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(h - v * h).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: "100%", height }} className="block">
      {fill && (
        <>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.28" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#${gradientId})`} />
        </>
      )}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
