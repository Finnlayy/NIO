## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-10-10 - [IPC/API Integration Insight]
**Learning:** In hot-reloading environments like Next.js, child processes and UDS  files can be left orphaned if global exit/interrupt handlers are missing or unbound across reloads.
**Action:** Use global symbol registries (e.g., `Symbol.for('nio.listeners')`) to attach `SIGINT`, `SIGTERM`, and `exit` listeners to explicitly terminate tracked processes and socket bindings. Always propagate the exit signals via `process.exit(130)` and `process.exit(143)`.

## 2026-10-10 - [IPC/API Integration Insight]
**Learning:** In hot-reloading environments like Next.js, child processes and UDS `.sock` files can be left orphaned if global exit/interrupt handlers are missing or unbound across reloads.
**Action:** Use global symbol registries (e.g., `Symbol.for('nio.listeners')`) to attach `SIGINT`, `SIGTERM`, and `exit` listeners to explicitly terminate tracked processes and socket bindings. Always propagate the exit signals via `process.exit(130)` and `process.exit(143)`.
