import { NextResponse } from 'next/server';
import { readFileSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';

export async function GET(req: Request) {
  let kanban = { tasks: [], workers: [] };
  let limbs: { registry: any[] } = { registry: [] };
  let runs: Array<{ id: string; modified: number; status: string; task_id?: string }> = [];

  try {
    const cwd = process.cwd();
    // In Next.js, cwd is frontend/. Repo root is one level up.
    const repoRoot = resolve(cwd, '..');

    // Read Kanban via API
    try {
      const token = process.env.NIO_KANBAN_API_TOKEN;
      if (token) {
        const port = process.env.NIO_KANBAN_API_PORT || 8740;
        const host = process.env.NIO_KANBAN_API_HOST || "127.0.0.1";
        const [apiRes, workerRes] = await Promise.all([
          fetch(`http://${host}:${port}/api/v1/kanban/tasks`, {
            headers: { "Authorization": `Bearer ${token}` }
          }).catch(() => null),
          fetch(`http://${host}:${port}/api/v1/workers`, {
            headers: { "Authorization": `Bearer ${token}` }
          }).catch(() => null)
        ]);

        if (apiRes?.ok) {
           kanban.tasks = await apiRes.json();
        }

        if (workerRes?.ok) {
           kanban.workers = await workerRes.json();
        }
      }
    } catch(e) {
      // Ignored
    }

    // Read Limb registry from repo root
    try {
        const rawLimbs = JSON.parse(readFileSync(join(repoRoot, 'limbs/registry.json'), 'utf8'));
        // Only return required fields
        if (Array.isArray(rawLimbs)) {
          limbs.registry = rawLimbs.map(l => ({
            id: l.id,
            name: l.name,
            kind: l.kind
          }));
        }
    } catch(e) {
      // Ignored
    }

    // Read agents
    try {
        const agentsDir = join(repoRoot, 'runtime/agents');
        const agentFiles = readdirSync(agentsDir);
        for (const file of agentFiles) {
            const agentPath = join(agentsDir, file);
            const stat = statSync(agentPath);
            if (stat.isDirectory()) {
                let status = "unknown";
                let task_id;
                try {
                   const stateJson = JSON.parse(readFileSync(join(agentPath, 'state.json'), 'utf8'));
                   status = stateJson.status || status;
                   task_id = stateJson.task_id;
                } catch(e) {}
                runs.push({
                   id: file,
                   modified: stat.mtimeMs,
                   status,
                   task_id
                });
            }
        }
        runs.sort((a,b) => b.modified - a.modified);
        runs = runs.slice(0, 5); // recent 5
    } catch(e) {
      // Ignored
    }
  } catch (e) {
     // Ignored
  }

  // If we couldn't load any data, fail closed.
  if (kanban.tasks.length === 0 && limbs.registry.length === 0 && runs.length === 0) {
     return NextResponse.json({ error: "keine Daten" }, { status: 500 });
  }

  return NextResponse.json({ kanban, limbs, runs });
}
