/**
 * Server-side bridge from the Python UDS event bus to the browser.
 *
 * The bus (`orchestrator/uds.py`) broadcasts over `AF_UNIX`/**SOCK_DGRAM**, and
 * Node can only bind `AF_UNIX` as `SOCK_STREAM` — connecting a datagram socket
 * to a stream path fails with `EPROTOTYPE` (errno 91). So this module does *not*
 * touch the socket. It owns two child processes instead:
 *
 *   Architect/limbs/telemetry_feed.py   computes engine output, sends datagrams
 *   scripts/uds_to_stdout.py            binds the datagram socket via the repo's
 *                                       own `UDSBroadcastServer` and prints
 *                                       every line as NDJSON on stdout
 *
 * and fans that NDJSON out to any number of HTTP/SSE clients. Keeping the socket
 * in Python also keeps its `0600` mode and stale-inode handling in one tested
 * place (`tests/test_nexus_triad2.py` asserts the mode).
 *
 * Losing events is acceptable by contract (the sink drops rather than blocks),
 * but *silence* is not: if no record arrives within STALE_AFTER_MS the hub
 * reports `stale` and clients fail closed instead of showing a frozen value as
 * if it were live.
 */
import { spawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable } from "node:stream";
import { backoffDelayMs } from "../ops/backoff";

/** Wire contract — mirrors `TELEMETRY_PAYLOAD_FIELDS` in `Architect/core/events.py`. */
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
  is_forbidden_zone: number;
}

export type TelemetryKind = "microstructure_tick" | "gravity_tick" | "regime_tick";

export interface TelemetryRecord {
  kind: TelemetryKind;
  symbol: string;
  clock_s: number | null;
  payload: MicrostructurePayload | GravityPayload | RegimePayload;
}

export type HubState = "live" | "stale";

export const STALE_AFTER_MS = 3000;
const RING_SIZE = 240;
const MAX_STDERR_LOGS = 40;

type Proc = ChildProcessByStdio<null, Readable, Readable>;

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Validate one record against the wire contract. Fail closed on any doubt. */
export function parseTelemetryLine(line: string): TelemetryRecord | null {
  let raw: unknown;
  try {
    raw = JSON.parse(line);
  } catch {
    return null;
  }
  if (!raw || typeof raw !== "object") return null;
  const event = raw as Record<string, unknown>;
  const kind = event.event_kind;
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
    // Field checks above justify the narrowing; TS needs the detour via unknown.
    payload: fields as unknown as TelemetryRecord["payload"],
  };
}

type Listener = (record: TelemetryRecord) => void;

/**
 * `NIO_REPO_ROOT` is the repository root. Both derived paths are relative to the
 * server's working directory when it is unset, so start the server from the repo
 * root or set it explicitly:
 *
 *   NIO_REPO_ROOT=/path/to/NIO npm --prefix frontend run start
 *
 * `NIO_TELEMETRY_FEED`, `NIO_TELEMETRY_CONSUMER` and `NIO_TELEMETRY_SOCKET`
 * override the individual pieces.
 */
export function resolvePaths() {
  const root = (process.env.NIO_REPO_ROOT ?? "").replace(/\/+$/, "");
  return {
    root,
    feed: process.env.NIO_TELEMETRY_FEED ?? `${root}/Architect/limbs/telemetry_feed.py`,
    consumer: process.env.NIO_TELEMETRY_CONSUMER ?? `${root}/scripts/uds_to_stdout.py`,
    socketPath: process.env.NIO_TELEMETRY_SOCKET ?? `${root}/runtime/telemetry.sock`,
  };
}

class TelemetryHub {
  readonly socketPath: string;
  private readonly feedScript: string;
  private readonly consumerScript: string;
  private producer: Proc | null = null;
  private consumer: Proc | null = null;
  private listeners = new Set<Listener>();
  private ring: TelemetryRecord[] = [];
  private lastRecordAt = 0;
  private respawnTimer: NodeJS.Timeout | null = null;
  private respawnAttempts = 0;
  private started = false;
  private stopping = false;
  /** Tail of the children's stderr, so a broken producer is diagnosable. */
  private logs: string[] = [];

  constructor(paths: ReturnType<typeof resolvePaths>) {
    this.feedScript = paths.feed;
    this.consumerScript = paths.consumer;
    this.socketPath = paths.socketPath;
  }

  get state(): HubState {
    if (this.lastRecordAt === 0) return "stale";
    return Date.now() - this.lastRecordAt <= STALE_AFTER_MS ? "live" : "stale";
  }

  get lastAgeMs(): number {
    return this.lastRecordAt === 0 ? Number.POSITIVE_INFINITY : Date.now() - this.lastRecordAt;
  }

  get buffer(): readonly TelemetryRecord[] {
    return this.ring;
  }

  get producerRunning(): boolean {
    return alive(this.producer);
  }

  get consumerRunning(): boolean {
    return alive(this.consumer);
  }

  get recentLogs(): readonly string[] {
    return this.logs;
  }

  start(): void {
    if (this.started || this.stopping) return;
    this.started = true;
    // The consumer owns the socket, so it goes first — the producer only ever
    // `connect`s and tolerates a missing receiver.
    this.spawnConsumer();
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    this.start();
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Replay the ring, then live records. Returns the unsubscribe function. */
  attach(listener: Listener): () => void {
    for (const record of this.ring) listener(record);
    return this.subscribe(listener);
  }

  stop(): void {
    this.stopping = true;
    if (this.respawnTimer) clearTimeout(this.respawnTimer);
    this.respawnTimer = null;
    this.listeners.clear();
    kill(this.producer);
    kill(this.consumer);
    this.producer = null;
    this.consumer = null;
  }

  private log(source: string, chunk: string): void {
    // `chunk` ist dank setEncoding("utf8") bereits ein string.
    const text = chunk.trim();
    if (!text) return;
    for (const line of text.split("\n")) {
      this.logs.push(`${source}: ${line}`);
      if (this.logs.length > MAX_STDERR_LOGS) this.logs.shift();
    }
  }

  private accept(line: string): void {
    const record = parseTelemetryLine(line);
    if (!record) return; // unverifiable lines never reach a widget
    this.lastRecordAt = Date.now();
    this.respawnAttempts = 0;
    this.ring.push(record);
    if (this.ring.length > RING_SIZE) this.ring.splice(0, this.ring.length - RING_SIZE);
    for (const listener of [...this.listeners]) {
      try {
        listener(record);
      } catch {
        /* one bad subscriber must not break the fan-out */
      }
    }
  }

  private spawnConsumer(): void {
    if (this.stopping || alive(this.consumer)) return;
    const child = launch(process.env.NIO_PYTHON ?? "python3", [this.consumerScript, "--socket", this.socketPath]);
    if (!child) {
      this.log("consumer", `spawn failed for ${this.consumerScript}`);
      this.scheduleRespawn();
      return;
    }
    let pending = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      pending += chunk;
      let newline = pending.indexOf("\n");
      while (newline !== -1) {
        const line = pending.slice(0, newline).trim();
        pending = pending.slice(newline + 1);
        if (line) this.accept(line);
        newline = pending.indexOf("\n");
      }
    });
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk: string) => this.log("consumer", chunk));
    child.on("error", () => {
      this.consumer = null;
      this.scheduleRespawn();
    });
    child.on("exit", () => {
      this.log("consumer", `exit code ${child.exitCode ?? "?"} signal ${child.signalCode ?? "-"}`);
      this.consumer = null;
      this.scheduleRespawn();
    });
    this.consumer = child;
    this.spawnProducer();
  }

  private spawnProducer(): void {
    if (this.stopping || alive(this.producer)) return;
    const child = launch(process.env.NIO_PYTHON ?? "python3", [
      this.feedScript,
      "--socket",
      this.socketPath,
      "--tick-s",
      process.env.NIO_TELEMETRY_TICK_S ?? "1",
    ]);
    if (!child) {
      this.log("producer", `spawn failed for ${this.feedScript}`);
      this.scheduleRespawn();
      return;
    }
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk: string) => this.log("producer", chunk));
    child.on("error", () => {
      this.producer = null;
      this.scheduleRespawn();
    });
    child.on("exit", () => {
      this.log("producer", `exit code ${child.exitCode ?? "?"} signal ${child.signalCode ?? "-"}`);
      this.producer = null;
      this.scheduleRespawn();
    });
    this.producer = child;
  }

  private scheduleRespawn(): void {
    if (this.stopping || this.respawnTimer) return;
    const delay = Math.min(1000 * Math.pow(2, this.respawnAttempts), 30000);
    this.respawnAttempts++;
    this.respawnTimer = setTimeout(() => {
      this.respawnTimer = null;
      if (this.stopping) return;
      if (!alive(this.consumer)) this.spawnConsumer();
      else if (!alive(this.producer)) this.spawnProducer();
    }, delay);
    // Must never keep the Node process alive on its own.
    this.respawnTimer.unref?.();
  }
}

function alive(child: Proc | null): boolean {
  return child !== null && child.exitCode === null && child.signalCode === null;
}

function kill(child: Proc | null): void {
  if (child && child.exitCode === null) child.kill("SIGTERM");
}

function launch(command: string, args: string[]): Proc | null {
  try {
    return spawn(command, args, {
      cwd: process.cwd(),
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      stdio: ["ignore", "pipe", "pipe"],
    }) as Proc;
  } catch {
    return null;
  }
}

const HUB_KEY = Symbol.for("nio.telemetry.hub");

/** Singleton across hot reloads — two consumers would fight over the socket. */
export function getTelemetryHub(): TelemetryHub {
  const holder = globalThis as unknown as Record<symbol, { hub?: TelemetryHub }>;
  if (!holder[HUB_KEY]) holder[HUB_KEY] = {};
  const slot = holder[HUB_KEY];
  if (!slot.hub) slot.hub = new TelemetryHub(resolvePaths());
  return slot.hub;
}
