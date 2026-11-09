/* ------------------------------------------------------------------ */
/* TradingView MCP — OAuth 2.1 (server-side only)                      */
/* Der offizielle MCP (mcp.tradingview.com) verlangt OAuth statt eines */
/* API-Keys. Ablauf: Dynamic Client Registration einmalig, dann        */
/* Authorization Code + PKCE (S256) im Browser, Refresh-Token danach    */
/* automatisch. Tokens liegen nur in einer lokalen, gitignorierten      */
/* Datei (Modus 0600) und verlassen den Server nie.                     */
/* ------------------------------------------------------------------ */

import { createHash, randomBytes } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export const MCP_URL = process.env.TRADINGVIEW_MCP_URL ?? "https://mcp.tradingview.com/mcp";
const SCOPE = process.env.TRADINGVIEW_MCP_SCOPE ?? "mcp:read mcp:tools";
/** Refresh this many ms before the access token actually expires. */
const REFRESH_SKEW_MS = 60_000;
/** A started login must be completed within this window. */
const PENDING_TTL_MS = 10 * 60_000;

/** Loopback only: the redirect URI is registered for this machine. */
export function isLoopbackHost(hostname: string): boolean {
  return /^(localhost|127\.0\.0\.1|\[::1\])$/.test(hostname);
}

export function storePath(): string {
  return process.env.TRADINGVIEW_OAUTH_STORE ?? join(process.cwd(), ".tradingview-oauth.json");
}

export interface OAuthStore {
  client_id?: string;
  client_secret?: string;
  redirect_uri?: string;
  access_token?: string;
  refresh_token?: string;
  /** Epoch ms; absent means the server gave no expiry. */
  expires_at?: number;
  scope?: string;
}

interface AuthServerMeta {
  authorization_endpoint: string;
  token_endpoint: string;
  registration_endpoint?: string;
}

export class OAuthError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "OAuthError";
  }
}

export function readStore(): OAuthStore {
  try {
    const path = storePath();
    if (!existsSync(path)) return {};
    return JSON.parse(readFileSync(path, "utf-8")) as OAuthStore;
  } catch {
    return {};
  }
}

function writeStore(store: OAuthStore) {
  writeFileSync(storePath(), JSON.stringify(store, null, 2), { encoding: "utf-8", mode: 0o600 });
}

/** Drop tokens but keep the client registration (logout). */
export function clearTokens() {
  const { client_id, client_secret, redirect_uri } = readStore();
  writeStore({ client_id, client_secret, redirect_uri });
}

/* --------------------------- Discovery ---------------------------- */

let metaPromise: Promise<AuthServerMeta> | null = null;

async function getJson(url: string): Promise<any> {
  const res = await fetch(url, { cache: "no-store", redirect: "error" });
  if (!res.ok) throw new OAuthError(502, `Discovery ${url} -> HTTP ${res.status}`);
  return res.json();
}

/** RFC 9728 (path-based) -> RFC 8414 metadata of the authorization server. */
export function discover(): Promise<AuthServerMeta> {
  if (!metaPromise) {
    metaPromise = (async () => {
      const resource = new URL(MCP_URL);
      const prm = await getJson(`${resource.origin}/.well-known/oauth-protected-resource${resource.pathname}`);
      const issuer = String(prm?.authorization_servers?.[0] ?? "").replace(/\/+$/, "");
      if (!issuer) throw new OAuthError(502, "No authorization server advertised");
      const meta = await getJson(`${issuer}/.well-known/oauth-authorization-server`);
      if (!meta?.authorization_endpoint || !meta?.token_endpoint) {
        throw new OAuthError(502, "Authorization server metadata incomplete");
      }
      return meta as AuthServerMeta;
    })().catch((err) => {
      metaPromise = null;
      throw err;
    });
  }
  return metaPromise;
}

/* ---------------------- Registration + PKCE ----------------------- */

function b64url(buf: Buffer): string {
  return buf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function pkcePair(): { verifier: string; challenge: string } {
  const verifier = b64url(randomBytes(32));
  const challenge = b64url(createHash("sha256").update(verifier).digest());
  return { verifier, challenge };
}

async function ensureClient(meta: AuthServerMeta, redirectUri: string): Promise<OAuthStore> {
  const store = readStore();
  if (store.client_id && store.redirect_uri === redirectUri) return store;
  if (!meta.registration_endpoint) throw new OAuthError(502, "Server offers no dynamic client registration");

  const res = await fetch(meta.registration_endpoint, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({
      client_name: "NIO Ops Grid",
      redirect_uris: [redirectUri],
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
      scope: SCOPE,
    }),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok || !body?.client_id) {
    throw new OAuthError(502, `Client registration failed: HTTP ${res.status} ${JSON.stringify(body).slice(0, 200)}`);
  }
  // A new registration invalidates tokens issued to the old client.
  const next: OAuthStore = { client_id: body.client_id, client_secret: body.client_secret, redirect_uri: redirectUri };
  writeStore(next);
  return next;
}

/** state -> verifier for logins in flight (per server process). */
const pending = new Map<string, { verifier: string; redirectUri: string; at: number }>();

export async function buildAuthorizeUrl(redirectUri: string): Promise<string> {
  const meta = await discover();
  const client = await ensureClient(meta, redirectUri);
  const { verifier, challenge } = pkcePair();
  const state = b64url(randomBytes(16));
  for (const [key, entry] of pending) {
    if (Date.now() - entry.at > PENDING_TTL_MS) pending.delete(key);
  }
  pending.set(state, { verifier, redirectUri, at: Date.now() });

  const url = new URL(meta.authorization_endpoint);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: client.client_id!,
    redirect_uri: redirectUri,
    code_challenge: challenge,
    code_challenge_method: "S256",
    state,
    scope: SCOPE,
    resource: MCP_URL,
  }).toString();
  return url.toString();
}

/* ----------------------------- Tokens ----------------------------- */

async function tokenRequest(params: Record<string, string>): Promise<void> {
  const meta = await discover();
  const store = readStore();
  if (!store.client_id) throw new OAuthError(401, "No registered client");
  const form = new URLSearchParams({ ...params, client_id: store.client_id, resource: MCP_URL });
  if (store.client_secret) form.set("client_secret", store.client_secret);

  const res = await fetch(meta.token_endpoint, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", accept: "application/json" },
    body: form.toString(),
    cache: "no-store",
  });
  const body = await res.json().catch(() => null);
  if (!res.ok || !body?.access_token) {
    throw new OAuthError(res.status === 400 || res.status === 401 ? 401 : 502, `Token request failed: HTTP ${res.status} ${body?.error ?? ""}`.trim());
  }
  writeStore({
    ...store,
    access_token: body.access_token,
    // Servers may rotate the refresh token; keep the old one if they don't.
    refresh_token: body.refresh_token ?? store.refresh_token,
    expires_at: typeof body.expires_in === "number" ? Date.now() + body.expires_in * 1000 : undefined,
    scope: body.scope ?? store.scope,
  });
}

export async function completeLogin(code: string, state: string): Promise<void> {
  const entry = pending.get(state);
  pending.delete(state);
  if (!entry || Date.now() - entry.at > PENDING_TTL_MS) throw new OAuthError(400, "Unknown or expired login state");
  await tokenRequest({
    grant_type: "authorization_code",
    code,
    redirect_uri: entry.redirectUri,
    code_verifier: entry.verifier,
  });
}

let refreshing: Promise<void> | null = null;

export async function refreshAccessToken(): Promise<boolean> {
  const { refresh_token } = readStore();
  if (!refresh_token) return false;
  if (!refreshing) {
    refreshing = tokenRequest({ grant_type: "refresh_token", refresh_token }).finally(() => {
      refreshing = null;
    });
  }
  try {
    await refreshing;
    return true;
  } catch {
    return false;
  }
}

/** A valid access token, refreshed if it is about to expire; null when not connected. */
export async function getAccessToken(): Promise<string | null> {
  let store = readStore();
  if (!store.access_token) return null;
  if (store.expires_at && store.expires_at - REFRESH_SKEW_MS < Date.now()) {
    if (!(await refreshAccessToken())) return null;
    store = readStore();
  }
  return store.access_token ?? null;
}

export function connectionStatus(): { connected: boolean; expiresAt: number | null; scope: string | null } {
  const store = readStore();
  return {
    connected: Boolean(store.access_token),
    expiresAt: store.expires_at ?? null,
    scope: store.scope ?? null,
  };
}
