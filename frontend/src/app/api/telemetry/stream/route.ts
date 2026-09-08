import type { NextRequest } from "next/server";
import { getTelemetryHub } from "@/server/telemetryBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Never let a proxy buffer an event stream into a stall. */
export const maxDuration = 300;

const KEEPALIVE_MS = 15_000;

/**
 * Server-Sent Events mirror of the Python UDS event bus.
 *
 * The browser cannot open an `AF_UNIX` socket, so `telemetryBridge` is the one
 * consumer of `runtime/telemetry.sock` and this route re-publishes what it
 * receives. Each client gets the ring buffer replayed first, then live records.
 *
 * Fail-closed is negotiated here, not guessed in the widget: if the hub has not
 * seen a record within `STALE_AFTER_MS` it says `state: "stale"`, and the
 * client shows a degraded badge instead of treating a frozen value as live.
 */
export async function GET(_req: NextRequest) {
  const hub = getTelemetryHub();
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let closed = false;

      const safe = (chunk: string) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(chunk));
        } catch {
          closed = true;
        }
      };

      safe(
        `event: hello\ndata: ${JSON.stringify({
          state: hub.state,
          lastAgeMs: hub.lastAgeMs,
          producerRunning: hub.producerRunning,
          consumerRunning: hub.consumerRunning,
          socket: hub.socketPath,
          logs: hub.recentLogs.slice(-8),
        })}\n\n`,
      );

      const unsubscribe = hub.attach((record) => {
        safe(`event: telemetry\ndata: ${JSON.stringify(record)}\n\n`);
      });

      // Keeps intermediaries from closing an idle stream and tells the client
      // the transport is alive even when the producer is silent.
      const keepalive = setInterval(() => {
        safe(`event: ping\ndata: ${JSON.stringify({ state: hub.state, at: Date.now() })}\n\n`);
      }, KEEPALIVE_MS);
      keepalive.unref?.();

      _req.signal.addEventListener("abort", () => {
        clearInterval(keepalive);
        unsubscribe();
        if (!closed) {
          closed = true;
          try {
            controller.close();
          } catch {
            /* already closed */
          }
        }
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
