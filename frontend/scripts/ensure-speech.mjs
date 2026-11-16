// Starts the local speech engine (speaches) together with Apollo.
//
// Runs as npm "predev"/"prestart". It only starts an existing container named
// by NIO_SPEECH_CONTAINER (default "speaches"); creating one is documented in
// docs/SPEECH.md. It never fails the UI start: without Docker or the container
// it prints one line and Apollo comes up with dictation marked offline.
// NIO_SPEECH_AUTOSTART=off disables it.
import { execFileSync } from "node:child_process";

const setting = (process.env.NIO_SPEECH_AUTOSTART ?? "").trim().toLowerCase();
const container = (process.env.NIO_SPEECH_CONTAINER ?? "speaches").trim() || "speaches";

function docker(args) {
  return execFileSync("docker", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 20_000 }).trim();
}

function main() {
  if (["off", "0", "false", "none"].includes(setting)) return;
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

main();
