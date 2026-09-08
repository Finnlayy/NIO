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

/* ================================================================== */
/* Engine telemetry over the UDS event bus (P1)                        */
/* ================================================================== */
/* The browser cannot open an AF_UNIX socket, so the Python producer            */
/* (Architect/limbs/telemetry_feed.py) is consumed by                          */
/* src/server/telemetryBridge.ts and re-published as SSE at                    */
/* /api/telemetry/stream. The field names below are the same wire contract as  */
/* TELEMETRY_PAYLOAD_FIELDS in Architect/core/events.py — keep the two in sync.*/

/** Feed connection states — named after `FeedConnectionState` in `Architect/core/state_machine.py`. */
export type FeedConnectionState = "CONNECTED_LIVE" | "STALE_CACHE_DEGRADED" | "DISCONNECTED";

export interface MicrostructurePayload {
  imbalance_ratio: number;
  depth_2pct: number;
  footprint_delta: number[];
}

export interface GravityPayload {
  l2_depth: number;
  l3_iceberg: number;
  polymarket_prob: number;
  v_total: number;
}

export interface RegimePayload {
  cluster_id: number;
  confidence: number;
  /** Wire format is numeric (0/1) — see `validate_telemetry_payload` in Python. */
  is_forbidden_zone: number;
}

export type TelemetryKind = "microstructure_tick" | "gravity_tick" | "regime_tick";

export interface TelemetryRecord {
  kind: TelemetryKind;
  symbol: string;
  clock_s: number | null;
  payload: MicrostructurePayload | GravityPayload | RegimePayload;
}

export interface TelemetrySnapshot {
  microstructure: MicrostructurePayload | null;
  gravity: GravityPayload | null;
  regime: RegimePayload | null;
  /** Wall-clock ms of the last accepted record, 0 when nothing arrived yet. */
  receivedAt: number;
}

export const EMPTY_TELEMETRY: TelemetrySnapshot = {
  microstructure: null,
  gravity: null,
  regime: null,
  receivedAt: 0,
};

/** No tick for this long ⇒ the cached values may no longer describe the market. */
export const STALE_AFTER_MS = 3000;

const MAX_BACKOFF_MS = 30_000;

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Client-side re-validation: a malformed record never reaches widget state. */
export function parseTelemetryRecord(input: unknown): TelemetryRecord | null {
  if (!input || typeof input !== "object") return null;
  const event = input as Record<string, unknown>;
  const kind = event.kind;
  if (kind !== "microstructure_tick" && kind !== "gravity_tick" && kind !== "regime_tick") {
    return null;
  }
  const payload = event.payload;
  if (!payload || typeof payload !== "object") return null;
  const fields = payload as Record<string, unknown>;

  if (kind === "microstructure_tick") {
    const vector = fields.footprint_delta;
    if (!Array.isArray(vector) || vector.length === 0 || !vector.every(isFiniteNumber)) return null;
    if (!isFiniteNumber(fields.imbalance_ratio) || !isFiniteNumber(fields.depth_2pct)) return null;
  } else if (kind === "gravity_tick") {
    for (const key of ["l2_depth", "l3_iceberg", "polymarket_prob", "v_total"] as const) {
      if (!isFiniteNumber(fields[key])) return null;
    }
  } else {
    for (const key of ["cluster_id", "confidence", "is_forbidden_zone"] as const) {
      if (!isFiniteNumber(fields[key])) return null;
    }
  }

  return {
    kind,
    symbol: typeof event.symbol === "string" ? event.symbol : "",
    clock_s: isFiniteNumber(event.clock_s) ? event.clock_s : null,
    // Feldpruefung oben belegt die Verengung; TS braucht den Umweg ueber unknown.
    payload: fields as unknown as TelemetryRecord["payload"],
  };
}

/** Pure state fold — kept free of hooks so the fail-closed rule is unit-testable. */
export function nextTelemetry(snapshot: TelemetrySnapshot, record: TelemetryRecord, now: number): TelemetrySnapshot {
  if (record.kind === "microstructure_tick") {
    return { ...snapshot, microstructure: record.payload as MicrostructurePayload, receivedAt: now };
  }
  if (record.kind === "gravity_tick") {
    return { ...snapshot, gravity: record.payload as GravityPayload, receivedAt: now };
  }
  return { ...snapshot, regime: record.payload as RegimePayload, receivedAt: now };
}

/**
 * Connection state machine.
 *
 * `DISCONNECTED`      transport down — no socket, no stream.
 * `STALE_CACHE_DEGRADED`  transport fine, but no tick within STALE_AFTER_MS.
 * `CONNECTED_LIVE`    a tick arrived inside the window.
 */
export function nextFeedConnection(
  current: FeedConnectionState,
  info: { transportOpen: boolean; lastTickAt: number },
  now: number,
  staleAfterMs: number = STALE_AFTER_MS,
): FeedConnectionState {
  if (!info.transportOpen) return "DISCONNECTED";
  if (info.lastTickAt === 0) return current; // connected, nothing received yet
  return now - info.lastTickAt <= staleAfterMs ? "CONNECTED_LIVE" : "STALE_CACHE_DEGRADED";
}

/** Exponential backoff with a ceiling: 1s, 2s, 4s … capped at MAX_BACKOFF_MS. */
export function backoffDelayMs(attempt: number): number {
  const safeAttempt = Math.max(0, Math.min(20, Math.floor(attempt)));
  return Math.min(MAX_BACKOFF_MS, 1000 * 2 ** safeAttempt);
}

export interface EngineFeed {
  telemetry: TelemetrySnapshot;
  connection: FeedConnectionState;
  /** Attempts made so far — exposed so tests can assert the backoff ladder. */
  attempts: number;
  lastError: string | null;
}

/**
 * Subscribe to the engine telemetry stream.
 *
 * Fail-closed contract: the snapshot is never cleared on a drop (widgets keep
 * their last known shape and stay readable), but `connection` says so, and
 * every consumer gates its *values* on `connection === "CONNECTED_LIVE"`.
 *
 * Reconnects with exponential backoff. All timers and the EventSource are
 * released in the effect cleanup, and every late callback is rejected via
 * `stale`, so an unmount cannot leak a listener or schedule a reconnect.
 */
export function useEngineTelemetry(
  url: string = "/api/telemetry/stream",
  options: { staleAfterMs?: number; maxAttempts?: number } = {},
): EngineFeed {
  const staleAfterMs = options.staleAfterMs ?? STALE_AFTER_MS;
  const maxAttempts = options.maxAttempts ?? Number.POSITIVE_INFINITY;

  const [telemetry, setTelemetry] = useState<TelemetrySnapshot>(EMPTY_TELEMETRY);
  const [connection, setConnection] = useState<FeedConnectionState>("DISCONNECTED");
  const [attempts, setAttempts] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let stalenessTimer: ReturnType<typeof setInterval> | null = null;
    let attempt = 0;
    let transportOpen = false;
    let lastTickAt = 0;
    // Mirror of the published state. The connection state must NOT be an effect
    // dependency: re-running the effect on every badge change would tear the
    // stream down and reset the backoff ladder.
    let current: FeedConnectionState = "DISCONNECTED";

    const applyConnection = (state: FeedConnectionState) => {
      if (stale || state === current) return;
      current = state;
      setConnection(state);
    };

    const onTelemetry = (raw: string) => {
      if (stale) return;
      const record = parseTelemetryRecord(safeParse(raw));
      if (!record) return; // unverifiable ⇒ ignored, state stays as it was
      lastTickAt = Date.now();
      const snapshotAt = lastTickAt;
      setTelemetry((prev) => nextTelemetry(prev, record, snapshotAt));
      applyConnection("CONNECTED_LIVE");
    };

    const connect = () => {
      if (stale) return;
      let opened: EventSource;
      try {
        opened = new EventSource(url);
      } catch (err) {
        applyConnection("DISCONNECTED");
        if (!stale) setLastError(err instanceof Error ? err.message : String(err));
        scheduleReconnect();
        return;
      }
      source = opened;

      opened.onopen = () => {
        if (stale) return;
        transportOpen = true;
        attempt = 0;
        setAttempts(0);
        if (!stale) setLastError(null);
        // `hello` and `ping` are transport signals, not market data: they must
        // not flip the badge to live on their own — only a real tick does that.
        applyConnection(lastTickAt === 0 ? "DISCONNECTED" : "CONNECTED_LIVE");
      };
      opened.addEventListener("telemetry", (event) => onTelemetry((event as MessageEvent).data));
      opened.onerror = () => {
        if (stale) return;
        transportOpen = false;
        opened.close();
        if (source === opened) source = null;
        applyConnection("DISCONNECTED");
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (stale || reconnectTimer) return;
      if (attempt >= maxAttempts) {
        applyConnection("DISCONNECTED");
        return;
      }
      const delay = backoffDelayMs(attempt);
      attempt += 1;
      if (!stale) setAttempts(attempt);
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, delay);
    };

    connect();

    stalenessTimer = setInterval(() => {
      if (stale) return;
      applyConnection(
        nextFeedConnection(current, { transportOpen, lastTickAt }, Date.now(), staleAfterMs),
      );
    }, 1000);

    return () => {
      // Order matters: flag first, so no late callback can touch state.
      stale = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (stalenessTimer) clearInterval(stalenessTimer);
      reconnectTimer = null;
      stalenessTimer = null;
      if (source) {
        source.onopen = null;
        source.onerror = null;
        source.close();
        source = null;
      }
    };
  }, [url, staleAfterMs, maxAttempts]);

  return { telemetry, connection, attempts, lastError };
}

function safeParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
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
