import type { NextConfig } from "next";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

// Same rules as core/envfile.py: the operator file ~/.config/nio/nio.env fills
// only variables that are not set yet, skips the checkout-bound paths, and is
// ignored unless it is owner-only. NEXT_PUBLIC_* is never taken from it, so no
// secret can reach the browser bundle. NIO_ENV_FILE=off disables this.
const CHECKOUT_KEYS = new Set(["NEU_ROOT", "NIO_REPO_ROOT", "NIO_PYTHON"]);

function loadOperatorEnv(): void {
  const configured = (process.env.NIO_ENV_FILE ?? "").trim();
  if (["off", "0", "false", "none"].includes(configured.toLowerCase())) return;
  const file = configured
    ? configured.replace(/^~(?=\/|$)/, os.homedir())
    : path.join(os.homedir(), ".config", "nio", "nio.env");
  let text: string;
  try {
    const info = fs.lstatSync(file);
    const uid = typeof process.getuid === "function" ? process.getuid() : info.uid;
    if (!info.isFile() || info.uid !== uid || (info.mode & 0o077) !== 0) {
      console.warn(`[nio-env] ${file} must be yours with mode 600; nothing loaded.`);
      return;
    }
    text = fs.readFileSync(file, "utf8");
  } catch {
    return;
  }
  for (const raw of text.split(/\r?\n/)) {
    const match = /^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$/.exec(raw.trim());
    if (!match) continue;
    const key = match[1];
    let value = match[2].trim();
    if (value.length >= 2 && value[0] === value[value.length - 1] && (value[0] === '"' || value[0] === "'")) {
      value = value.slice(1, -1);
    }
    if (CHECKOUT_KEYS.has(key) || key.startsWith("NEXT_PUBLIC_") || key in process.env) continue;
    process.env[key] = value;
  }
}

loadOperatorEnv();

const nextConfig: NextConfig = {
  turbopack: {
    root: frontendRoot,
  },
  // The dev badge sits bottom-left, exactly where the stage's task rail lives.
  devIndicators: false,
  // The sandbox preview is served from a proxied origin (*.e2b.app), and local
  // probes hit 127.0.0.1 rather than localhost. Without this the dev server
  // refuses the client chunks and the page never hydrates.
  allowedDevOrigins: ["localhost", "127.0.0.1", "*.e2b.app"],
};

export default nextConfig;
