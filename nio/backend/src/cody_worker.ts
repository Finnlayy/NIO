import { spawn, type ChildProcess } from 'child_process';
import { existsSync } from 'fs';
import { resolve } from 'path';
import { getWorkspaceRoot } from './cody_stats';

let child: ChildProcess | null = null;
let shuttingDown = false;

/** True when Cody Telegram poller should run alongside NIO. */
export function isCodyWorkerEnabled(): boolean {
  const explicit = process.env.CODY_ENABLED?.trim().toLowerCase();
  if (explicit === '0' || explicit === 'false' || explicit === 'off') return false;
  if (explicit === '1' || explicit === 'true' || explicit === 'on') return true;
  return Boolean(process.env.TELEGRAM_BOT_TOKEN?.trim());
}

function pipeWithPrefix(stream: NodeJS.ReadableStream | null): void {
  if (!stream) return;
  let buffer = '';
  stream.on('data', (chunk: Buffer | string) => {
    buffer += chunk.toString();
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (line.length > 0) {
        console.log(`[Cody] ${line}`);
      }
    }
  });
  stream.on('end', () => {
    if (buffer.length > 0) {
      console.log(`[Cody] ${buffer}`);
    }
  });
}

function buildChildEnv(workspaceRoot: string): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env, WORKSPACE_ROOT: workspaceRoot };

  if (!env.TELEGRAM_NOTIFICATIONS_ENABLED) {
    env.TELEGRAM_NOTIFICATIONS_ENABLED = 'true';
  }

  if (!env.NIO_API_URL?.trim()) {
    const port = process.env.PORT ?? '4000';
    const host = process.env.HOST ?? 'localhost';
    const connectHost = host === '0.0.0.0' ? 'localhost' : host;
    env.NIO_API_URL = `http://${connectHost}:${port}`;
  }

  return env;
}

/** Spawn `python telegram_notify.py serve` after NIO is listening. */
export function startCodyWorker(): void {
  if (!isCodyWorkerEnabled()) {
    console.log('[Cody] Worker disabled (set TELEGRAM_BOT_TOKEN or CODY_ENABLED=true to enable)');
    return;
  }

  if (child) {
    console.warn('[Cody] Worker already running');
    return;
  }

  const workspaceRoot = getWorkspaceRoot();
  const scriptPath = resolve(workspaceRoot, 'telegram_notify.py');
  if (!existsSync(scriptPath)) {
    console.error(`[Cody] telegram_notify.py not found at ${scriptPath}`);
    return;
  }

  const python = process.env.CODY_PYTHON?.trim() || 'python';
  const env = buildChildEnv(workspaceRoot);

  if (!env.TELEGRAM_BOT_TOKEN?.trim() || !env.TELEGRAM_CHAT_ID?.trim()) {
    console.warn('[Cody] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing — poller may exit immediately');
  }

  child = spawn(python, [scriptPath, 'serve'], {
    cwd: workspaceRoot,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  console.log(
    `[Cody] Started Telegram poller (pid ${child.pid ?? 'unknown'}, NIO_API_URL=${env.NIO_API_URL})`,
  );

  pipeWithPrefix(child.stdout);
  pipeWithPrefix(child.stderr);

  child.on('error', (err) => {
    console.error('[Cody] Failed to start:', err.message);
    child = null;
  });

  child.on('exit', (code, signal) => {
    if (!shuttingDown) {
      console.warn(`[Cody] Process exited (code=${code ?? 'null'}, signal=${signal ?? 'null'})`);
    }
    child = null;
  });
}

/** Gracefully stop the Cody child process. */
export function stopCodyWorker(): Promise<void> {
  return new Promise((resolvePromise) => {
    if (!child) {
      resolvePromise();
      return;
    }

    shuttingDown = true;
    const proc = child;
    const forceKill = setTimeout(() => {
      if (!proc.killed) {
        proc.kill('SIGKILL');
      }
    }, 5000);

    proc.once('exit', () => {
      clearTimeout(forceKill);
      child = null;
      shuttingDown = false;
      resolvePromise();
    });

    proc.kill('SIGTERM');
  });
}

/** Register SIGINT/SIGTERM handlers that stop Cody and optionally close the HTTP server. */
export function registerCodyShutdownHandlers(onShutdown?: () => void): void {
  const shutdown = (signal: string): void => {
    console.log(`\n${signal} received, shutting down...`);
    void stopCodyWorker().then(() => {
      if (onShutdown) {
        onShutdown();
      } else {
        process.exit(0);
      }
    });
  };

  process.once('SIGINT', () => shutdown('SIGINT'));
  process.once('SIGTERM', () => shutdown('SIGTERM'));
}
