## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry processes left orphaned `.sock` files on application exit because the Node process did not explicitly terminate the child processes or clean up sockets on signals.
**Action:** Trap `exit`, `SIGINT`, and `SIGTERM` in the Node process to explicitly call `.stop()` on the telemetry hub and exit with the correct signal codes (`130` for SIGINT, `143` for SIGTERM).
