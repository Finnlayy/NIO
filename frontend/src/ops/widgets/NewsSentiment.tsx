import type { NewsItem } from "../marketData";
import { toTvSymbol, useMarketData } from "../hooks/useMarketData";
import { LiveBadge } from "./bits";

const sentColor: Record<NewsItem["sentiment"], string> = {
  POS: "#34d399",
  NEG: "#f87171",
  NEU: "#94a3b8",
};

export function NewsSentiment({ data, symbol }: { data: Record<string, unknown>; symbol?: string }) {
  const simItems = (data.items as NewsItem[]) ?? [];
  const { data: liveItems, source } = useMarketData<NewsItem[]>(
    "news",
    { symbol: toTvSymbol(symbol), limit: "8" },
    simItems,
    300_000,
  );
  const items = liveItems.length ? liveItems : simItems;

  // Derive sentiment split from the rendered items; fall back to sim baseline.
  const total = items.length || 1;
  const posCount = items.filter((i) => i.sentiment === "POS").length;
  const negCount = items.filter((i) => i.sentiment === "NEG").length;
  const positive = source === "live" ? Math.round((posCount / total) * 100) : (data.positive as number);
  const negative = source === "live" ? Math.round((negCount / total) * 100) : (data.negative as number);
  const neutral = source === "live" ? 100 - positive - negative : (data.neutral as number);
  const verdict = data.verdict as string;

  const verdictColor =
    negative > positive + 10 ? "#f87171" : positive > negative + 10 ? "#34d399" : "#fbbf24";

  return (
    <div className="flex flex-col h-full">
      <p className="text-xl font-bold flex items-center gap-2" style={{ color: verdictColor }}>
        {negative > positive + 10
          ? "Mostly negative"
          : positive > negative + 10
            ? "Mostly positive"
            : verdict}
        <LiveBadge source={source} />
      </p>

      <div className="flex h-1.5 rounded-full overflow-hidden mt-2.5">
        <div style={{ width: `${negative}%`, background: "#f87171" }} />
        <div style={{ width: `${neutral}%`, background: "#6b7280" }} />
        <div style={{ width: `${positive}%`, background: "#34d399" }} />
      </div>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-1.5 text-[10px] text-slate-500">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-rose-400" /> Negative {negative}%</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-slate-500" /> Neutral {neutral}%</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Positive {positive}%</span>
      </p>

      <div className="mt-2.5 divide-y divide-white/[0.05] flex-1">
        {items.map((item, i) => (
          <div key={i} className="py-2.5 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[12px] text-slate-200 leading-snug line-clamp-2">{item.headline}</p>
              <p className="text-[10px] text-slate-600 mt-1 flex items-center gap-1.5">
                {item.source} · {item.age}
                {item.highImpact && (
                  <span className="px-1 rounded bg-rose-500/15 text-rose-300 font-semibold">HIGH IMPACT</span>
                )}
              </p>
            </div>
            <span className="text-[10px] font-bold shrink-0 mt-0.5" style={{ color: sentColor[item.sentiment] }}>
              {item.sentiment}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
