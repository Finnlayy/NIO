import { readFile, readdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { NextResponse } from "next/server";
import { kanbanToken } from "../../../apollo/proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const KANBAN_TIMEOUT_MS = 3_000;
const MAX_RUNS = 5;

/**
 * Read-only telemetry for /ops. Takes nothing from the request and returns only
 * the fields the widgets need: task descriptions, results, souls and agent
 * output stay on the server. A failing source sets its own flag, so one outage
 * shows "keine Daten" for that source and leaves the others alone.
 */

interface OpsTask {
  id: string;
  title: string;
  status: string;
  assigned_worker_uid: string | null;
}
interface OpsWorker {
  uid: string;
  name: string;
  status: string;
}
interface OpsLimb {
  name: string;
  status: string;
  runtime: string;
}
interface OpsRun {
  run_id: string;
  agent: string;
  state: string;
  created_at: string;
}

const text = (value: unknown): string => (typeof value === "string" ? value : "");

async function kanbanList(path: string, token: string): Promise<Array<Record<string, unknown>>> {
  const host = process.env.NIO_KANBAN_API_HOST || "127.0.0.1";
  const port = process.env.NIO_KANBAN_API_PORT || "8740";
  const response = await fetch(`http://${host}:${port}${path}`, {
    headers: { authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(KANBAN_TIMEOUT_MS),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`kanban HTTP ${response.status}`);
  const body: unknown = await response.json();
  if (!Array.isArray(body)) throw new Error("kanban response is not a list");
  return body as Array<Record<string, unknown>>;
}

async function readKanban(): Promise<{ tasks: OpsTask[]; workers: OpsWorker[] }> {
  const token = kanbanToken(process.env);
  if (!token) throw new Error("NIO_KANBAN_APOLLO_TOKEN is not set");
  const [tasks, workers] = await Promise.all([kanbanList("/api/v1/kanban/tasks", token), kanbanList("/api/v1/workers", token)]);
  return {
    tasks: tasks.map((task) => ({
      id: text(task.id),
      title: text(task.title),
      status: text(task.status),
      assigned_worker_uid: typeof task.assigned_worker_uid === "string" ? task.assigned_worker_uid : null,
    })),
    workers: workers.map((worker) => ({ uid: text(worker.uid), name: text(worker.name), status: text(worker.status) })),
  };
}

async function readLimbs(repoRoot: string): Promise<OpsLimb[]> {
  const raw = JSON.parse(await readFile(join(repoRoot, "limbs", "registry.json"), "utf8")) as {
    limbs?: Record<string, Record<string, unknown>>;
  };
  if (!raw.limbs || typeof raw.limbs !== "object") throw new Error("registry has no limbs map");
  return Object.entries(raw.limbs).map(([name, limb]) => ({ name, status: text(limb.status), runtime: text(limb.runtime) }));
}

async function readRuns(repoRoot: string): Promise<OpsRun[]> {
  const dir = join(repoRoot, "runtime", "agents");
  let names: string[];
  try {
    names = await readdir(dir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return []; // no agent has run yet
    throw error;
  }
  const runs: OpsRun[] = [];
  for (const name of names) {
    try {
      const state = JSON.parse(await readFile(join(dir, name, "state.json"), "utf8")) as Record<string, unknown>;
      runs.push({ run_id: text(state.run_id), agent: text(state.agent), state: text(state.state), created_at: text(state.created_at) });
    } catch {
      // A run being written or removed is not a broken source.
    }
  }
  return runs.sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, MAX_RUNS);
}

export async function GET() {
  // Next runs with frontend/ as working directory.
  const repoRoot = resolve(process.cwd(), "..");
  const [kanban, limbs, runs] = await Promise.allSettled([readKanban(), readLimbs(repoRoot), readRuns(repoRoot)]);
  return NextResponse.json({
    kanban: kanban.status === "fulfilled" ? kanban.value : { tasks: [], workers: [] },
    limbs: limbs.status === "fulfilled" ? limbs.value : [],
    runs: runs.status === "fulfilled" ? runs.value : [],
    errors: {
      kanban: kanban.status === "rejected",
      limbs: limbs.status === "rejected",
      runs: runs.status === "rejected",
    },
  });
}
