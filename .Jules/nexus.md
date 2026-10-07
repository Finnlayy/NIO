## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-07 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked explicit exit listeners (`SIGINT`, `SIGTERM`), leaving orphaned child processes and `.sock` files on termination.
**Action:** Attached explicit exit, SIGINT, and SIGTERM event handlers using a global tracker (`Symbol.for("nio.listeners")`) across hot reloads to explicitly call `hub.stop()` to clean up sockets and child processes before propagating exit code `130` or `143`.
