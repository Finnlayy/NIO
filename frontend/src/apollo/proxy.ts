import crypto from "crypto";

const ALLOWED_ROUTES = [
  { method: "GET", pattern: /^\/api\/v1\/kanban\/tasks(\?.*)?$/ },
  { method: "POST", pattern: /^\/api\/v1\/kanban\/tasks$/ },
  { method: "GET", pattern: /^\/api\/v1\/kanban\/boards$/ },
  { method: "POST", pattern: /^\/api\/v1\/kanban\/boards$/ },
  { method: "GET", pattern: /^\/api\/v1\/workers$/ },
  { method: "POST", pattern: /^\/api\/v1\/kanban\/stop$/ }
];

export function isGenericValid(method: string, path: string): boolean {
  if (path.includes("..") || path.includes("%") || path.includes("\\") || path.includes("\0")) {
    return false;
  }
  for (const r of ALLOWED_ROUTES) {
    if (r.method === method && r.pattern.test(path)) {
      return true;
    }
  }
  return false;
}

export async function handleGenericProxy(
  path: string,
  method: string,
  payload: unknown,
  env: Record<string, string | undefined>
) {
  const token = env.NIO_KANBAN_API_TOKEN;
  if (!token) {
    return { status: 503, body: { ok: false, error: "NIO_KANBAN_API_TOKEN ist nicht gesetzt" } };
  }
  if (typeof path !== "string" || !path.startsWith("/")) {
    return { status: 400, body: { ok: false, error: "invalid path" } };
  }
  if (!isGenericValid(method, path)) {
    return { status: 403, body: { ok: false, error: "route not in allowlist" } };
  }

  const host = env.NIO_KANBAN_API_HOST || "127.0.0.1";
  const port = env.NIO_KANBAN_API_PORT || "8740";
  const url = `http://${host}:${port}${path}`;

  try {
    const fetchOptions: RequestInit = {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      signal: AbortSignal.timeout(10000)
    };
    if (method === "POST" || method === "DELETE") {
      fetchOptions.body = payload ? JSON.stringify(payload) : undefined;
    }

    const response = await fetch(url, fetchOptions);
    const text = await response.text();
    const safeText = text.replace(new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '***REDACTED***');

    return { status: response.status, rawText: safeText, headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" } };
  } catch (error) {
    return { status: 502, body: { ok: false, error: error instanceof Error ? error.message : "network error" } };
  }
}

let lockCount = 0;
let lockUntil = 0;

export async function handleSecureProxy(
  path: string,
  method: string,
  pin: string,
  payload: unknown,
  env: Record<string, string | undefined>
) {
  const token = env.NIO_KANBAN_API_TOKEN;
  const targetPin = env.NIO_APOLLO_APPROVAL_PIN;

  if (!token) {
    return { status: 503, body: { ok: false, error: "NIO_KANBAN_API_TOKEN ist nicht gesetzt" } };
  }
  if (!targetPin) {
    return { status: 503, body: { ok: false, error: "NIO_APOLLO_APPROVAL_PIN ist nicht gesetzt" } };
  }
  if (Date.now() < lockUntil) {
    return { status: 429, body: { ok: false, error: "Locked out due to too many failed attempts" } };
  }

  if (typeof pin !== "string") {
    return { status: 400, body: { ok: false, error: "invalid pin format" } };
  }

  const pinBuf = Buffer.from(pin);
  const targetBuf = Buffer.from(targetPin);
  const isPinValid = pinBuf.length === targetBuf.length && crypto.timingSafeEqual(pinBuf, targetBuf);

  if (!isPinValid) {
    lockCount++;
    if (lockCount >= 5) {
      lockUntil = Date.now() + 60000;
      lockCount = 0;
    }
    return { status: 401, body: { ok: false, error: "Ungueltige PIN" } };
  }

  lockCount = 0;
  lockUntil = 0;

  if (path.includes("..") || path.includes("%") || path.includes("\\") || path.includes("\0")) {
    return { status: 403, body: { ok: false, error: "route not in allowlist" } };
  }

  const isApproved = (method === "POST" && path === "/api/v1/approvals/issue") ||
                     (method === "DELETE" && path === "/api/v1/kanban/stop") ||
                     (method === "POST" && path === "/api/v1/workers");

  if (!isApproved) {
    return { status: 403, body: { ok: false, error: "route not in secure allowlist" } };
  }

  const host = env.NIO_KANBAN_API_HOST || "127.0.0.1";
  const port = env.NIO_KANBAN_API_PORT || "8740";
  const url = `http://${host}:${port}${path}`;

  try {
    const fetchOptions: RequestInit = {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      signal: AbortSignal.timeout(10000)
    };
    if (method === "POST" || method === "DELETE") {
      fetchOptions.body = payload ? JSON.stringify(payload) : undefined;
    }

    const response = await fetch(url, fetchOptions);
    const text = await response.text();
    const safeText = text.replace(new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '***REDACTED***');

    return { status: response.status, rawText: safeText, headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" } };
  } catch (error) {
    return { status: 502, body: { ok: false, error: error instanceof Error ? error.message : "network error" } };
  }
}
