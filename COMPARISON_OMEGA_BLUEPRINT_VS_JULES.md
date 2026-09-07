# NIO Omega Blueprint vs. Jules's OMEGA Architect — Full Comparison

> **Blueprint sources:** `docs/NEU.md`, `docs/ARCHITECTURE.md`, `protocol/PROTOCOL.md`,
> `docs/REVIEW-2026-09-04.md`, `README.md`, `core/`, `orchestrator/`, `limbs/`,
> `src/`, `frontend/`, `schemas/learning/`, `src/learning/`
>
> **Jules's code (PR #11):** `Architect/` directory — merged as
> `feat: scaffold pure-python Architect system`
>
> **Status:** Jules's OMEGA is an **active 5-phase build**. Only Phase 1 (Foundation)
> has shipped. Phases 2–5 are planned and progressively closer to the blueprint's
> feature set. This comparison evaluates both what exists *today* and what the
> roadmap targets.

---

## 1. Executive Summary

| Dimension | **Omega Blueprint (NIO main)** | **Jules's OMEGA Architect** |
|---|---|---|
| **What it is** | A layered AI operating system: deterministic core → orchestrator → limbs, with a TypeScript middleware layer, a React frontend, a continuous-learning engine, a formal protocol, and a multi-phase bootstrap plan. | A pure-Python **AI trading + self-improving agent system** — PyQt6 GUI, exchange feeds, risk engines, GenAI integration, vector memory — with a 5-phase plan toward reflection, safe self-modification, RLHF, and self-modeling. |
| **Philosophy** | Stdlib-only, file-transport, protocol-first, incremental phases (Phase 1–4), zero external runtime deps for the core. | External services embraced: PyQt6, torch, onnx, qdrant-client, ccxt.pro, google-genai, numpy, pydantic-settings. Domain-specific from day one. |
| **Current maturity** | **Production-grade** for Phases 1–2 (241+ unit tests, 20 E2E proofs, 3 performance triads, CI matrix across Python 3.11–3.13). | **Phase 1 of 5 shipped** — foundation scaffold with state machines, risk invariants, GUI shell, exchange daemon. Phase 2 in progress. |
| **Lines of code** | ~36,600 (211 files, 12+ PRs) | ~2,200 (≈30 files) — Phase 1 only |
| **Tests** | 555+ unit tests across 15 test files, plus E2E scripts, benchmark scripts, schema-parity guards | 1 smoke test (`test_init.py`) — asserts imports and GUI window creation |
| **Roadmap coverage** | Phases 1–2 done, Phase 3 (Ouroboros) and Phase 4 (recursive expansion) planned | 5-phase plan targeting reflection, self-modification, RLHF, and self-modeling — converging with the blueprint's later phases |

---

## 2. Architectural Philosophy

### Omega Blueprint — "The Brain"
The blueprint designs a **recursive self-improving AI system** built in strict layers:

```
prompts/         ← Role specifications (text, no logic)
orchestrator/    ← Runner, scheduler, planner, events, locks, transport, CLI
limbs/           ← Executing arms (echo_limb, bootstrap_limb)
core/            ← Protocol, config, policy, job lifecycle, kernel, schema-checker
protocol/        ← Normative spec + JSON schemas + operations register
```

**Key principles:**
1. **Stdlib-only Python 3.11+** — a limb must run anywhere, even offline.
2. **File-based transport** — every intent and result is a durable JSON file in `runtime/`.
3. **Protocol-first** — `neu/intent` → `neu/result` v1.2 is the normative contract; schemas and parser have machine-checked parity.
4. **Every job gets a clock** — two modes: `deadline` (budget) and `unlimited` (track time, don't limit it).
5. **Fail-fast policy** — triggers, paths, and budgets are validated *before* the limb starts.
6. **Two stacks, one boundary** — Python core (execution) and TypeScript middleware (HTTP/UI) share no runtime or data model.

### Jules's Architect — "The Terminal"
Jules built a **Global Market Terminal (GMT)** — a trading dashboard with:

```
Architect/
├── core/          ← Pydantic config, daemon supervisor, state machine enums
├── gui/           ← PyQt6 MainWindow, TickerTape, CommandBar, UnifiedChartTab, theme
├── limbs/
│   ├── intelligence/  ← GenAI client (Gemini), microstructure engine, Qdrant memory
│   ├── math/          ← AC Gravity engine, The Judge M8 (6 risk invariants)
│   └── ml/            ← HDBSCAN clustering engine
├── models/        ← ONNX regime model export + weights
├── evals/         ← Empty __init__
└── snap/          ← Snapcraft packaging
```

**Key principles:**
1. **External services** — Gemini API, Qdrant cloud, Kraken/Bybit exchanges, AlphaVantage.
2. **GUI-first** — PyQt6 dark-matrix theme with live ticker tape, chart views, command bar.
3. **Risk invariants** — 6 hard constraints (max leverage 5×, max slippage 15 bps, power factor ≥ 0.89, 10% vault reserve, forbidden zones at 99.9% quantile, feed integrity).
4. **Daemon supervisor** — asyncio `ccxt.pro` background watchers feeding the GUI.

---

## 3. Component-by-Component Comparison

### 3.1 Core / Configuration

| Aspect | Blueprint | Jules |
|---|---|---|
| **Config system** | `core/config.py` — 409 lines; profiles (`dev`/`scale`), limits, paths, constitution guard, timer defaults, sandbox roots. Pure stdlib. | `Architect/core/config.py` — 49 lines; Pydantic-settings with `.env` file; API keys for 5 services, risk invariant thresholds. |
| **State machine** | Implicit — `core/job.py` models job lifecycle (open → running → resolved/iterating/failed/escalated) with 512 lines of state management. | Explicit enums — `SystemExecutionState` (5 states), `TrancheLifecycleState` (4), `FeedConnectionState` (2), `MarketRegimeState` (4). No transitions or logic. |
| **Daemon/process management** | `orchestrator/runner.py` — 2,012 lines; async spawn/collect, supervise loop, heartbeat, slot renewal, tick-scheduler integration, safety-net enforcement. | `Architect/core/daemon_supervisor.py` — 54 lines; `FeedDaemon` wraps `ccxt.pro.watch_ticker`, `DaemonSupervisor` runs coroutines with `asyncio.gather`. Stub-level. |

### 3.2 Orchestrator / Execution Engine

| Aspect | Blueprint | Jules |
|---|---|---|
| **Job orchestration** | Full orchestrator: `runner.py` (2,012 lines), `scheduler.py` (874 lines), `planner.py` (594 lines), `events.py` (382 lines), `transport.py` (852 lines), `locks.py` (229 lines). | **Not implemented.** No orchestrator, no scheduler, no planner. |
| **Protocol** | `protocol/PROTOCOL.md` — 492 lines of normative spec; v1.2 with timer modes, schedule triggers, autodidactic correction, safety nets. | **Not present.** No protocol, no envelope format, no schemas. |
| **Scheduling** | Full scheduler with virtual clock, edge-triggered conditions, interval triggers, time marks, persistent state, catch-up logic, bounded caches. | **Not present.** |
| **CLI** | `orchestrator/cli.py` — 1,564 lines; subcommands for `spec`, `status`, `job run/watch/show/list`, `schedule show/list/clear`, `validate --schema`, `archive stats/compact/lookup/verify`, `bus tail`, `scale`. | **Not present.** |

### 3.3 Limbs / Intelligence Modules

| Aspect | Blueprint | Jules |
|---|---|---|
| **Echo Limb** | `limbs/echo_limb.py` — 143 lines; returns the intent params as a result. Fully tested. | Not present. |
| **Bootstrap Limb** | `limbs/bootstrap_limb.py` — 389 lines; `fs.read_file`, `fs.write_file`, `fs.patch`, `fs.list`, `fs.mkdir` with sandbox enforcement, backup, hash verification. | Not present. |
| **Microstructure Engine** | Not present. | `Architect/limbs/intelligence/microstructure_engine.py` — 40 lines; OBI calculation (orderbook imbalance), footprint map (intra-bar volume delta). Uses numpy. |
| **AC Gravity Engine** | Not present. | `Architect/limbs/math/ac_gravity_engine.py` — 22 lines; active/reactive power calculation, gravity field (L2+L3+Polymarket blend), forbidden-zone detection at 99.9% quantile. |
| **The Judge M8** | Not present. | `Architect/limbs/math/the_judge_m8.py` — 30 lines; checks 6 risk invariants (feed integrity, forbidden zone, leverage ≤ 5×, slippage ≤ 15 bps, power factor ≥ 0.89, vault reserve ≥ 10%). |
| **GenAI Client** | Core kernel is an LLM + deterministic wrapper (`core/kernel.py`, 480 lines). Full evaluation, verdict, autodidactic loop. | `Architect/limbs/intelligence/genai_client.py` — 30 lines; Gemini SDK wrapper with `generate_journal()` and `reflect_dsr()` — both return stub strings. |
| **Qdrant Memory** | Not present (planned for Phase 4). | `Architect/limbs/intelligence/qdrant_memory_engine.py` — 35 lines; try/except to fall back to local DB. Stub methods. |
| **HDBSCAN** | Not present. | `Architect/limbs/ml/hdbscan_engine.py` — 17 lines; stub import of hdbscan. No logic. |

### 3.4 Frontend / GUI

| Aspect | Blueprint | Jules |
|---|---|---|
| **Technology** | React/Next.js (`frontend/`); Next 15, Zustand state, framer-motion animations, Tailwind CSS. | PyQt6 desktop application (`Architect/gui/`). |
| **Components** | 10+ widget types (EnvelopeChart, CvdHeatmap, LimbMesh, TechnicalGauge, TradePlan, PatternScanner, MarketBreadthRadar, etc.), GridCanvas drag-reorder, McpConsole, GalleryDrawer. | 3 widgets: `TickerTape` (live price strip with stale-feed desaturation), `CommandBar`, `UnifiedChartTab`. |
| **Data flow** | Mock market data via `ops/marketData.ts`, tvremix adapters for TradingView-style data, Zustand store with 216 lines. | `ccxt.pro` async daemon feeding ticker tape; no other data pipeline. |
| **Performance work** | 3 optimization cycles documented in `.jules/specter.md`: re-render churn 10→1 per tick, closed-console zero-work, SVG ID scoping via `useId()`. | Ticker tape has per-feed stale detection via `QGraphicsColorizeEffect` desaturation. No measured optimizations. |
| **Tests** | Custom zero-dep test harness (`frontend/scripts/ui-test.mjs`), 6 test files verifying memo contracts, snapshot audits, gradient scoping. | None. |

### 3.5 Continuous Learning Engine

| Aspect | Blueprint | Jules |
|---|---|---|
| **TypeScript engine** | `src/learning/` — 10 files (~2,000 lines): outcome ingestion, feedback processing, Wilson-score skill profiles, SM-2 spaced repetition, error pattern detection, knowledge base, risk guards, evaluation pipeline (`defineEval` with RLHF samples). | **Not present.** |
| **Schemas** | 8 JSON schemas under `schemas/learning/` (outcome, feedback, knowledge_entry, skill, error_pattern, learning_task, schedule, risk_guard). | **Not present.** |
| **API endpoints** | 7 REST endpoints (`/learning/outcomes`, `/feedback`, `/state`, `/research`, `/guidance`, `/schedules/run`, `/schedules/install-defaults`). | **Not present.** |

### 3.6 Models / ML

| Aspect | Blueprint | Jules |
|---|---|---|
| **ONNX export** | Not present. | `Architect/models/export_regime_onnx.py` — 42 lines; PyTorch → ONNX export with dynamic batch sizes. |
| **Model weights** | Not present. | `Architect/models/weights/omega_regime_16d.onnx` (833 bytes) + `.data` file. |

### 3.7 Protocol & Schemas

| Aspect | Blueprint | Jules |
|---|---|---|
| **Protocol spec** | 492-line normative document; intent/result envelopes, timer semantics, schedule triggers, error codes, job lifecycle, rights/sandbox, scaling profiles. | **Not present.** |
| **JSON Schemas** | `intent.schema.json` (632 lines), `result.schema.json` (416 lines), `operations.json` (197 lines) — all JSON Schema 2020-12. | **Not present.** |
| **Schema parity** | `tests/test_schema_parity.py` — 392 lines; machine-verified that parser and schema agree in both directions. | **Not present.** |

### 3.8 Testing & CI

| Aspect | Blueprint | Jules |
|---|---|---|
| **Unit tests** | 15 test files, 555+ tests: protocol (261), policy (233), orchestrator (409), planner (183), scheduler (414), unlimited (375), schema parity (392), CLI contract (337), limbs (174), bootstrap (316), triads (1,644). | 1 file, ~20 assertions: import checks, dummy daemon, GUI window creation. |
| **E2E** | `scripts/ci_e2e_unlimited.py` — 171 lines; 20 proofs over real CLI (timers, triggers, clock coherence, cleanup). | None. |
| **Benchmarks** | `scripts/nexus_bench.py` — 986 lines; in-process A/B for IPC, scheduler, archive (3 triads of optimizations). | None. |
| **CI** | `ci/neu.yml` — 115 lines; Python 3.11/3.12/3.13 matrix, ruff, mypy, E2E, schema parity, exit-code contract. Also `ci-evals.yml` for the TS learning engine. | None. |
| **Quality gate** | `make check` = compile + ruff + mypy + 241+ tests + E2E. | `make` in `Architect/` — just `pip install -r requirements.txt`. |

---

## 4. What the Blueprint Specifies That Jules Hasn't Built *Yet*

Many of these are targeted by Jules's later phases (see §4b). This table reflects
**Phase 1 (Foundation) only** — what has shipped, not what is planned.

| Blueprint Feature | Phase 1 Status | Expected in Jules Phase |
|---|---|---|
| **Protocol 1.2 envelopes** (intent → result) | ❌ Not present | Phase 1 (schema extension) |
| **File-based transport** (`runtime/inbox/`, `runtime/outbox/`, `runtime/archive/`) | ❌ Not present | — |
| **Timer system** (deadline + unlimited modes, safety net, t₀, elapsed_s) | ❌ Not present | — |
| **Schedule triggers** (edge-triggered `when`, interval `every_s`, marks `at_s`) | ❌ Not present | — |
| **Autodidactic correction** (2nd attempt with diagnosis, scaled timer, forbidden repeats) | ❌ Not present | Phase 2 (reflection planning) |
| **Orchestrator** (runner, scheduler, planner, event bus, transport, locks) | ❌ Not present | — |
| **Policy / sandbox** (path resolution, denied globs, constitution guard, elevation) | ❌ Not present | Phase 3 (safe self-modification) |
| **Bootstrap limb** (fs operations with backup + hash verification) | ❌ Not present | Phase 3 (manifest updates) |
| **Event bus** (NDJSON events with clock_s, job correlation, UDS broadcast, shared-memory ring) | ❌ Not present | — |
| **Archive / ledger** (compaction, index, SHA-256 digests, cross-day verification) | ❌ Not present | Phase 1 (baseline retrieval) |
| **Continuous learning engine** (outcomes, feedback, skills, error patterns, knowledge base) | ❌ Not present | Phase 4 (RLHF integration) |
| **Performance triads** (IPC optimization, scheduler fast-path, archive indexing) | ❌ Not present | — |
| **Scaling profiles** (dev → scale) | ❌ Not present | — |
| **Phase 3 Ouroboros test** (self-modification via bootstrap limb) | ❌ Not present | Phase 3 (safe self-modification) |
| **Phase 4 HTTP bridge** (middleware ↔ orchestrator via events) | ❌ Not present | — |
| **Trajectory visualization / alignment tracking** | ❌ Not present | Phase 5 (self-model & insights) |

### 4b. Jules's 5-Phase Roadmap ↔ Blueprint Feature Mapping

| Jules Phase | Status | What It Builds | Blueprint Equivalent |
|---|---|---|---|
| **Phase 1: Foundation** | ✅ Complete | Schema extension, post-mortem triggers, baseline retrieval, state machines, risk invariants, GUI shell, exchange daemon | Protocol 1.2 foundation, `core/protocol.py`, risk/policy layer, `limbs/registry.json` |
| **Phase 2: Reflection Planning** | 🔄 In Progress | Memory-driven planning, confidence scoring, agent assignments | `orchestrator/planner.py` (autodidactic diagnosis + correction intent design), `core/kernel.py` (verdicts, confidence gating) |
| **Phase 3: Safe Self-Modification** | 🔜 Next | `validateManifestUpdate`, safety validation | Ouroboros test (Phase 3 in blueprint), bootstrap limb writing to `orchestrator/events.py`, policy/sandbox enforcement |
| **Phase 4: RLHF Integration** | 🔜 Next | Feedback UI, preference model updater | Continuous learning engine (`src/learning/`), outcome ingestion, feedback processing, Wilson-score skill profiles, `defineEval` pipeline |
| **Phase 5: Self-Model & Insights** | 🔜 Next | Trajectory visualization, alignment tracking dashboards | No direct blueprint equivalent — goes *beyond* the blueprint with alignment monitoring |

**Key insight:** Jules's Phases 2–5 map closely to the blueprint's later phases
(blueprint Phases 3–4 + the continuous learning engine). The two systems are
converging toward similar goals — self-modification, learning from feedback,
alignment tracking — but via **very different architectural paths** (see §6).

---

## 5. What Jules Built That the Blueprint Doesn't Cover

| Architect Feature | Blueprint Status |
|---|---|
| **PyQt6 desktop GUI** (Global Market Terminal) | Blueprint has a web frontend (React/Next.js), not a desktop terminal |
| **Orderbook imbalance (OBI)** calculation | Not in blueprint |
| **Intra-bar volume delta** (footprint map / Zeiierman port) | Not in blueprint |
| **AC Gravity engine** (active/reactive power, L2+L3+Polymarket gravity field) | Not in blueprint |
| **Risk invariant checker** (6 axioms: feed integrity, forbidden zone, leverage, slippage, power factor, vault reserve) | Blueprint has policy/sandbox but not trading-specific risk invariants |
| **ONNX regime model** (16-dimensional market regime classifier) | Not in blueprint |
| **Exchange feed daemon** (ccxt.pro WebSocket tickers) | Not in blueprint (Phase 4 mentions HTTP bridge, not exchange feeds) |
| **Qdrant vector memory** integration | Planned for Phase 4 but not implemented in blueprint |
| **Gemini GenAI** integration (journal entries, DSR reflection) | Blueprint uses generic "LLM + deterministic core"; Jules picked Gemini specifically |
| **Snap packaging** (Snapcraft YAML for Linux desktop distribution) | Not in blueprint |
| **Ticker tape with stale-feed detection** (per-feed desaturation via QGraphicsColorizeEffect) | Blueprint frontend has widgets but no per-widget staleness visual treatment |
| **HDBSCAN clustering** engine | Not in blueprint |
| **Kraken FIX API + staking auto-compound** | Not in blueprint |

---

## 6. Structural Differences

### 6.1 Dependency Model

```
Blueprint (core/orchestrator/limbs):     Jules (Architect/):
┌─────────────────────────────┐          ┌─────────────────────────────┐
│ Python 3.11+ stdlib ONLY    │          │ PyQt6                       │
│ Zero pip install needed     │          │ torch                       │
│ No framework, no runtime    │          │ onnx                        │
│ Own JSON schema validator   │          │ qdrant-client               │
│ Own event bus               │          │ ccxt.pro                    │
│ Own archive system          │          │ google-genai                │
└─────────────────────────────┘          │ numpy                       │
                                         │ pydantic-settings           │
                                         │ hdbscan                     │
                                         └─────────────────────────────┘
```

### 6.2 Transport & Persistence

| | Blueprint | Jules |
|---|---|---|
| **Intent delivery** | File in `runtime/inbox/<limb>/<intent_id>.json` | Not applicable — no orchestrator |
| **Result return** | stdout JSON → archive in `runtime/archive/` | Not applicable |
| **State persistence** | JSON files in `runtime/` with fsync, atomic writes, SHA-256 digests | Not present |
| **Event streaming** | NDJSON on stderr + UDS datagram broadcast + shared-memory ring | Not present |

### 6.3 Error Handling

| | Blueprint | Jules |
|---|---|---|
| **Errors** | 16+ error codes (E_SCHEMA_INVALID through E_INTERNAL); structured diagnosis; autodidactic correction loop; escalation to human. | `try/except ImportError` fallbacks; return `(False, "reason string")` tuples from risk checks. |
| **Safety** | Constitution Guard (`human_only_globs`), sandbox path resolution, elevation levels, denied globs, backup-before-write. | `.env` excluded via `.gitignore`; risk invariants (leverage cap, slippage budget, vault reserve). |

### 6.4 Testability Philosophy

| | Blueprint | Jules |
|---|---|---|
| **Unit tests** | 555+ tests with real subprocesses, real timers, virtual clocks | 1 smoke test (imports + window creation) |
| **Determinism** | Virtual clock injection for scheduler; no `sleep()` in tests | Not addressed |
| **Schema parity** | Machine-verified parser ↔ schema agreement in both directions | Not addressed |
| **Performance regression** | Benchmark script with in-process A/B, bounded caches, guarded metrics | Not addressed |

---

## 7. Alignment Score

### What exists today (Phase 1 only)

| Category | Score | Notes |
|---|---|---|
| **Directory structure** | ⭐⭐⭐ | Jules followed the 4-folder contract (`core/`, `limbs/`, `gui/`, `models/`) but added `evals/` (empty) and `snap/` instead of `protocol/`, `orchestrator/`, `prompts/` |
| **"Pure Python" intent** | ⭐⭐ | Jules claims "pure Python" but uses 8+ third-party packages; the blueprint's core is genuinely stdlib-only |
| **Risk / policy concept** | ⭐⭐⭐ | Both have policy/risk enforcement, but Jules's is trading-specific while the blueprint's is execution-security-specific |
| **Daemon/process supervision** | ⭐⭐ | Jules has a daemon skeleton; the blueprint has a full 2,000-line supervised runner with tick loops, slot locks, heartbeats |
| **AI/LLM integration** | ⭐⭐ | Blueprint integrates LLM as the "intelligent core" with evaluation; Jules has a Gemini stub returning hard-coded strings |
| **GUI / UI** | ⭐⭐⭐⭐ | Both have UIs — blueprint has a richer web UI with 10+ widget types, Jules has a functional desktop terminal. Different tech stacks. |
| **Protocol / contracts** | ⭐ | Blueprint has a 492-line normative protocol with machine-checked parity; Jules has no formal protocol or schemas |
| **Testing rigor** | ⭐ | Blueprint: 555+ tests, E2E, benchmarks. Jules: 1 smoke test. |
| **Trading domain** | ⭐⭐⭐⭐⭐ | Jules's code is deeply domain-specific (orderbook imbalance, AC gravity, regime models, exchange feeds) — the blueprint has no trading logic at all |
| **Phase 1 coverage of blueprint** | **~15%** | Jules implemented the GUI shell, 3 math/intelligence modules, a config, and state machine enums — but none of the orchestrator, protocol, scheduler, transport, learning engine, or execution infrastructure |

### Projected coverage after all 5 phases

| Blueprint Feature | Jules's Planned Coverage |
|---|---|
| Self-modification (Ouroboros) | ✅ Phase 3 targets this directly with `validateManifestUpdate` + safety validation |
| Autodidactic correction / planning | ✅ Phase 2 (reflection planning) mirrors `orchestrator/planner.py`'s diagnosis → correction loop |
| Continuous learning / RLHF | ✅ Phase 4 explicitly adds feedback UI + preference model updater |
| Alignment tracking | ✅ Phase 5 goes *beyond* the blueprint with trajectory visualization |
| Formal protocol + schemas | ✅ Phase 1 already includes schema extension (though the blueprint's is far more comprehensive) |
| File-based transport / archive | ⚠️ Not addressed — Jules uses external services (Qdrant, APIs) where the blueprint uses local files |
| Timer / scheduler / supervision loop | ⚠️ Not addressed — Jules's daemon supervisor is an exchange feed watcher, not a job scheduler |
| Policy / sandbox / constitution guard | ⚠️ Jules has trading risk invariants but no execution-security sandbox |

**Projected total alignment: ~50–60%** if Phases 2–5 ship as described — with the
remaining gap being architectural choices (external services vs. stdlib-only,
PyQt6 vs. web, different transport models).

---

## 8. Summary

The **NIO Omega Blueprint** is a comprehensive, heavily tested AI operating system with a formal protocol, a full orchestrator (job lifecycle, scheduling, autodidactic correction, event bus, archive), a continuous-learning engine, and a phased bootstrap plan — all built on a zero-dependency, file-transport, stdlib-only foundation.

**Jules's OMEGA Architect** is an **active 5-phase project** building a pure-Python AI trading + self-improving agent system. Phase 1 (Foundation) has shipped — state machines, trading risk invariants, GUI shell, exchange daemon, GenAI and vector memory stubs, ONNX regime model. Phases 2–5 are planned:

| Phase | Focus | Status |
|---|---|---|
| **1 — Foundation** | Schema extension, post-mortem triggers, baseline retrieval | ✅ Complete |
| **2 — Reflection Planning** | Memory-driven planning, confidence scoring, agent assignments | 🔄 In Progress |
| **3 — Safe Self-Modification** | `validateManifestUpdate`, safety validation | 🔜 Next |
| **4 — RLHF Integration** | Feedback UI, preference model updater | 🔜 Planned |
| **5 — Self-Model & Insights** | Trajectory visualization, alignment tracking dashboards | 🔜 Planned |

### Where They Converge

Both systems are building toward the same core goals:
- **Self-improvement** — the blueprint via autodidactic correction + Ouroboros; Jules via reflection planning + safe self-modification
- **Learning from outcomes** — the blueprint via continuous learning engine; Jules via RLHF integration
- **Safety constraints** — the blueprint via policy/sandbox/constitution guard; Jules via 6 risk invariants + manifest validation
- **Formal contracts** — the blueprint via Protocol 1.2 + JSON schemas; Jules via schema extension

### Where They Diverge

| | Blueprint | Jules |
|---|---|---|
| **Dependency model** | Stdlib-only, zero pip install | External services (Gemini, Qdrant, ccxt, Kraken, AlphaVantage) |
| **UI stack** | React/Next.js web frontend | PyQt6 desktop terminal |
| **Transport** | File-based (`runtime/`), deterministic, auditable | External APIs + Qdrant cloud + WebSocket feeds |
| **Domain** | Generic AI orchestration (any task) | Trading-specific (market microstructure, regime detection, risk management) |
| **Maturity** | Production-grade (Phases 1–2 done, 555+ tests) | Early-stage (Phase 1 scaffold, 1 test) |
| **What Jules has that blueprint lacks** | — | Trading domain engines (OBI, AC Gravity, Judge M8), desktop GUI, exchange integration, ONNX regime model |
| **What blueprint has that Jules lacks** | Full orchestrator, protocol, scheduler, event bus, archive, learning engine, 555+ tests, 3 performance triads | — |

### The Bottom Line

These are **two parallel approaches to self-improving AI systems** that happen to live in the same repository. The blueprint is further along and more rigorously tested. Jules's OMEGA brings deep trading-domain expertise and a desktop-native approach. Their Phase 2–5 roadmap shows clear intent to converge with the blueprint's later features (reflection, self-modification, RLHF, alignment tracking) — just via a different architectural path.

**Today's coverage: ~15%.** **Projected after all 5 phases: ~50–60%** — with the remaining gap being architectural choices (external services vs. stdlib-only, PyQt6 vs. web, different transport models) rather than missing feature intent.
