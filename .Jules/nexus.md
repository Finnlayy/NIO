## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-17 - [IPC/API Integration Insight]
**Learning:** Orphaned `.sock` files can be left behind if UDS telemetry child processes are not explicitly terminated when the Next.js frontend node process exits.
**Action:** Always add explicit process event listeners (`exit`, `SIGINT`, `SIGTERM`) utilizing `hub.stop()` and deterministic exit codes (`130` for `SIGINT`, `143` for `SIGTERM`) to clean up child processes gracefully, leveraging global symbols to prevent duplicate listeners across hot reloads.
