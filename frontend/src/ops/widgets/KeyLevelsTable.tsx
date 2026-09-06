import type { KeyLevel } from "../marketData";
import { fmt } from "../marketData";
import { Insight } from "./bits";

const kindColor: Record<KeyLevel["kind"], string> = {
  resistance: "#f87171",
  support: "#34d399",
  poc: "#34d399",
  user: "#60a5fa",
  now: "#818cf8",
};

export function KeyLevelsTable({ data, symbol }: { data: Record<string, unknown>; symbol?: string }) {
  const levels = (data.levels as KeyLevel[]) ?? [];

  return (
    <div className="flex flex-col h-full">
      <div className="space-y-[7px]">
        {levels.map((lvl, i) => {
          const color = kindColor[lvl.kind];
          const isNow = lvl.kind === "now";
          return (
            <div key={`${lvl.label}-${i}`} className="flex items-center gap-2 text-[11px]">
              <span
                className="w-24 shrink-0 truncate font-medium flex items-center gap-1.5"
                style={{ color: isNow ? "#818cf8" : color }}
              >
                {lvl.kind === "user" && <span className="text-[8px] px-1 rounded bg-blue-500/20 text-blue-300">YOURS</span>}
                {lvl.label}
              </span>
              <span className="flex-1 h-[6px] relative">
                {isNow ? (
                  <span className="absolute inset-x-0 top-1/2 border-t border-dashed border-indigo-400/70" />
                ) : (
                  <span
                    className="absolute top-1/2 -translate-y-1/2 rounded-[2px] border"
                    style={{
                      width: `${Math.max(10, lvl.width * 100)}%`,
                      marginLeft: lvl.distancePct < 0 ? `${Math.max(0, (1 - lvl.width) * 100 - 40)}%` : "0",
                      borderColor: color,
                      background: `${color}22`,
                      height: "8px",
                    }}
                  />
                )}
              </span>
              <span className="w-20 text-right font-mono text-slate-200 tabular-nums shrink-0">
                {fmt(lvl.price, lvl.price > 100 ? 2 : 4)}
              </span>
              <span
                className="w-14 text-right font-mono tabular-nums shrink-0"
                style={{ color: lvl.distancePct >= 0 ? "#f87171" : "#34d399" }}
              >
                {lvl.distancePct >= 0 ? "+" : ""}
                {lvl.distancePct.toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>

      <Insight>
        {symbol ? `${symbol} trades at the Now line. ` : ""}
        Nearest resistance above / support below frame the invalidation and first target —
        levels flagged YOURS are pinned from the task preset.
      </Insight>
    </div>
  );
}
