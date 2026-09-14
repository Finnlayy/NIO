## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-09 - [IPC/API Integration Insight]
**Learning:** Node.js child processes spawned for UDS telemetry were orphaned on SIGINT/SIGTERM, leaving behind stale `.sock` files and blocking the main event loop from shutting down cleanly.
**Action:** Always test socket cleanup on application shutdown and register `process.on('exit'/'SIGTERM')` handlers to explicitly terminate spawned Python daemon processes.
