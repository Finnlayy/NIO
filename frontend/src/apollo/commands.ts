import type { NodeCategory } from "./types";

/* ==================================================================== */
/* Hybrid CLI parser                                                     */
/*                                                                       */
/* Pure: text in, intent out. The store is what turns an intent into a   */
/* side effect, so every command can be tested without a DOM.            */
/* ==================================================================== */

export type ParsedCommand =
  | { kind: "spawn"; type: NodeCategory; name: string }
  | { kind: "dispatch"; nodeId: string; payload: Record<string, unknown> }
  | { kind: "failover-simulate" }
  | { kind: "router-status" }
  | { kind: "config-set"; key: string; value: string | number | boolean; raw: string }
  | { kind: "sandbox-exec"; command: string }
  | { kind: "clear" }
  | { kind: "help" }
  | { kind: "unknown"; input: string }
  | { kind: "error"; message: string; hint?: string };

export const COMMANDS = [
  { command: "/spawn", usage: "/spawn <type> <name>", detail: "Lymp mitosis: grow a new neural node" },
  { command: "/dispatch", usage: "/dispatch <node_id> <json>", detail: "fire an axon impulse from Apollo" },
  { command: "/failover", usage: "/failover simulate", detail: "drain the primary quota, hot-swap to FreeLLMAPI" },
  { command: "/router", usage: "/router status", detail: "providers, pool estimates, score ranking" },
  { command: "/config", usage: "/config set <key> <value>", detail: "mutate Apollo runtime parameters" },
  { command: "/sandbox", usage: "/sandbox exec <cmd>", detail: "run a read-only command in the sandbox jail" },
  { command: "/clear", usage: "/clear", detail: "flush terminal history" },
  { command: "/help", usage: "/help", detail: "list commands" },
] as const;

const CATEGORY_ALIASES: Record<string, NodeCategory> = {
  orchestrator: "ORCHESTRATOR",
  orch: "ORCHESTRATOR",
  router: "FREELLM_ROUTER",
  freellm: "FREELLM_ROUTER",
  llm: "FREELLM_ROUTER",
  sandbox: "SANDBOX",
  exec: "SANDBOX",
  mcp: "MCP_WORKER",
  worker: "MCP_WORKER",
  data: "DATA_STREAM",
  stream: "DATA_STREAM",
  inference: "INFERENCE",
  infer: "INFERENCE",
  model: "INFERENCE",
  memory: "MEMORY",
  vault: "MEMORY",
};

export const MUTABLE_CONFIG_KEYS = [
  "temperature",
  "maxTokens",
  "primaryQuotaPercent",
  "primaryModel",
  "executionPolicy",
  "allowDynamicNodeSpawn",
  "allowAppMutation",
  "systemDirective",
] as const;

export type MutableConfigKey = (typeof MUTABLE_CONFIG_KEYS)[number];

const BOOLEAN_KEYS = new Set(["allowDynamicNodeSpawn", "allowAppMutation"]);
const NUMBER_KEYS: Record<string, { min: number; max: number; integer?: boolean }> = {
  temperature: { min: 0, max: 2 },
  maxTokens: { min: 256, max: 1_000_000, integer: true },
  primaryQuotaPercent: { min: 0, max: 100 },
};
const POLICIES = new Set(["AUTONOMOUS", "CONSERVATIVE", "SANDBOX_STRICT"]);

function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  const prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    let diagonal = prev[0];
    prev[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const temp = prev[j];
      prev[j] = Math.min(prev[j] + 1, prev[j - 1] + 1, diagonal + (a[i - 1] === b[j - 1] ? 0 : 1));
      diagonal = temp;
    }
  }
  return prev[b.length];
}

/** Nearest command name, used for "did you mean" hints. */
export function suggestCommand(token: string): string | null {
  const normalized = token.toLowerCase();
  let best: { name: string; distance: number } | null = null;
  for (const entry of COMMANDS) {
    const distance = levenshtein(normalized, entry.command);
    if (!best || distance < best.distance) best = { name: entry.command, distance };
  }
  return best && best.distance <= 3 ? best.name : null;
}

function splitHead(text: string): [string, string] {
  const trimmed = text.trim();
  const match = /^(\S+)\s*([\s\S]*)$/.exec(trimmed);
  if (!match) return ["", ""];
  return [match[1].toLowerCase(), match[2].trim()];
}

/** Coerce a CLI string to the type the configuration key expects. */
export function coerceConfigValue(
  key: string,
  raw: string,
): { ok: true; value: string | number | boolean } | { ok: false; message: string } {
  const text = raw.trim();
  if (!(MUTABLE_CONFIG_KEYS as readonly string[]).includes(key)) {
    return {
      ok: false,
      message: `unknown key '${key}' — allowed: ${MUTABLE_CONFIG_KEYS.join(", ")}`,
    };
  }
  if (BOOLEAN_KEYS.has(key)) {
    if (/^(true|on|1|yes)$/i.test(text)) return { ok: true, value: true };
    if (/^(false|off|0|no)$/i.test(text)) return { ok: true, value: false };
    return { ok: false, message: `${key} expects true|false, got '${text}'` };
  }
  if (key === "executionPolicy") {
    const upper = text.toUpperCase().replace(/-/g, "_");
    if (POLICIES.has(upper)) return { ok: true, value: upper };
    return { ok: false, message: `executionPolicy expects ${[...POLICIES].join(" | ")}` };
  }
  if (key === "primaryModel" || key === "systemDirective") {
    if (!text) return { ok: false, message: `${key} must not be empty` };
    return { ok: true, value: text };
  }
  const bounds = NUMBER_KEYS[key];
  const value = Number(text);
  if (!bounds) {
    if (!Number.isFinite(value)) return { ok: false, message: `${key} expects a number` };
    return { ok: true, value };
  }
  if (!Number.isFinite(value)) return { ok: false, message: `${key} expects a number, got '${text}'` };
  if (bounds.integer && !Number.isInteger(value)) {
    return { ok: false, message: `${key} must be an integer` };
  }
  if (value < bounds.min || value > bounds.max) {
    return { ok: false, message: `${key} must be between ${bounds.min} and ${bounds.max}` };
  }
  return { ok: true, value };
}

export function parseCommand(input: string): ParsedCommand {
  const text = input.trim();
  if (!text) return { kind: "error", message: "empty command" };
  if (!text.startsWith("/")) return { kind: "unknown", input: text };

  const [head, rest] = splitHead(text);
  switch (head) {
    case "/spawn": {
      const [typeToken = "", ...nameParts] = rest.split(/\s+/).filter(Boolean);
      const type = CATEGORY_ALIASES[typeToken.toLowerCase()];
      if (!typeToken) {
        return { kind: "error", message: "/spawn needs a node type", hint: "e.g. /spawn inference Vision Cortex" };
      }
      if (!type) {
        return {
          kind: "error",
          message: `unknown node type '${typeToken}'`,
          hint: `types: ${[...new Set(Object.keys(CATEGORY_ALIASES))].join(", ")}`,
        };
      }
      const name = nameParts.join(" ").trim() || `${typeToken} node`;
      return { kind: "spawn", type, name };
    }
    case "/dispatch": {
      const [nodeId = "", ...payloadParts] = rest.split(/\s+/);
      if (!nodeId) {
        return { kind: "error", message: "/dispatch needs a node id", hint: "e.g. /dispatch node-mcp {\"tool\":\"fetch\"}" };
      }
      const rawPayload = rest.slice(nodeId.length).trim();
      if (!rawPayload) return { kind: "dispatch", nodeId, payload: {} };
      let parsed: unknown;
      try {
        parsed = JSON.parse(rawPayload);
      } catch {
        return { kind: "error", message: "payload is not valid JSON", hint: 'e.g. {"tool":"fetch","url":"…"}' };
      }
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        return { kind: "error", message: "payload must be a JSON object" };
      }
      return { kind: "dispatch", nodeId, payload: parsed as Record<string, unknown> };
    }
    case "/failover": {
      if (/^simulate$/i.test(rest) || rest === "") return { kind: "failover-simulate" };
      return { kind: "error", message: "usage: /failover simulate" };
    }
    case "/router": {
      if (/^status$/i.test(rest) || rest === "") return { kind: "router-status" };
      return { kind: "error", message: "usage: /router status" };
    }
    case "/config": {
      const [verb = "", key = "", ...valueParts] = rest.split(/\s+/);
      if (verb.toLowerCase() !== "set" || !key) {
        return { kind: "error", message: "usage: /config set <key> <value>", hint: MUTABLE_CONFIG_KEYS.join(", ") };
      }
      const raw = valueParts.join(" ");
      const coerced = coerceConfigValue(key, raw);
      if (!coerced.ok) return { kind: "error", message: coerced.message };
      return { kind: "config-set", key, value: coerced.value, raw };
    }
    case "/sandbox": {
      const [verb = "", ...cmdParts] = rest.split(/\s+/);
      const command = cmdParts.join(" ").trim();
      if (verb.toLowerCase() !== "exec" || !command) {
        return { kind: "error", message: "usage: /sandbox exec <cmd>", hint: "read-only allowlist: pwd, ls, cat, echo, date, whoami" };
      }
      return { kind: "sandbox-exec", command };
    }
    case "/clear":
      return { kind: "clear" };
    case "/help":
    case "/?":
      return { kind: "help" };
    default: {
      const suggestion = suggestCommand(head);
      return {
        kind: "error",
        message: `unknown command '${head}'`,
        hint: suggestion ? `did you mean ${suggestion}? (try /help)` : "try /help",
      };
    }
  }
}
