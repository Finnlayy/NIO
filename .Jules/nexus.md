## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2025-02-23 - [IPC/API Integration Insight]
**Learning:** UDS child processes spawned by Node.js require explicit signal handling (SIGINT, SIGTERM, exit) connected to global singletons to avoid leaving orphaned `.sock` files during Next.js hot reloads.
**Action:** Use a global tracking symbol (e.g., `Symbol.for('nio.listeners')`) to attach explicit exit and signal listeners that clean up UDS sockets and cleanly propagate the exit codes (130 for SIGINT, 143 for SIGTERM).
