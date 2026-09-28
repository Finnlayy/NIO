## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-28 - [IPC/API Integration Insight]
**Learning:** Node.js main process termination does not automatically clean up Python UDS telemetry child processes, which can leave orphaned `.sock` files and block the event loop.
**Action:** Explicitly attach `exit`, `SIGINT`, and `SIGTERM` listeners using a global symbol tracking object (to avoid hot reload memory leaks). Terminate the child processes (e.g., via `hub.stop()`), and exit with signals 130 and 143 respectively to properly propagate termination reasons.
