## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.
## 2026-09-26 - [IPC/API Integration Insight]\n**Learning:** UDS telemetry bridge node process was leaving orphaned .sock files and failing to clean up on termination because SIGINT and SIGTERM listeners did not explicitly call process.exit with the correct POSIX exit codes (130 for SIGINT, 143 for SIGTERM).\n**Action:** Registered explicit exit listeners on the telemetry hub protected by a global symbol to prevent duplicates across Next.js hot reloads, ensuring child processes are killed and proper exit codes are propagated.
