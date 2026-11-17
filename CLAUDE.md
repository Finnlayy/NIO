# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Docs, comments, commit messages and CLI output in this repo are written in **German**; match that when editing. Entry point for documentation: `docs/INDEX.md`.

## Several stacks in one repo

The repo holds independent systems that share neither runtime nor data model (see `docs/ARCHITECTURE.md`). Know which one you are in before changing anything:

| Stack | Dirs | Runtime | Tests |
|---|---|---|---|
| **NEU core** (Python) | `core/`, `orchestrator/`, `limbs/`, `protocol/`, `prompts/`, `scripts/`, `tests/` | Python 3.11+, **stdlib only** (deliberate — `dependencies = []` in `pyproject.toml`) | `make test-core` |
| **Ciel** (Python) | `apollo/ciel/` | stdlib; pydantic v2 / onnxruntime optional with stdlib fallbacks | `tests/test_ciel_*.py` (part of `make test-core`) |
| **Architect / OMEGA** (Python) | `Architect/` | own package root (`core/`, `limbs/`, `gui/` PyQt6); tests are stdlib-only, GUI tests skip without PyQt6 | `make test-architect` (runs from inside `Architect/`) |
| **Legacy TS middleware** | `src/`, `evals/`, `agents/`, `schemas/learning/`, `prompts/system/` | Node 18+, `yaml`, `zod` | `npm run typecheck`, `pytest evals/tests` |
| **Apollo UI** | `frontend/` | Next 16, React 19, zustand, Tailwind 4 | `node frontend/scripts/ui-test.mjs` |

Normative boundary: everything about a job (who runs it, timers, permissions, iterations, results) belongs to the Python core and is expressed in Protocol 1.2. TypeScript never decides timers/rights/iterations; Python never renders UI. Note `Architect/core` and root `core/` are different packages — don't cross-import.

## Commands

```bash
make check          # full gate, same as CI: compile · ruff · mypy · test (core+Architect) · ui-test · e2e
make test-core      # python3 -W error::ResourceWarning -m unittest discover -s tests -t . -q
make test-architect
make lint / lint-fix / types   # ruff (line-length 140, E501 ignored) / mypy over core, orchestrator, limbs
make e2e            # scripts/ci_e2e_unlimited.py — proves unlimited-mode properties through the real CLI

# single test (from repo root)
python3 -m unittest tests.test_protocol -v
python3 -m unittest tests.test_protocol.SomeTestCase.test_name
# Architect single test
cd Architect && python3 -m unittest tests.test_timer -v

# dev tools: python3 -m pip install -e '.[dev]'   (ruff, mypy)

# TS middleware
npm run build | npm run typecheck | npm run trace:generate
python3 -m pytest evals/tests -v

# frontend (port 4001; API on 4000)
cd frontend && npx next dev -p 4001
cd frontend && npx tsc --noEmit && node scripts/ui-test.mjs && npm run build
```

`make ui-test` silently skips if `frontend/node_modules` is missing. Tests run with `-W error::ResourceWarning` — unclosed files/sockets/subprocesses fail the suite.

CI: `.github/workflows/ci-evals.yml` covers only the TS middleware + `evals/`. The NEU gate lives in `ci/neu.yml` and is activated by `git mv` into `.github/workflows/` (the GitHub app can't create workflows — see `ci/README.md`).

## NEU core architecture

Flow: **Core → Intent → Orchestrator → Limb → Result**, Protocol `neu/intent` / `neu/result` version **1.2** (`protocol/PROTOCOL.md` is normative; `core/protocol.py` is the reference implementation and wins on disagreement).

- **Transport is file-based**: intents land in `runtime/inbox/<limb>/<intent_id>.json`; a limb is a subprocess that reads it and prints exactly one Result as one JSON line on stdout. `runtime/` (queues, jobs, schedules, archive, locks) is not versioned.
- **Registries**: `limbs/registry.json` (limbs, status `planned|active|deprecated` — only `active` may be spawned, runtime argv templates) and `protocol/operations.json` (operations, risk, permissions). `orchestrator/runner.py::LimbRegistry` loads the former; `Orchestrator.dispatch()` → `_spawn()` runs one subprocess per limb.
- **Schema parity**: `protocol/*.schema.json` must stay in sync with the dataclasses in `core/protocol.py` — `tests/test_schema_parity.py` enforces it. Unknown envelope keys are errors; old 1.0/1.1 envelopes are upgraded on read, so new fields need defaults.
- **Every job gets a clock before it starts**. `timer.mode="deadline"`: on expiry the limb reports `done/remaining/blockers` and the orchestrator plans a reduced second pass (max 2 iterations per job). `timer.mode="unlimited"`: time is tracked from `timer.t0`, driven by `intent.schedule.triggers[]` (`when`/`every_s`/`at_s` → `emit_event|check|escalate|finish_job|log`); `check` spawns `kind="scheduled"` control jobs that don't consume iteration budget; `safety_net_s` is zombie protection only.
- Key modules: `core/kernel.py`, `core/job.py` (lifecycle), `core/policy.py` (sandbox/permissions — limbs write only under `workspace/`), `orchestrator/scheduler.py`, `orchestrator/planner.py`, `orchestrator/events.py` (synchronous EventBus; does **not** validate kinds), `orchestrator/uds.py` (opt-in AF_UNIX datagram broadcast → `frontend/src/server/telemetryBridge.ts` → SSE `/api/telemetry/stream`).
- CLI: `python3 -m orchestrator {spec,status,job,watch,schedule,subagent,bus,archive,validate}`. Exit codes: 0 ok · 1 protocol · 2 job unresolved · 3 usage.
- Limbs: `echo`, `bootstrap` (`fs.*`), `rea` (subagent with own sandbox under `workspace/subagents/<id>/`, `docs/REA-SUBAGENT.md`), `trading` (thin seam to the external Sigma worker over its public `/api/*`; pinned commit, never patch the donor — `docs/TRADING-LIMB.md`).
- **Ciel** (`apollo/ciel/`, `docs/CIEL.md`) is purely additive: cold-storage tool registry mirrored from `limbs/registry.json`, NCM gate (System-1 bypass ≥0.88 confidence, else JIT top-3 tools + meta-tool), sandbox agent, macro synthesizer, `ciel.*` bus events, external MCP nodes. It wraps existing code by delegation rather than modifying it.

## Testing rules (from docs/TESTING.md)

- No network and no running services in tests — use fakes for adapters/contracts.
- Tests using a sandbox must use their own directory (e.g. `workspace/.test-…`), never the real `workspace` — a test once killed a live worker that way.
- Fixture intents have fixed timestamps; use `fresh_intent()` to reset timers, otherwise an expired timer yields a correctly invalid Result.
- Core tests use real subprocesses and real timers.

## Frontend (Apollo)

`/` and `/apollo` render the Apollo stage (shader orb, neural graph, deck, terminal); `/ops` is the widget grid. API routes: `POST /api/apollo` (LLM routing proxy; keys server-side only, fail-closed; never invent a model — no candidate ⇒ `EXHAUSTED`), `POST /api/sandbox` (read-only allowlist, no shell), `/api/market/[tool]`, `/api/telemetry/stream`. Static routes must not touch `window` during prerender, and server/first-client render must match (hydration) — `npm run build` is the check for both. UI tests are a zero-dependency harness (`tsc` + `node --test`, no DOM) under `frontend/src/ops/__tests__/`.
