## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-04 - [IPC/API Integration Insight]
**Learning:** Next.js server restarts and process signals (SIGINT/SIGTERM) do not inherently clean up spawned UDS socket telemetry children, leading to orphaned sockets and process leaks.
**Action:** Always register global event listeners (using a `Symbol.for` guard to prevent duplication on hot-reload) on the Node process that explicitly invoke `hub.stop()` and exit with proper codes (`130` for SIGINT, `143` for SIGTERM) to propagate the shutdown signal.
