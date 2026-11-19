import { secretEnvironment } from "@/server/secretManager";
import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Server-seitiger Proxy auf die Control-Plane-Routen `/api/runtime/...` der Kanban-API.
 *
 * Regeln, nach Wichtigkeit:
 *  1. Das Operator-Token (`NIO_KANBAN_API_TOKEN`) kommt aus der Server-Umgebung und
 *     gelangt nie in eine Browser-Antwort oder in eine URL.
 *  2. Allowlist: nur die fünf Pfadmuster unten; jede andere Kombination ist 404,
 *     bevor überhaupt eine Verbindung entsteht.
 *  3. Fail-closed: ohne Token 503, wie die Kanban-API selbst.
 *  4. Der SSE-Strom (`approvals/stream`) wird durchgereicht und endet mit dem Browser.
 */

type Method = "GET" | "POST";

interface Rule {
  method: Method;
  pattern: RegExp;
}

const ID = "[A-Za-z0-9_.:-]{1,128}";
const ID_RE = new RegExp(`^${ID}$`);
const ALLOWED: Rule[] = [
  { method: "GET", pattern: new RegExp(`^session/${ID}/dag$`) },
  { method: "POST", pattern: new RegExp(`^session/${ID}/(undo|retry|abort)$`) },
  { method: "GET", pattern: /^approvals\/pending$/ },
  { method: "GET", pattern: /^approvals\/stream$/ },
  { method: "POST", pattern: new RegExp(`^approvals/${ID}/resolve$`) },
];
const STREAM_PATH = "approvals/stream";
const MAX_BODY_BYTES = 4096;
const TIMEOUT_MS = 10_000;

function isAllowed(method: Method, segments: string[]): boolean {
  // `.` und `..` passen auf das ID-Muster, sind aber nie ein gültiges Segment.
  if (segments.some((segment) => segment === "." || segment === "..")) return false;
  const joined = segments.join("/");
  return ALLOWED.some((rule) => rule.method === method && rule.pattern.test(joined));
}

function jsonError(status: number, error: string): NextResponse {
  return NextResponse.json({ ok: false, error }, { status });
}

async function forward(request: NextRequest, segments: string[]): Promise<Response> {
  const method: Method = request.method === "GET" ? "GET" : "POST";
  if (!isAllowed(method, segments)) return jsonError(404, "Route nicht freigegeben");

  let env: Record<string, string | undefined>;
  try {
    env = await secretEnvironment();
  } catch {
    return jsonError(503, "secret_store_unavailable_or_invalid");
  }
  const token = env.NIO_KANBAN_API_TOKEN;
  if (!token) return jsonError(503, "NIO_KANBAN_API_TOKEN ist nicht gesetzt");

  const base =
    env.NIO_KANBAN_API_URL || `http://${env.NIO_KANBAN_API_HOST || "127.0.0.1"}:${env.NIO_KANBAN_API_PORT || "8740"}`;
  const url = new URL(`/api/runtime/${segments.map(encodeURIComponent).join("/")}`, base);

  // Query: nur session_id, und nur als sicherer Wert.
  const sessionId = request.nextUrl.searchParams.get("session_id");
  if (sessionId !== null) {
    if (!ID_RE.test(sessionId)) return jsonError(400, "session_id ungültig");
    url.searchParams.set("session_id", sessionId);
  }

  let body: string | undefined;
  if (method === "POST") {
    body = await request.text();
    if (Buffer.byteLength(body, "utf8") > MAX_BODY_BYTES) return jsonError(413, "Body zu groß");
  }

  const isStream = segments.join("/") === STREAM_PATH;
  const headers: Record<string, string> = {
    authorization: `Bearer ${token}`,
    accept: isStream ? "text/event-stream" : "application/json",
  };
  if (body !== undefined) headers["content-type"] = "application/json";

  try {
    const upstream = await fetch(url, {
      method,
      headers,
      body,
      cache: "no-store",
      // Der Strom läuft, bis der Browser die Verbindung schließt; alles andere hat ein Zeitlimit.
      signal: isStream ? request.signal : AbortSignal.timeout(TIMEOUT_MS),
    });
    if (isStream) {
      return new Response(upstream.body, {
        status: upstream.status,
        headers: { "content-type": "text/event-stream", "cache-control": "no-cache, no-transform" },
      });
    }
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return jsonError(502, "Kanban-API nicht erreichbar");
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return forward(request, path);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return forward(request, path);
}
