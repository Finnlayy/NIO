import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Server-side proxy for the FreeLLMAPI / OpenAI-compatible endpoint.
 *
 * Why this exists at all: the browser must never hold provider keys, and it
 * must never talk to a third-party origin directly from the tab. The operator
 * configures one base URL; this route adds the credential (from the server
 * environment only) and returns just the assistant text.
 *
 * Fail-closed contract:
 *  - no endpoint  -> 400, the client falls back to labelled local synthesis
 *  - upstream bad -> 502 with the reason, never an invented answer
 *  - 20 s hard timeout, no redirect following, no streaming
 */

const TIMEOUT_MS = 20_000;
const MAX_BODY = 512_000;
const MAX_MESSAGES = 24;

interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface ProxyPayload {
  endpointUrl?: unknown;
  model?: unknown;
  messages?: unknown;
  temperature?: unknown;
  maxTokens?: unknown;
}

function badRequest(error: string) {
  return NextResponse.json({ ok: false, error }, { status: 400 });
}

function validate(payload: ProxyPayload): { url: URL; messages: ChatMessage[]; model: string; temperature: number; maxTokens: number } | { error: string } {
  if (typeof payload.endpointUrl !== "string" || !payload.endpointUrl.trim()) {
    return { error: "no_endpoint" };
  }
  let url: URL;
  try {
    url = new URL(payload.endpointUrl.trim());
  } catch {
    return { error: "endpoint is not a URL" };
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return { error: "endpoint must be http(s)" };
  }

  const rawMessages = Array.isArray(payload.messages) ? payload.messages : [];
  const messages: ChatMessage[] = [];
  for (const entry of rawMessages.slice(0, MAX_MESSAGES)) {
    if (!entry || typeof entry !== "object") continue;
    const item = entry as Record<string, unknown>;
    const role = item.role;
    const content = item.content;
    if (role !== "system" && role !== "user" && role !== "assistant") continue;
    if (typeof content !== "string") continue;
    messages.push({ role, content: content.slice(0, 24_000) });
  }
  if (messages.length === 0) return { error: "no messages" };

  const temperature = typeof payload.temperature === "number" ? Math.min(2, Math.max(0, payload.temperature)) : 0.4;
  const maxTokens =
    typeof payload.maxTokens === "number" ? Math.min(4096, Math.max(16, Math.round(payload.maxTokens))) : 1024;
  const model = typeof payload.model === "string" && payload.model.trim() ? payload.model.trim() : "gpt-4o-mini";

  return { url, messages, model, temperature, maxTokens };
}

/** Optional server-side credential; never accepted from the client. */
function authHeaders(url: URL): Record<string, string> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  const keys: Array<[RegExp, string | undefined]> = [
    [/openrouter/i, process.env.OPENROUTER_API_KEY],
    [/groq/i, process.env.GROQ_API_KEY],
    [/googleapis|generativelanguage/i, process.env.GOOGLE_API_KEY],
    [/mistral/i, process.env.MISTRAL_API_KEY],
    [/cerebras/i, process.env.CEREBRAS_API_KEY],
  ];
  for (const [pattern, key] of keys) {
    if (key && pattern.test(url.host)) {
      headers.authorization = `Bearer ${key}`;
      return headers;
    }
  }
  if (process.env.FREELLMAPI_KEY) headers.authorization = `Bearer ${process.env.FREELLMAPI_KEY}`;
  return headers;
}

export async function POST(request: NextRequest) {
  let payload: ProxyPayload;
  try {
    const text = await request.text();
    if (text.length > MAX_BODY) return badRequest("payload too large");
    payload = JSON.parse(text) as ProxyPayload;
  } catch {
    return badRequest("invalid JSON body");
  }

  const checked = validate(payload);
  if ("error" in checked) {
    return NextResponse.json(
      {
        ok: false,
        error: checked.error,
        hint:
          checked.error === "no_endpoint"
            ? "Set a FreeLLMAPI proxy endpoint in the deck to answer live; empty means local simulation."
            : undefined,
      },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const started = Date.now();

  try {
    const response = await fetch(checked.url, {
      method: "POST",
      headers: authHeaders(checked.url),
      body: JSON.stringify({
        model: checked.model,
        messages: checked.messages,
        temperature: checked.temperature,
        max_tokens: checked.maxTokens,
        stream: false,
      }),
      signal: controller.signal,
      redirect: "error",
      cache: "no-store",
    });

    const latencyMs = Date.now() - started;
    const raw = await response.text();
    if (!response.ok) {
      return NextResponse.json(
        {
          ok: false,
          error: `upstream HTTP ${response.status}`,
          detail: raw.slice(0, 400),
          latencyMs,
        },
        { status: 502 },
      );
    }

    // Fail closed: only a real OpenAI-compatible completion is an answer. A 200
    // that carries HTML (wrong URL, captive portal, a web page) must not be
    // pasted into the chat as if a model had said it.
    let text = "";
    try {
      const parsed = JSON.parse(raw) as {
        choices?: Array<{ message?: { content?: string }; text?: string }>;
        provider?: string;
      };
      text = parsed.choices?.[0]?.message?.content ?? parsed.choices?.[0]?.text ?? "";
      if (!Array.isArray(parsed.choices)) {
        return NextResponse.json(
          {
            ok: false,
            error: "upstream_not_openai_compatible",
            detail: "response has no `choices` array",
            latencyMs,
          },
          { status: 502 },
        );
      }
    } catch {
      return NextResponse.json(
        {
          ok: false,
          error: "upstream_not_json",
          detail: raw.slice(0, 160).replace(/\s+/g, " "),
          latencyMs,
        },
        { status: 502 },
      );
    }
    if (!text.trim()) {
      return NextResponse.json({ ok: false, error: "empty_upstream_response", latencyMs }, { status: 502 });
    }

    return NextResponse.json({
      ok: true,
      text: text.slice(0, 12_000),
      provider: checked.url.host,
      model: checked.model,
      latencyMs,
    });
  } catch (error) {
    const latencyMs = Date.now() - started;
    const aborted = error instanceof Error && error.name === "AbortError";
    return NextResponse.json(
      {
        ok: false,
        error: aborted ? "upstream timeout" : error instanceof Error ? error.message : "network error",
        latencyMs,
      },
      { status: 504 },
    );
  } finally {
    clearTimeout(timer);
  }
}

export async function GET() {
  return NextResponse.json({
    ok: true,
    configured:
      Boolean(process.env.FREELLMAPI_KEY) ||
      Boolean(process.env.OPENROUTER_API_KEY) ||
      Boolean(process.env.GROQ_API_KEY),
    note: "POST an OpenAI-compatible chat completion here; keys stay server-side.",
  });
}
