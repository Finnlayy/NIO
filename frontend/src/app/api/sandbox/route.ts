import { execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * `/sandbox exec` — a deliberately tiny, read-only command jail.
 *
 * Rules, in order of importance:
 *  1. No shell. The command is tokenised here and run with `execFile`, so
 *     `; | && $(…) > <` are inert text, not operators.
 *  2. Allowlist of binaries. Anything else is refused before a process exists.
 *  3. Fixed working directory (`<tmp>/nio-sandbox`), created on demand.
 *     Every argument except for `echo` must stay inside it (`refuseArg`).
 *  4. Hard 5 s timeout, 64 KiB output cap, output trimmed to 8 KiB in the reply.
 *
 * This is a demo jail, not a security boundary against a hostile operator:
 * the real execution sandbox is the Python orchestrator's `workspace/`.
 */

const ALLOWED = new Set(["pwd", "ls", "cat", "echo", "date", "whoami", "head", "wc", "uname"]);
const TIMEOUT_MS = 5_000;
const MAX_BUFFER = 64 * 1024;

const JAIL = path.join(os.tmpdir(), "nio-sandbox");

async function ensureJail(): Promise<string> {
  await fs.mkdir(JAIL, { recursive: true });
  const readme = path.join(JAIL, "README.txt");
  try {
    await fs.access(readme);
  } catch {
    await fs.writeFile(
      readme,
      [
        "NIO sandbox jail",
        "",
        "`/sandbox exec` runs a read-only allowlist here: pwd, ls, cat, echo, date,",
        "whoami, head, wc, uname. No shell, no writes, no path traversal.",
        "The real execution sandbox lives in the Python orchestrator's workspace/.",
        "",
      ].join("\n"),
      "utf8",
    );
  }
  return JAIL;
}

/** Why an argument may not reach a binary, or null. Options can carry a path of their own. */
async function refuseArg(arg: string, jail: string): Promise<string | null> {
  if (arg.startsWith("--files0")) return "--files0-from is not allowed";
  const outside = "paths must stay inside the jail (no '..', no absolute paths)";
  if (arg.includes("..")) return outside;
  if (arg.startsWith("-")) return arg.includes("/") ? outside : null;
  if (arg.startsWith("/")) return outside;
  try {
    const real = await fs.realpath(path.resolve(jail, arg));
    const realJail = await fs.realpath(jail);
    if (real !== realJail && !real.startsWith(realJail + path.sep)) {
      return "paths must stay inside the jail (no symlinks outside)";
    }
  } catch {
    // Nothing there to follow; the binary reports the missing file itself.
  }
  return null;
}

/** Minimal POSIX-ish tokeniser: quotes group, nothing else is special. */
function tokenize(input: string): string[] | { error: string } {
  const tokens: string[] = [];
  let current = "";
  let quote: '"' | "'" | null = null;
  let quoted = false;
  for (const char of input) {
    if (quote) {
      if (char === quote) quote = null;
      else current += char;
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      quoted = true;
      continue;
    }
    if (/\s/.test(char)) {
      if (current || quoted) tokens.push(current);
      current = "";
      quoted = false;
      continue;
    }
    if (";|&$`<>(){}".includes(char)) {
      return { error: `shell metacharacter '${char}' is not allowed — this jail has no shell` };
    }
    current += char;
  }
  if (quote) return { error: "unterminated quote" };
  if (current || quoted) tokens.push(current);
  return tokens;
}

export async function POST(request: NextRequest) {
  let body: { command?: unknown };
  try {
    body = (await request.json()) as { command?: unknown };
  } catch {
    return NextResponse.json({ ok: false, error: "invalid JSON body" }, { status: 400 });
  }
  if (typeof body.command !== "string" || !body.command.trim()) {
    return NextResponse.json({ ok: false, error: "command is required" }, { status: 400 });
  }
  if (body.command.length > 400) {
    return NextResponse.json({ ok: false, error: "command too long" }, { status: 400 });
  }

  const tokens = tokenize(body.command.trim());
  if (!Array.isArray(tokens)) {
    return NextResponse.json({ ok: false, error: tokens.error, code: 2, mode: "jail" }, { status: 400 });
  }
  const [command, ...args] = tokens;
  if (!command || !ALLOWED.has(command)) {
    return NextResponse.json(
      {
        ok: false,
        error: `'${command ?? ""}' is not in the allowlist (${[...ALLOWED].join(", ")})`,
        code: 127,
        mode: "jail",
      },
      { status: 400 },
    );
  }

  const cwd = await ensureJail();

  if (command !== "echo") {
    for (const arg of args) {
      const refusal = await refuseArg(arg, cwd);
      if (refusal) return NextResponse.json({ ok: false, error: refusal, code: 2, mode: "jail" }, { status: 400 });
    }
  }

  return new Promise<NextResponse>((resolve) => {
    execFile(
      command,
      args.slice(0, 12),
      { cwd, timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER, killSignal: "SIGKILL", shell: false },
      (error, stdout, stderr) => {
        const code = typeof (error as { code?: unknown } | null)?.code === "number" ? (error as { code: number }).code : error ? 1 : 0;
        const killed = Boolean((error as { killed?: boolean } | null)?.killed);
        const out = (stdout || "").slice(0, 8_192);
        const err = (stderr || "").slice(0, 2_048);
        resolve(
          NextResponse.json({
            ok: !error,
            command: body.command,
            stdout: out,
            stderr: err,
            code,
            killed,
            mode: "jail",
            error: error && !out ? (killed ? `timeout after ${TIMEOUT_MS} ms` : err || error.message) : undefined,
          }),
        );
      },
    );
  });
}

export async function GET() {
  return NextResponse.json({
    ok: true,
    allowlist: [...ALLOWED],
    jail: JAIL,
    note: "read-only; no shell; 5 s timeout",
  });
}
