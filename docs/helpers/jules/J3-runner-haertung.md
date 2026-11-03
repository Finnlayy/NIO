# J3: Environment, process groups and a kill switch in the runner (NIO)

Branch: `jules/j3-runner-haertung`

Files: `orchestrator/runner.py`, `orchestrator/kanban/dispatcher.py`, `orchestrator/cli.py`, `limbs/registry.json`, `limbs/rea_limb.py`, one added error code in `core/protocol.py`, tests under `tests/`.

## Gaps

1. Limbs inherit the full host environment (`runner.py:1026`, `:1315`), so every limb sees every secret.
2. The hard abort kills only the main process (`runner.py:1432`), so child processes keep running.
3. NIO's core has no kill switch.

## Required result

- Limbs get a minimal base environment plus only the names in a new per-limb `env_allow` list in `limbs/registry.json`. Add the entries existing limbs need and justify each in the PR.
- Every limb runs in its own process group. Timeout and abort use `killpg`: first SIGTERM, then SIGKILL after a short grace period. A test starts a limb with a child process and shows that no process survives.
- A file `runtime/STOP` blocks new runs and ends running ones within 5 seconds. The Kanban dispatcher claims no tasks while it exists. Add `E_STOPPED` to `ErrorCode` in `core/protocol.py`; change nothing else in that file, another task works there.
- `orchestrator/cli.py` gets commands to set and clear the stop. Clearing never happens automatically.
