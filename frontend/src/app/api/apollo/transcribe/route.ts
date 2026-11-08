import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Server-side proxy for the local speech-to-text engine (speaches).
 *
 * The endpoint comes from the server environment only, never from the client,
 * so this route cannot be pointed at another host. Audio goes to that one
 * endpoint and is not stored here.
 *
 * Fail-closed contract:
 *  - engine down    -> 503 with a hint, never an invented transcript
 *  - upstream bad   -> 502 with the reason
 *  - 45 s hard timeout, no redirect following
 */

const TIMEOUT_MS = 45_000;
const MAX_AUDIO_BYTES = 10_000_000;
const DEFAULT_ENDPOINT = "http://127.0.0.1:8011/v1/audio/transcriptions";
const DEFAULT_MODEL = "Systran/faster-whisper-small";
const DEFAULT_LANGUAGE = "de";

const PROBE_TIMEOUT_MS = 2_000;

/** Names Whisper otherwise mishears ("Polo" for Apollo). The list is shared with `limbs/speech_limb.py`. */
const VOCABULARY_FILE = path.join(process.cwd(), "..", "docs", "knowledge", "speech", "vocabulary.txt");
const FALLBACK_VOCABULARY = "Apollo, NIO, Orchestrator, Kanban-Board, Limb.";

async function vocabulary(): Promise<string> {
  try {
    return (await readFile(VOCABULARY_FILE, "utf-8")).trim() || FALLBACK_VOCABULARY;
  } catch {
    return FALLBACK_VOCABULARY;
  }
}

function endpoint(): string {
  return process.env.STT_ENDPOINT_URL?.trim() || DEFAULT_ENDPOINT;
}

function badRequest(error: string, status = 400) {
  return NextResponse.json({ ok: false, error }, { status });
}

/** Engine status for the orb. Reaches only the `/health` of the configured engine. */
export async function GET() {
  try {
    const response = await fetch(new URL("/health", endpoint()), {
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
      redirect: "error",
      cache: "no-store",
    });
    if (response.ok) return NextResponse.json({ ok: true });
  } catch {
    /* falls through to the same answer as a refused connection */
  }
  return NextResponse.json({ ok: false, error: "stt_unavailable" }, { status: 503 });
}

export async function POST(request: NextRequest) {
  if (Number(request.headers.get("content-length") ?? 0) > MAX_AUDIO_BYTES) {
    return badRequest("audio too large", 413);
  }

  let audio: FormDataEntryValue | null;
  try {
    audio = (await request.formData()).get("file");
  } catch {
    return badRequest("expected multipart form data");
  }
  if (!(audio instanceof Blob) || audio.size === 0) return badRequest("no audio");
  if (audio.size > MAX_AUDIO_BYTES) return badRequest("audio too large", 413);

  const model = process.env.STT_MODEL?.trim() || DEFAULT_MODEL;
  const upstream = new FormData();
  upstream.set("file", audio, "dictation.webm");
  upstream.set("model", model);
  upstream.set("language", process.env.STT_LANGUAGE?.trim() || DEFAULT_LANGUAGE);
  upstream.set("prompt", await vocabulary());
  upstream.set("response_format", "json");
  upstream.set("vad_filter", "true");

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const started = Date.now();

  try {
    const response = await fetch(endpoint(), {
      method: "POST",
      body: upstream,
      signal: controller.signal,
      redirect: "error",
      cache: "no-store",
    });

    const latencyMs = Date.now() - started;
    const raw = await response.text();
    if (!response.ok) {
      return NextResponse.json(
        { ok: false, error: `upstream HTTP ${response.status}`, detail: raw.slice(0, 400), latencyMs },
        { status: 502 },
      );
    }

    let text: unknown;
    try {
      text = (JSON.parse(raw) as { text?: unknown }).text;
    } catch {
      text = undefined;
    }
    if (typeof text !== "string") {
      return NextResponse.json({ ok: false, error: "upstream_not_stt_compatible", latencyMs }, { status: 502 });
    }

    return NextResponse.json({ ok: true, text: text.trim().slice(0, 12_000), model, latencyMs });
  } catch (error) {
    const latencyMs = Date.now() - started;
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json({ ok: false, error: "upstream timeout", latencyMs }, { status: 504 });
    }
    return NextResponse.json(
      {
        ok: false,
        error: "stt_unavailable",
        hint: "Start the speech engine, see docs/SPEECH.md.",
        latencyMs,
      },
      { status: 503 },
    );
  } finally {
    clearTimeout(timer);
  }
}
