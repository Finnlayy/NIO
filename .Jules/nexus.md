## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.

## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** When Node.js is terminated via SIGINT or SIGTERM, the spawned Python UDS telemetry child processes can be orphaned, resulting in `.sock` files remaining and blocking future restarts, without propagating correct exit codes.
**Action:** Always listen to `process.on("exit")`, `process.on("SIGINT")`, and `process.on("SIGTERM")` to properly kill child processes. Additionally, when handling SIGINT and SIGTERM, always call `process.exit(130)` and `process.exit(143)` respectively rather than exiting cleanly, to avoid masking the true shutdown reason.
