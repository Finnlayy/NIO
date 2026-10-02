## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-02 - [IPC/API Integration Insight]
**Learning:** Next.js hot reloads and server shutdowns were leaving orphaned Python UDS telemetry child processes and `.sock` files behind, blocking the main event loop.
**Action:** Enforce explicit `exit`, `SIGINT`, and `SIGTERM` listeners using a global `Symbol.for("nio.listeners")` lock to clean up the sockets. `SIGINT` and `SIGTERM` listeners must call `process.exit(130)` and `process.exit(143)` respectively (NOT `process.exit(0)`) after cleanup to properly propagate the termination signal.
