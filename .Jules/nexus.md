## 2026-09-08 - [IPC/API Integration Insight]
**Learning:** UDS telemetry bridge node process lacked exponential backoff, causing too fast respawns on failure.
**Action:** Enforce exponential backoff bounded at 30 seconds for spawn loops next time.
## 2026-09-09 - [IPC/API Integration Insight]
**Learning:** `AgentPool.renew` using `write_text` caused temporary truncation of the lock file, causing `json.loads` to throw `JSONDecodeError` and misreport busy slots across orchestrator instances.
**Action:** When writing JSON machine state files that are read concurrently by other processes (e.g., locks, schedules), never use `Path.write_text()`. Always use `core.atomic.atomic_write_bytes` combined with compact serialization (`separators=(',', ':')`).
