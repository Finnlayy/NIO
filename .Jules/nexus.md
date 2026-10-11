## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-11 - [IPC/API Integration Insight]
**Learning:** Failing to gracefully stop spawned Python UDS child processes from Next.js server-side singletons during `SIGINT`/`SIGTERM` results in orphaned `.sock` processes and memory leaks.
**Action:** Enforce globally bound lifecycle hooks that propagate shutdown signals using explicit `process.exit` codes (130 for `SIGINT`, 143 for `SIGTERM`) to cleanly terminate child processes and perform socket cleanup.
