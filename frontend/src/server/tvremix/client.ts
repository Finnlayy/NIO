/* ------------------------------------------------------------------ */
/* tvremix MCP client — Streamable HTTP transport (server-side only)   */
/* Talks JSON-RPC to the hosted MCP endpoint. The API key never leaves  */
/* the server; browsers talk to /api/market/* routes instead.          */
/* ------------------------------------------------------------------ */

const MCP_URL = process.env.TVREMIX_MCP_URL ?? "https://tvremix.xyz/api/mcp/v1";
const API_KEY = process.env.TVREMIX_API_KEY ?? "";

let sessionId: string | null = null;
let initPromise: Promise<void> | null = null;

/** Minimal TTL cache so the 20/min · 200/hr · 1500/day limits are respected. */
const cache = new Map<string, { at: number; ttl: number; value: unknown }>();

export function cachedGet<T>(key: string): T | undefined {
  const hit = cache.get(key);
  if (!hit) return undefined;
  if (Date.now() - hit.at > hit.ttl) {
    cache.delete(key);
    return undefined;
  }
  return hit.value as T;
}

export function cachedSet<T>(key: string, value: T, ttlMs: number) {
  cache.set(key, { at: Date.now(), ttl: ttlMs, value });
}

function parseMcpBody(raw: string): any | null {
  const text = raw.trim();
  if (!text) return null;
  // Streamable HTTP may answer as SSE even when JSON is accepted.
  if (text.startsWith("event:") || text.startsWith("data:")) {
    const dataLines = text
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trim());
    for (const line of dataLines) {
      try {
        const parsed = JSON.parse(line);
        if (parsed.result || parsed.error || parsed.method) return parsed;
      } catch {
        /* keep scanning */
      }
    }
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function rpc(method: string, params: Record<string, unknown>): Promise<any> {
  if (!API_KEY) {
    throw new McpError(503, "TVREMIX_API_KEY not configured");
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${API_KEY}`,
    "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
  };
  if (sessionId) headers["Mcp-Session-Id"] = sessionId;

  const res = await fetch(MCP_URL, {
    method: "POST",
    headers,
    body: JSON.stringify({ jsonrpc: "2.0", id: Math.floor(Math.random() * 1e9), method, params }),
    cache: "no-store",
  });

  const newSession = res.headers.get("mcp-session-id");
  if (newSession) sessionId = newSession;

  const raw = await res.text();
  const payload = parseMcpBody(raw);

  if (!res.ok || payload?.error) {
    const message = payload?.error?.message ?? `MCP ${res.status}`;
    if (res.status === 429) throw new McpError(429, `Rate limited: ${message}`);
    if (res.status === 401 || res.status === 403) throw new McpError(res.status, `Auth failed: ${message}`);
    throw new McpError(res.status || 502, message);
  }
  if (!payload) throw new McpError(502, `Unparseable MCP response: ${raw.slice(0, 200)}`);
  return payload.result;
}

/** Lazily initialize the MCP session once per server process. */
async function ensureSession() {
  if (sessionId) return;
  if (!initPromise) {
    initPromise = rpc("initialize", {
      protocolVersion: "2025-03-26",
      capabilities: {},
      clientInfo: { name: "nio-ops-grid", version: "1.0.0" },
    }).then((result) => {
      if (result?.serverInfo) {
        // notifications/initialized is optional for stateless servers; ignore failures.
      }
    });
  }
  try {
    await initPromise;
  } finally {
    // Allow re-init if it failed.
    if (!sessionId) initPromise = null;
  }
}

export class McpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "McpError";
  }
}

/**
 * Call an MCP tool by name with arguments. Returns the tool's content
 * (preferring structured content, falling back to parsed text).
 */
export async function callTool(
  name: string,
  args: Record<string, unknown>,
  ttlMs = 60_000,
): Promise<unknown> {
  const cacheKey = `tool:${name}:${JSON.stringify(args)}`;
  const cached = cachedGet<unknown>(cacheKey);
  if (cached !== undefined) return cached;

  await ensureSession();
  const result = await rpc("tools/call", { name, arguments: args });

  if (result?.isError) {
    const text = extractText(result);
    throw new McpError(502, text || `Tool ${name} returned an error`);
  }

  // Prefer structured content per the MCP spec; fall back to parsed text.
  const value =
    result?.structuredContent?.data ??
    result?.structuredContent ??
    extractParsed(result) ??
    result;
  cachedSet(cacheKey, value, ttlMs);
  return value;
}

function extractText(result: any): string {
  const content = result?.content;
  if (Array.isArray(content)) {
    return content
      .filter((c: any) => c?.type === "text")
      .map((c: any) => c.text)
      .join("\n");
  }
  return "";
}

function extractParsed(result: any): unknown {
  const text = extractText(result);
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** List tools (used by the /api/market/tools debug route). */
export async function listTools(): Promise<any> {
  const cacheKey = "tools:list";
  const cached = cachedGet<any>(cacheKey);
  if (cached) return cached;
  await ensureSession();
  const result = await rpc("tools/list", {});
  cachedSet(cacheKey, result, 5 * 60_000);
  return result;
}
