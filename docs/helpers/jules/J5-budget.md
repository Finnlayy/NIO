# J5: Budget limits for agent runs (NIO)

Branch: `jules/j5-budget`

Files: `orchestrator/budget.py` (new), `limbs/agent_base.py`, tests under `tests/`.

## Gap

Runs are limited only by time, iterations and slots. There is no limit on tokens or credits. `AgentLimb.over_budget` in `limbs/agent_base.py` exists as a hook, but nothing feeds it from a shared budget.

## Required result

- `orchestrator/budget.py` tracks runtime seconds, tokens and credits per run and per day.
- The daily ledger lives under `runtime/budget/<YYYY-MM-DD>.json`. Writes are atomic and safe against two processes writing at once. The ledger holds numbers only, never prompts or keys.
- Limits come from `NIO_BUDGET_*` environment variables with conservative defaults in the module, because `neu.config.json` is reviewed by a human. Document each variable in the module docstring.
- `<limb>.start` is denied when the daily budget is used up. `<limb>.status` ends a run that exceeds its run limit or the daily limit, using the existing stop path, and the run ends with a clear reason.
- A run that reports no usage counts its runtime. Unknown tokens do not count as zero tokens used: they are recorded as unknown.
- A ledger that cannot be read or written denies new runs.
- Tests cover: run limit, daily limit, day rollover, corrupt ledger, two writers.

This PR does not edit `orchestrator/runner.py`. Packages J3 and J4 are changing it.
