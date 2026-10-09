## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-09 - [IPC/API Integration Insight]
**Learning:** Node.js process exit signals without handlers can leave spawned telemetry Python processes alive and .sock files orphaned, blocking the event loop and consuming resources.
**Action:** Always attach process.on handlers for `exit`, `SIGINT`, and `SIGTERM` when spawning child processes from a long-lived Node.js server. Use global symbols like `Symbol.for("nio.listeners")` to prevent attaching duplicates across Next.js hot reloads.
