# J7: Worker runtime `limb` (NIO)

Branch: `jules/j7-worker-runtime-limb`

Files: `orchestrator/kanban/limb_bridge.py` (new), `orchestrator/kanban/worker_entry.py`, tests under `tests/`.

## Gap

Kanban workers run `noop` or `command` with a free argv. Nothing connects Kanban to limbs, so a task cannot run a fixed limb operation.

## Required result

- `SOUL.md` frontmatter may say `runtime: limb` and `limb_operation: <operation>`. There is no argv, and task text never selects the operation.
- The worker does not execute limb code. In `worker_entry.py` it only validates the frontmatter and writes `out/limb_request.json` with the operation and the parameters from the task.
- `orchestrator/kanban/limb_bridge.py` runs on the host side. It reads that request, builds an intent and sends it through the normal orchestrator path, including `Policy.check`. It never calls a limb directly and never sets elevation or approval.
- The operation must equal the `limb_operation` in the stored active soul, must exist in `protocol/operations.json`, and must have risk `none`, `read` or `write`. Anything else is denied. Ticket-gated risk stays out of this runtime for now.
- The result returns to the task as data marked `untrusted: true`.
- Add one call to the bridge in the existing host-side path after a run. Keep this hook to a few lines, because PR 295 and package J3 change `orchestrator/kanban/sync.py` and `dispatcher.py`. Name the line in the PR.
- The change works after the worker hardening in PR 295, where `subprocess` allows only `noop`. Allow `limb` in that sandbox only if the worker really runs no external code, and say so in the PR.
- Tests cover: valid request runs `echo`, operation mismatch denied, unknown operation denied, high risk denied, forged request file denied, policy denial reaches the task.
