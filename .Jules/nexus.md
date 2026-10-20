## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.
## 2026-10-20 - [IPC/API Integration Insight]
**Learning:** When spawning Python UDS telemetry child processes from Node.js (e.g., telemetry bridge), if the Node process stops abruptly (e.g. SIGINT/SIGTERM), orphaned  files can block the event loop or block new listeners from binding to the same path.
**Action:** Next.js server-side singletons must track and attach `exit`, `SIGINT`, and `SIGTERM` listeners to explicitly terminate child processes and trigger socket cleanup. Crucially, `SIGINT` and `SIGTERM` listeners must call `process.exit(130)` and `process.exit(143)` respectively after cleanup to propagate the termination signal.
## 2023-10-20 - [IPC/API Integration Insight]
**Learning:** When spawning Python UDS telemetry child processes from Node.js (e.g., telemetry bridge), if the Node process stops abruptly (e.g. SIGINT/SIGTERM), orphaned `.sock` files can block the event loop or block new listeners from binding to the same path.
**Action:** Next.js server-side singletons must track and attach `exit`, `SIGINT`, and `SIGTERM` listeners to explicitly terminate child processes and trigger socket cleanup. Crucially, `SIGINT` and `SIGTERM` listeners must call `process.exit(130)` and `process.exit(143)` respectively after cleanup to propagate the termination signal.
