## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-05 - [IPC/API Integration Insight]
**Learning:** Orphaned UDS sockets (e.g., `runtime/telemetry.sock`) block the event loop and cause connection errors if the child processes bound to them are not properly terminated when the Next.js frontend is killed.
**Action:** Register explicit `exit`, `SIGINT`, and `SIGTERM` handlers on the Node process. Ensure `SIGINT` and `SIGTERM` propagate their exit codes (`130` and `143` respectively) after cleanup, and use a `Symbol.for()` check across Next.js hot reloads to avoid attaching duplicate listeners.
