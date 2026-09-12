import type { CvdCell } from "../marketData";
import { useEngineTelemetry, type MicrostructurePayload } from "../hooks/useMarketData";
import { FeedBadge, Insight } from "./bits";

function cellStyle(delta: number) {
  const intensity = Math.min(1, Math.abs(delta));
  if (delta > 0) return { background: `rgba(52,211,153,${0.12 + intensity * 0.5})` };
  return { background: `rgba(248,113,113,${0.12 + intensity * 0.5})` };
}

/**
 * Map a `microstructure_tick` payload onto the heatmap grid.
 *
 * `footprint_delta` is the engine's own volume-delta footprint
 * (`MicrostructureEngine.calculate_footprint_map`, resampled to 12 bins by
 * `Architect/limbs/telemetry_feed.py`) — the same quantity this widget draws,
 * so no re-interpretation happens here.
 */
export function cvdFromTelemetry(payload: MicrostructurePayload, labels?: string[]): {
  bins: CvdCell[];
  buyPct: number;
  sellPct: number;
  imbalanceRatio: number;
  depthPct: number;
} {
  const bins: CvdCell[] = payload.footprint_delta.map((delta, i) => ({
    delta,
    label: labels?.[i] ?? String(i).padStart(2, "0"),
  }));
  const buys = bins.filter((b) => b.delta > 0).length;
  const buyPct = bins.length ? Math.round((buys / bins.length) * 100) : 0;
  return {
    bins,
    buyPct,
    sellPct: 100 - buyPct,
    imbalanceRatio: payload.imbalance_ratio,
    depthPct: payload.depth_2pct,
  };
}

export function CvdHeatmap({ data }: { data: Record<string, unknown> }) {
  const { telemetry, connection } = useEngineTelemetry();
  const live = connection === "CONNECTED_LIVE" && telemetry.microstructure !== null;

  // Fail-closed: the engine's footprint replaces the template mock only while a
  // tick arrived inside the staleness window. On STALE/DISCONNECTED the grid
  // keeps the last shape it was hydrated with and the badge says so — no value
  // here is presented as live that the bus did not just deliver.
  const fromFeed = live ? cvdFromTelemetry(telemetry.microstructure!) : null;
  const bins = (fromFeed?.bins ?? (data.bins as CvdCell[])) ?? [];
  const buyPct = fromFeed?.buyPct ?? (data.buyPct as number);
  const sellPct = fromFeed?.sellPct ?? (data.sellPct as number);

  const imbalance = buyPct > sellPct ? "buy-side pressure dominant" : "sell-side pressure dominant";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 mb-2.5">
        <span className="text-[11px] text-slate-400">
          Buy pressure <b className="text-emerald-400 tabular-nums">{buyPct}%</b>
        </span>
        <div className="flex-1 h-1.5 rounded-full overflow-hidden flex relative">
          <div className="absolute inset-y-0 left-0 h-full" style={{ width: "100%", background: "#34d399", transform: `scaleX(${buyPct / 100})`, transformOrigin: "left" }} />
          <div className="absolute inset-y-0 right-0 h-full" style={{ width: "100%", background: "#f87171", transform: `scaleX(${sellPct / 100})`, transformOrigin: "right" }} />
        </div>
        <span className="text-[11px] text-slate-400">
          <b className="text-rose-400 tabular-nums">{sellPct}%</b> Sell
        </span>
        <FeedBadge connection={connection} />
      </div>

      <div className="grid grid-cols-12 gap-1">
        {bins.map((bin, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div
              className="w-full h-14 rounded-md grid place-items-center"
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
        {live ? (
          <>
            Engine-Orderflow: {imbalance} (Imbalance {fromFeed!.imbalanceRatio.toFixed(3)} bei{" "}
            {(fromFeed!.depthPct * 100).toFixed(1)} % Buchtiefe). Quelle:{" "}
            <code>MicrostructureEngine.calculate_footprint_map</code> über den UDS-Event-Bus.
          </>
        ) : (
          <>
            Kein Live-Orderflow ({connection === "STALE_CACHE_DEGRADED" ? "Cache veraltet" : "Bus getrennt"}) —
            gezeigt wird die Vorlagen-Hydratation, nicht der Markt.
          </>
        )}
      </Insight>
    </div>
  );
}
