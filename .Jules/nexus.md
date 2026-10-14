## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-14 - [IPC/API Integration Insight]
**Learning:** Orphaned UDS sockets can be left behind and block the main event loop when Node.js child processes for UDS telemetry spawn loops are not cleanly terminated on process exit or termination signals.
**Action:** When spawning Python UDS telemetry child processes from Node.js, ensure explicit process event listeners (`exit`, `SIGINT`, `SIGTERM`) are registered to terminate the child processes (e.g. via `hub.stop()`), using a global symbol to prevent duplicate listeners across hot reloads.
