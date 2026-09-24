## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** Python UDS telemetry child processes spawned from Node.js (Next.js server-side) can leave orphaned `.sock` files and block the event loop if the Node process exits abruptly (e.g., via SIGINT/SIGTERM) without explicitly terminating the child processes.
**Action:** Always register explicit process event listeners (`exit`, `SIGINT`, `SIGTERM`) on the Node side to call `hub.stop()` and explicitly terminate child processes. For Next.js hot reloads, use a global symbol (e.g., `Symbol.for("nio.listeners")`) to track listener binding and prevent memory leaks. Signal listeners must call `process.exit(130)` and `process.exit(143)` respectively after cleanup to preserve the exit reason.
