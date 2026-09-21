## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2024-05-18 - [IPC/API Integration Insight]
**Learning:** Node.js process termination signals (`SIGINT`, `SIGTERM`, `exit`) do not automatically clean up Python UDS telemetry child processes spawned by `telemetryBridge`. This leaves orphaned `.sock` files and blocks the event loop.
**Action:** Registered explicit process event listeners on the Node.js process to call `hub.stop()` and `process.exit(code)` for graceful shutdown and socket cleanup.
