## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-23 - [IPC/API Integration Insight]
**Learning:** Orphaned `.sock` files and blocked event loops occur if Python UDS telemetry child processes spawned by Node.js (via Next.js hot reload singletons) are not explicitly terminated on shutdown.
**Action:** Always attach explicit `exit`, `SIGINT`, and `SIGTERM` listeners using a global symbol tracking (e.g. `Symbol.for("nio.listeners")`) to cleanly terminate child processes (via `hub.stop()`). For `SIGINT` and `SIGTERM`, additionally ensure `process.exit(130)` and `process.exit(143)` are called to correctly propagate the exit signal without masking it.
