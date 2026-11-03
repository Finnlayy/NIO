# J8: Real run log (NIO)

Branch: `jules/j8-laufprotokoll`

Files: `orchestrator/events.py`, `limbs/agent_base.py`, `docs/OPERATIONS.md`, tests under `tests/`.

## Gap

`runtime/system.log` is only an anchor (`NEU-PHASE-3-ANCHOR` in `orchestrator/events.py`, function `build_event_bus`). Agent runs write `runtime/agents/<run_id>/events.jsonl`, but nothing brings them into one place.

## Required result

- `build_event_bus` adds a persistent file sink for `runtime/system.log`, using the existing `render_record` format.
- Write failures in the sink never stop a run. They are counted and reported once on the console.
- The file rotates by size, keeps a fixed number of files and needs no dependency.
- Each agent run logs start, end, final state, runtime, cost as far as known, and artifact count to the system log. Prompts, keys and raw agent output stay out. Use the existing `redact`.
- Log lines cannot be forged by agent output: strip newlines and control characters from any value that came from an agent.
- `docs/OPERATIONS.md` says where the log is and how rotation works.
- Tests cover: writing, rotation, unwritable path, redaction, newline injection.

This PR does not edit `orchestrator/runner.py`. Packages J3 and J4 are changing it. In `limbs/agent_base.py` keep the change small, because package J5 also touches that file.
