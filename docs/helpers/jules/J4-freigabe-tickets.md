# J4: Signed approval tickets and enforced risk (NIO)

Branch: `jules/j4-freigabe-tickets`

Files: `core/policy.py`, `core/protocol.py`, `protocol/operations.json`, `orchestrator/planner.py`, `orchestrator/kanban/api.py`, `orchestrator/cli.py`, tests under `tests/`.

`core/policy.py` is a protected file. The owner reviews this PR by hand, so keep the diff small and explain every policy change. List this at the top of the PR.

## Gaps

1. Approval is a text field: `approved_by: human` can be set without proof (`core/protocol.py:528`, `core/policy.py:156`).
2. `risk` is in the register but `core/policy.py` never reads it. Only `requires_elevation` is checked (`:301`, `:409`).
3. New register fields have no effect because `Operations.load` reads with `.get(...)` and does not reject unknown keys (`core/protocol.py:369-424`).
4. The planner suggests its own escalation: `approved_by='core'` with `repo_write` (`orchestrator/planner.py:186-199`).

## Required result

- An approval ticket is an HMAC-SHA256 over the intent hash, operation and expiry, with a constant-time comparison. The key comes from `NIO_APPROVAL_KEY`. If it is missing, ticket-gated operations are denied.
- That variable must never reach limbs or workers. Do not add it to any allowlist.
- Tickets are bound to one intent and expire. Add replay protection: a ticket works once.
- Add risk value `external`. Operations with `risk` of `high`, `destructive` or `external` run only with a valid ticket. Forged, expired, reused or foreign tickets are denied with a dedicated error code.
- Unknown risk values and unknown operation keys in `protocol/operations.json` fail on load.
- The planner can no longer grant `repo_write` or any approval itself. It may only request one.
- Issuing a ticket is a human action: add a CLI command and an authenticated route in `orchestrator/kanban/api.py`. Workers and limbs have no way to reach either.
- Tests cover: no ticket, forged, expired, reused, wrong intent, missing key.
