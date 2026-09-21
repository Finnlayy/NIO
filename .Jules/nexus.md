## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-21 - [IPC/API Integration Insight]
**Learning:** Orchestrator/socket node `telemetryBridge` left orphaned `.sock` files, blocking event loops and failing rebinds on subsequent executions.
**Action:** Subprocess nodes need explicit process listeners (`exit`, `SIGINT`, `SIGTERM`) registered to terminate the python consumer correctly via `hub.stop()` and avoid unhandled termination events. Proper handlers call `process.exit(130)` and `process.exit(143)` respectively.
