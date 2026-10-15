## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-15 - [IPC/API Integration Insight]
**Learning:** Node.js process termination without explicit SIGINT/SIGTERM handlers leaves orphaned UDS `.sock` files and underlying child processes active. Next.js hot module replacement (HMR) can lead to duplicated global event listeners if not guarded properly via `Symbol.for()`.
**Action:** Always register explicit `process.on('SIGINT')` and `process.on('SIGTERM')` listeners bound globally to terminate spawned sub-processes and explicitly call `process.exit(130)` / `process.exit(143)` respectively.
