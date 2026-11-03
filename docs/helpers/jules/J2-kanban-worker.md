# J2: Stop Kanban workers from granting themselves rights (NIO)

Branch: `jules/j2-kanban-worker`

Files: `orchestrator/kanban/sync.py`, `orchestrator/kanban/worker_entry.py`, `orchestrator/kanban/config.py`, `orchestrator/kanban/sandbox.py`, `orchestrator/kanban/store.py`, tests under `tests/`.

## Gaps

1. A worker can write back its own `SOUL.md`, including `runtime: command` with any argv (`sync.py:122-133`, `store.py:60`, `worker_entry.py:150-172`). On the next run it has a free shell.
2. The worker sandbox defaults to `subprocess` with no isolation (`config.py:50`).

## Required result

- A worker cannot change `runtime`, `command` or any other execution setting, neither directly nor through synced files. A change a worker makes to `SOUL.md` becomes a stored proposal that waits for human approval. Nothing proposed takes effect on its own.
- Docker is the default sandbox.
- `subprocess` is allowed only for the `noop` runtime. Runtime `command` requires the Docker sandbox. If Docker is missing, the run fails with a clear error and never falls back to `subprocess`.
- A regression test reproduces the self-escalation and shows it is blocked.
