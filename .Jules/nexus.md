## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-01 - [IPC/API Integration Insight]
**Learning:** UDS telemetry child processes spawned by Node.js leave orphaned `.sock` files and block the event loop if the main process is terminated without cleaning them up.
**Action:** Attach explicit process event listeners (`exit`, `SIGINT`, `SIGTERM`) on a global singleton (`Symbol.for("nio.listeners")`) to terminate the child processes (e.g. `hub.stop()`). For `SIGINT` and `SIGTERM`, ensure to call `process.exit(130)` and `process.exit(143)` respectively.
