import { NextResponse, type NextRequest } from "next/server";
import { complete, providerStatuses, selectProvider, type Message } from "@/server/providers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** All credentials and provider selection are resolved server-side. Fail closed. */
export async function POST(request: NextRequest) {
  let payload: Record<string, unknown>;
  try {
    const raw = await request.text();
    if (raw.length > 512_000) return NextResponse.json({ ok: false, error: "payload_too_large" }, { status: 413 });
    const data: unknown = JSON.parse(raw);
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error();
    payload = data as Record<string, unknown>;
  } catch { return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 }); }
  const messages: Message[] = [];
  if (Array.isArray(payload.messages)) {
    for (const item of payload.messages.slice(-24)) {
      if (item && ["system", "user", "assistant"].includes(item.role) && typeof item.content === "string") {
        messages.push({ role: item.role, content: item.content.slice(0, 24_000) });
      }
    }
  }
  if (!messages.length) return NextResponse.json({ ok: false, error: "no_messages" }, { status: 400 });
  try {
    const endpoint = typeof payload.endpointUrl === "string" ? payload.endpointUrl : undefined;
    const providerId = typeof payload.providerId === "string" ? payload.providerId : undefined;
    let config;
    try { config = await selectProvider(providerId, endpoint); }
    catch { return NextResponse.json({ ok: false, error: "configuration_error" }, { status: 503 }); }
    if (!config) return NextResponse.json({ ok: false, error: endpoint ? "forbidden target host" : "no_provider_configured" }, { status: endpoint ? 403 : 503 });
    // Legacy gateway callers may supply a model; direct providers use the server catalogue.
    if (!config.model && config.id === "freellm" && typeof payload.model === "string") config.model = payload.model.trim();
    const maxTokens = typeof payload.maxTokens === "number" && Number.isFinite(payload.maxTokens) ? Math.round(payload.maxTokens) : 256;
    const temperature = typeof payload.temperature === "number" && Number.isFinite(payload.temperature) ? Math.min(2, Math.max(0, payload.temperature)) : 0;
    const result = await complete(config, messages, maxTokens, temperature);
    return NextResponse.json(result, { status: result.ok ? 200 : ["missing_secret", "model_missing"].includes(result.error ?? "") ? 503 : result.error === "timeout" ? 504 : 502 });
  } catch { return NextResponse.json({ ok: false, error: "secret_store_unavailable_or_invalid" }, { status: 503 }); }
}

/** Presence is not health. Only a successful completion earns status=ready. */
export async function GET() {
  try {
    const providers = await providerStatuses();
    return NextResponse.json({ ok: true, configured: providers.some((p) => p.configured),
      ready: providers.some((p) => p.status === "ready"), providers }, { headers: { "Cache-Control": "no-store" } });
  } catch { return NextResponse.json({ ok: false, configured: false, ready: false, error: "secret_store_unavailable_or_invalid" }, { status: 503 }); }
}
