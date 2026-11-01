import { execFile } from "node:child_process";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Apollo's way into the Obsidian vault.
 *
 * Every call runs as one intent through the orchestrator, so policy, timer and
 * event log apply exactly as for an agent. No shell: the arguments go to
 * `execFile` as a list, and the client can only pick `search` or `capture`.
 *
 * Fail-closed contract:
 *  - orchestrator or limb unreachable -> 503, never an empty result that reads like "no notes"
 *  - limb refuses                     -> 422 with its reason
 *  - JSON content type required, so another site's plain form cannot write a note
 */

const TIMEOUT_MS = 15_000;
const MAX_TEXT_CHARS = 64_000;
const MAX_QUERY_CHARS = 200;
const REPO_ROOT = path.join(process.cwd(), "..");

interface LimbReply {
  status?: string;
  output?: Record<string, unknown>;
  error?: { code?: string; message?: string } | null;
}

function refuse(error: string, status = 400) {
  return NextResponse.json({ ok: false, error }, { status });
}

function runIntent(operation: string, params: Record<string, unknown>): Promise<LimbReply> {
  const argv = [
    "-m", "orchestrator", "--json", "--quiet", "intent",
    "--op", operation, "--limb", "vault", "--goal", "Apollo vault",
    "--params", JSON.stringify(params), "--deadline", "10", "--dispatch",
  ];
  return new Promise((resolve, reject) => {
    execFile("python3", argv, { cwd: REPO_ROOT, timeout: TIMEOUT_MS, maxBuffer: 2_000_000 }, (error, stdout) => {
      try {
        resolve(JSON.parse(stdout) as LimbReply);
      } catch {
        reject(error ?? new Error("orchestrator returned no JSON"));
      }
    });
  });
}

export async function POST(request: NextRequest) {
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return refuse("expected application/json", 415);
  }
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return refuse("invalid JSON");
  }

  let operation: string;
  let params: Record<string, unknown>;
  if (body.action === "search") {
    const query = typeof body.query === "string" ? body.query.trim() : "";
    if (!query || query.length > MAX_QUERY_CHARS) return refuse("query is empty or too long");
    operation = "vault.search";
    params = { query, limit: 8 };
  } else if (body.action === "capture") {
    const text = typeof body.text === "string" ? body.text.trim() : "";
    if (!text || text.length > MAX_TEXT_CHARS) return refuse("text is empty or too long");
    operation = "vault.capture";
    params = { text, source: "apollo" };
  } else {
    return refuse("unknown action");
  }

  try {
    const reply = await runIntent(operation, params);
    if (reply.status !== "success") {
      return NextResponse.json({ ok: false, error: reply.error?.message ?? "vault refused the request" }, { status: 422 });
    }
    return NextResponse.json({ ok: true, ...reply.output });
  } catch {
    return refuse("vault_unavailable", 503);
  }
}
