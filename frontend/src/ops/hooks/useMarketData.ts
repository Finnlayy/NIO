"use client";

import { useEffect, useRef, useState } from "react";

export type DataSource = "live" | "sim" | "loading";

interface MarketState<T> {
  data: T;
  source: DataSource;
}

/** Normalize a bare ticker ("BTCUSDT") to tvremix's EXCHANGE:TICKER form. */
export function toTvSymbol(symbol?: string): string {
  if (!symbol) return "BINANCE:BTCUSDT";
  if (symbol.includes(":")) return symbol;
  return `BINANCE:${symbol}`;
}

/**
 * Fetch a normalized market dataset from the server-side tvremix proxy.
 * Falls back to the provided simulated dataset whenever the live feed is
 * unavailable, so the grid always renders. Polls on `refreshMs`.
 */
export function useMarketData<T>(
  tool: "quote" | "quotes" | "ohlcv" | "technicals" | "news" | "screener",
  query: Record<string, string>,
  fallback: T,
  refreshMs = 120_000,
): MarketState<T> {
  const [state, setState] = useState<MarketState<T>>({ data: fallback, source: "loading" });
  const fallbackRef = useRef(fallback);
  fallbackRef.current = fallback;

  const qs = new URLSearchParams(
    Object.entries(query).filter(([, v]) => v !== undefined && v !== ""),
  ).toString();
  const url = `/api/market/${tool}?${qs}`;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function load() {
      try {
        const res = await fetch(url, { cache: "no-store" });
        const json = await res.json();
        if (cancelled) return;
        if (json?.ok && json?.data) {
          setState({ data: mergeDeep(fallbackRef.current, json.data) as T, source: "live" });
        } else {
          setState({ data: fallbackRef.current, source: "sim" });
        }
      } catch {
        if (!cancelled) setState({ data: fallbackRef.current, source: "sim" });
      } finally {
        if (!cancelled && refreshMs > 0) {
          timer = setTimeout(load, refreshMs);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [url, refreshMs]);

  return state;
}

/** Shallow-merge live fields over the simulated baseline (keeps sim-only fields). */
function mergeDeep<T>(base: T, live: unknown): T {
  if (Array.isArray(live)) return live as T;
  if (live && typeof live === "object" && base && typeof base === "object" && !Array.isArray(base)) {
    return { ...(base as Record<string, unknown>), ...(live as Record<string, unknown>) } as T;
  }
  return live as T;
}

/** Global connection status — is the tvremix proxy reaching live data? */
export function useDataSourceStatus(): DataSource {
  const [status, setStatus] = useState<DataSource>("loading");

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch("/api/market/quote?symbol=BINANCE:BTCUSDT", { cache: "no-store" });
        const json = await res.json();
        if (!cancelled) setStatus(json?.ok ? "live" : "sim");
      } catch {
        if (!cancelled) setStatus("sim");
      }
    }
    check();
    const t = setInterval(check, 60_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  return status;
}
