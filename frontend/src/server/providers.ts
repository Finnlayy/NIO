import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
interface ProviderDefinition { id: string; name: string; secret: string; aliases?: string[]; endpoint: string; model: string; modelEnv: string; protocol: string }
async function catalogue(): Promise<ProviderDefinition[]> {
  const root = process.env.NIO_REPO_ROOT || resolve(process.cwd(), "..");
  return JSON.parse(await readFile(resolve(root, "orchestrator/provider_catalog.json"), "utf8"));
}
import { secretEnvironment } from "./secretManager";

export type ProviderState = "missing_secret" | "model_missing" | "unchecked" | "ready" | "auth_failed" | "rate_limited" | "upstream_error" | "invalid_response" | "network_error" | "timeout" | "configuration_error";
export interface ProviderStatus {
  id: string; name: string; configured: boolean; model: string;
  status: ProviderState; checkedAt?: string; latencyMs?: number; httpStatus?: number;
}
export interface ProviderConfig {
  id: string; name: string; key: string; endpoint: string; model: string; protocol: string;
}
export interface Message { role: "system" | "user" | "assistant"; content: string }
export interface Completion {
  ok: boolean; text: string; provider: string; model: string;
  error?: ProviderState; latencyMs?: number; httpStatus?: number;
}
const root = globalThis as typeof globalThis & {
  nioProviderHealth?: Map<string, { fingerprint: string; result: ProviderStatus; at: number }>;
  nioProviderProbe?: Promise<ProviderStatus[]>;
  nioProviderProbeAt?: number;
};
const health = root.nioProviderHealth ??= new Map();
const TTL = 300_000;

export async function providerConfigs(): Promise<ProviderConfig[]> {
  const env = await secretEnvironment();
  return (await catalogue()).map((provider) => {
    const key = [provider.secret, ...(provider.aliases ?? [])]
      .map((name) => env[name]?.trim()).find(Boolean) ?? "";
    let endpoint = provider.endpoint;
    if (provider.id === "freellm" && env.FREELLMAPI_HOST) {
      // The gateway is the sole explicitly configured host; never client-controlled.
      const host = env.FREELLMAPI_HOST.trim();
      const url = new URL(`http://${host}`);
      if (url.host !== host || url.username || url.password) throw new Error("invalid_gateway_host");
      const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
      endpoint = `${local ? "http" : "https"}://${host}/v1/chat/completions`;
    }
    return { id: provider.id, name: provider.name, key, endpoint,
      model: env[provider.modelEnv]?.trim() || (provider.id === env.NIO_LLM_PROVIDER ? env.APOLLO_MODEL?.trim() : "") || provider.model,
      protocol: provider.protocol };
  });
}
function fingerprint(config: ProviderConfig): string {
  return createHash("sha256").update(JSON.stringify(config)).digest("hex");
}
export function configStatus(config: ProviderConfig): ProviderStatus {
  const base: ProviderStatus = { id: config.id, name: config.name, configured: !!config.key,
    model: config.model, status: !config.key ? "missing_secret" : !config.model ? "model_missing" : "unchecked" };
  if (base.status !== "unchecked") return base;
  const saved = health.get(config.id);
  return saved && saved.fingerprint === fingerprint(config) && Date.now() - saved.at < TTL ? saved.result : base;
}
export async function providerStatuses(): Promise<ProviderStatus[]> {
  return (await providerConfigs()).map(configStatus);
}
export async function selectProvider(id?: string, endpoint?: string): Promise<ProviderConfig | undefined> {
  const env = await secretEnvironment();
  const configs = await providerConfigs();
  if (id) return configs.find((p) => p.id === id);
  if (endpoint?.trim()) {
    const target = new URL(endpoint);
    if (target.username || target.password || target.hash) return undefined;
    const found = configs.find((p) => new URL(p.endpoint).host === target.host &&
      (target.protocol === "https:" || (p.id === "freellm" && target.protocol === "http:" &&
        ["localhost", "127.0.0.1", "[::1]"].includes(target.hostname))));
    // Legacy localhost spelling is accepted for the default gateway only.
    if (!found && !env.FREELLMAPI_HOST && target.host === "localhost:3001" && target.protocol === "http:") {
      return { ...configs[0], endpoint: target.href };
    }
    return found ? { ...found, endpoint: target.href } : undefined;
  }
  if (env.NIO_LLM_PROVIDER) return configs.find((p) => p.id === env.NIO_LLM_PROVIDER);
  return configs.find((p) => p.key);
}
function redact(text: string, configs: ProviderConfig[]): string {
  return configs.reduce((value, p) => p.key ? value.split(p.key).join("[REDACTED]") : value, text);
}

/** One real request, no retry, no provider failover and no simulated response. */
export async function complete(config: ProviderConfig, messages: Message[], maxTokens = 256, temperature = 0): Promise<Completion> {
  const started = Date.now();
  const base = { provider: config.id, model: config.model };
  const save = (result: Completion): Completion => {
    const status: ProviderStatus = { id: config.id, name: config.name, configured: !!config.key,
      model: config.model, status: result.ok ? "ready" : result.error!, checkedAt: new Date().toISOString(),
      latencyMs: Date.now() - started, httpStatus: result.httpStatus };
    health.set(config.id, { fingerprint: fingerprint(config), result: status, at: Date.now() });
    return { ...result, latencyMs: status.latencyMs };
  };
  if (!config.key) return save({ ...base, ok: false, text: "", error: "missing_secret" });
  if (!config.model) return save({ ...base, ok: false, text: "", error: "model_missing" });
  const headers: Record<string, string> = { "content-type": "application/json" };
  const body: Record<string, unknown> = { model: config.model, messages, temperature, max_tokens: Math.min(4096, Math.max(16, maxTokens)), stream: false };
  if (config.protocol === "anthropic") {
    headers["x-api-key"] = config.key;
    headers["anthropic-version"] = "2023-06-01";
    body.system = messages.filter((m) => m.role === "system").map((m) => m.content).join("\n");
    body.messages = messages.filter((m) => m.role !== "system");
  } else headers.authorization = `Bearer ${config.key}`;
  try {
    const response = await fetch(config.endpoint, { method: "POST", headers, body: JSON.stringify(body),
      signal: AbortSignal.timeout(20_000), redirect: "error", cache: "no-store" });
    if (!response.ok) {
      return save({ ...base, ok: false, text: "", httpStatus: response.status,
        error: [401, 403].includes(response.status) ? "auth_failed" : response.status === 429 ? "rate_limited" : "upstream_error" });
    }
    const raw = await response.text();
    let text: unknown;
    try {
      const data = JSON.parse(raw);
      text = config.protocol === "anthropic" ? data.content?.find((part: { type: string }) => part.type === "text")?.text
        : config.protocol === "cohere" ? data.message?.content?.find((part: { type: string }) => part.type === "text")?.text
        : data.choices?.[0]?.message?.content;
    } catch { /* invalid response stays an error, never echoed to the browser */ }
    if (typeof text !== "string" || !text.trim()) return save({ ...base, ok: false, text: "", error: "invalid_response", httpStatus: response.status });
    return save({ ...base, ok: true, text: redact(text.trim(), await providerConfigs()).slice(0, 12_000), httpStatus: response.status });
  } catch (error) {
    return save({ ...base, ok: false, text: "", error: error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name) ? "timeout" : "network_error" });
  }
}

/** Explicit paid operation; cached for 30 s to bound duplicate clicks. GET never probes. */
export async function probeProviders(): Promise<ProviderStatus[]> {
  if (root.nioProviderProbe) return root.nioProviderProbe;
  if (root.nioProviderProbeAt && Date.now() - root.nioProviderProbeAt < 30_000) return providerStatuses();
  root.nioProviderProbe = (async () => {
    const configs = await providerConfigs();
    await Promise.all(configs.filter((p) => p.key && p.model).map((p) => complete(p, [{ role: "user", content: "Reply with OK." }], 16)));
    root.nioProviderProbeAt = Date.now();
    return providerStatuses();
  })();
  try { return await root.nioProviderProbe; } finally { root.nioProviderProbe = undefined; }
}
