// Starts the local services Apollo needs, together with Apollo.
//
// Runs as npm "predev"/"prestart". It never fails the UI start: whatever cannot
// start prints one line, and Apollo comes up with that part marked offline.
//
// - speaches (dictation): starts the existing container named by
//   NIO_SPEECH_CONTAINER (default "speaches"); setup in docs/SPEECH.md.
//   NIO_SPEECH_AUTOSTART=off disables it.
// - Kanban (chat tasks): if nothing listens on NIO_KANBAN_API_PORT (8740),
//   starts `python3 -m orchestrator kanban serve` from this checkout, detached,
//   logging to ~/.local/state/nio/kanban.log. It loads ~/.config/nio/nio.env
//   itself. NIO_KANBAN_AUTOSTART=off disables it.
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const disabled = (name) => ["off", "0", "false", "none"].includes((process.env[name] ?? "").trim().toLowerCase());

function docker(args) {
  return execFileSync("docker", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 20_000 }).trim();
}

function ensureSpeech() {
  if (disabled("NIO_SPEECH_AUTOSTART")) return;
  const container = (process.env.NIO_SPEECH_CONTAINER ?? "speaches").trim() || "speaches";
  let running;
  try {
    running = docker(["inspect", "--format", "{{.State.Running}}", container]);
  } catch {
    console.warn(`[nio-speech] Container "${container}" nicht gefunden oder Docker nicht erreichbar. Einrichtung: docs/SPEECH.md`);
    return;
  }
  if (running === "true") {
    console.log(`[nio-speech] ${container} laeuft bereits.`);
    return;
  }
  try {
    docker(["start", container]);
    console.log(`[nio-speech] ${container} gestartet (127.0.0.1:8011).`);
  } catch (error) {
    const detail = error instanceof Error ? error.message.split("\n")[0] : String(error);
    console.warn(`[nio-speech] ${container} konnte nicht starten: ${detail}`);
  }
}

function listening(host, port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port, timeout: 500 });
    const done = (result) => { socket.destroy(); resolve(result); };
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
  });
}

async function ensureKanban() {
  if (disabled("NIO_KANBAN_AUTOSTART")) return;
  const host = (process.env.NIO_KANBAN_API_HOST ?? "").trim() || "127.0.0.1";
  const port = Number(process.env.NIO_KANBAN_API_PORT) || 8740;
  if (await listening(host, port)) {
    console.log(`[nio-kanban] API laeuft bereits auf ${host}:${port}.`);
    return;
  }
  const logDir = path.join(os.homedir(), ".local", "state", "nio");
  fs.mkdirSync(logDir, { recursive: true });
  const log = fs.openSync(path.join(logDir, "kanban.log"), "a");
  const python = (process.env.NIO_KANBAN_PYTHON ?? "").trim() || "python3";
  const child = spawn(python, ["-m", "orchestrator", "kanban", "serve"], {
    cwd: repoRoot, detached: true, stdio: ["ignore", log, log],
  });
  child.on("error", (error) => console.warn(`[nio-kanban] Start fehlgeschlagen: ${error.message}`));
  child.unref();
  for (let i = 0; i < 20; i += 1) {
    if (await listening(host, port)) {
      console.log(`[nio-kanban] API gestartet auf ${host}:${port} (Log: ~/.local/state/nio/kanban.log).`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  console.warn("[nio-kanban] API antwortet nicht nach 10 s. Log: ~/.local/state/nio/kanban.log");
}

ensureSpeech();
await ensureKanban();
