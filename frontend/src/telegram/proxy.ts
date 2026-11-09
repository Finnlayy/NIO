/**
 * Server side of `/api/telegram/*`: adds the operator bearer so the token never
 * reaches the browser. That also makes this route a loaded gun, so it refuses
 * anything that is not the local `/telegram` page:
 *  - a loopback Host (blocks DNS rebinding), unless `NIO_TELEGRAM_UI_HOSTS` adds one,
 *  - no cross-site requests (`Sec-Fetch-Site`, `Origin`),
 *  - writes need `x-nio-telegram`, which a foreign page cannot send without a
 *    CORS preflight that this route never answers,
 *  - only known first path segments and plain segments, so `..` cannot escape.
 *
 * `next dev` binds all interfaces and a LAN client can forge Host: start the
 * frontend with `-H 127.0.0.1` when Telegram is configured.
 */

const DEFAULT_API = "http://127.0.0.1:8740";
const MAX_BODY_BYTES = 64 * 1024;
const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);
const SEGMENT = /^[A-Za-z0-9_@-][A-Za-z0-9_@.-]*$/;

export const WRITE_HEADER = "x-nio-telegram";

const ROUTES = new Set([
  "status",
  "dialogs",
  "messages",
  "monitored",
  "pairings",
  "allowlist",
  "suggestions",
  "approvals",
  "ask",
  "signals",
  "gather",
  "events",
]);

export interface GuardInput {
  method: string;
  segments: string[];
  host: string | null;
  origin: string | null;
  fetchSite: string | null;
  writeHeader: string | null;
  extraHosts: string[];
}

export type GuardResult = { ok: true } | { ok: false; status: number; detail: string };

function hostname(host: string): string {
  const lower = host.toLowerCase();
  return lower.startsWith("[") ? lower.slice(0, lower.indexOf("]") + 1) : lower.split(":")[0];
}

export function guardRequest(input: GuardInput): GuardResult {
  const refuse = (status: number, detail: string): GuardResult => ({ ok: false, status, detail });
  if (!input.host) return refuse(403, "Host fehlt");
  const name = hostname(input.host);
  if (!LOOPBACK.has(name) && !input.extraHosts.includes(name)) return refuse(403, "Host nicht erlaubt");
  if (input.fetchSite && input.fetchSite !== "same-origin" && input.fetchSite !== "none") {
    return refuse(403, "Fremde Herkunft");
  }
  if (input.origin) {
    let originHost: string;
    try {
      originHost = new URL(input.origin).host.toLowerCase();
    } catch {
      return refuse(403, "Fremde Herkunft");
    }
    if (originHost !== input.host.toLowerCase()) return refuse(403, "Fremde Herkunft");
  }
  if (input.method !== "GET" && input.writeHeader !== "1") return refuse(403, "Schreibzugriff nur aus der Oberfläche");
  if (!ROUTES.has(input.segments[0] ?? "")) return refuse(404, "Unbekannte Route");
  if (!input.segments.every((s) => SEGMENT.test(s) && s !== "." && s !== "..")) {
    return refuse(404, "Unbekannte Route");
  }
  return { ok: true };
}

function json(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function hostList(raw: string | undefined): string[] {
  return (raw ?? "")
    .split(",")
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean);
}

type Env = Record<string, string | undefined>;

export async function proxyTelegram(req: Request, segments: string[], env: Env, doFetch: typeof fetch): Promise<Response> {
  const verdict = guardRequest({
    method: req.method,
    segments,
    host: req.headers.get("host"),
    origin: req.headers.get("origin"),
    fetchSite: req.headers.get("sec-fetch-site"),
    writeHeader: req.headers.get(WRITE_HEADER),
    extraHosts: hostList(env.NIO_TELEGRAM_UI_HOSTS),
  });
  if (!verdict.ok) return json(verdict.status, { detail: verdict.detail });

  const token = env.NIO_KANBAN_API_TOKEN;
  if (!token) return json(503, { detail: "NIO_KANBAN_API_TOKEN fehlt im Frontend", code: "no_token" });

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  let body: string | undefined;
  if (req.method === "POST") {
    body = await req.text();
    if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) return json(413, { detail: "Anfrage zu groß" });
    headers["Content-Type"] = "application/json";
  }

  const base = (env.NIO_KANBAN_API_URL || DEFAULT_API).replace(/\/+$/, "");
  const url = `${base}/api/v1/telegram/${segments.map(encodeURIComponent).join("/")}${new URL(req.url).search}`;
  let upstream: Response;
  try {
    // Kein Redirect: das Bearer-Token darf den konfigurierten Host nicht verlassen.
    upstream = await doFetch(url, { method: req.method, headers, body, redirect: "manual", cache: "no-store", signal: req.signal });
  } catch {
    return json(502, { detail: "Hermes-API nicht erreichbar", code: "backend_down" });
  }
  if (upstream.status >= 300 && upstream.status < 400) return json(502, { detail: "Unerwartete Weiterleitung", code: "backend_down" });

  const out = new Headers({ "Cache-Control": "no-store" });
  for (const name of ["content-type", "retry-after"]) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}
