## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** Python UDS telemetry child processes spawned from Node.js (e.g., telemetry bridge) could leave orphaned `.sock` files and block the event loop because implicit signals do not trigger manual socket cleanup on fast exits.
**Action:** Always register explicit process event listeners (`exit`, `SIGINT`, `SIGTERM`) to terminate the child processes (e.g., `hub.stop()`), and ensure `SIGINT`/`SIGTERM` explicitly exit the Node process with codes 130 and 143 respectively to properly propagate the termination signal. Use a global symbol (e.g., `Symbol.for("nio.listeners")`) to avoid attaching duplicate listeners across hot reloads.
