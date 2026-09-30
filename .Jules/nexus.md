## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.
## 2026-09-30 - [IPC/API Integration Insight]
**Learning:** Orphaned UDS sockets can be left behind and block the Node event loop on frontend application termination if proper process termination listeners (`exit`, `SIGINT`, `SIGTERM`) are missing for spawned bridge child processes.
**Action:** When spawning Python UDS telemetry child processes from Node.js (e.g., telemetry bridge), explicit process event listeners (`exit`, `SIGINT`, `SIGTERM`) must be registered to explicitly terminate the child processes (e.g., via `hub.stop()`), ensuring socket cleanup and preventing orphaned `.sock` files.
