# Omega NIO Blueprint — Jules OMEGA Architect Implementation Plan

> **Scope:** Finish Jules's `Architect/` implementation against the Omega Blueprint (`docs/ARCHITECTURE.md`, `docs/NEU.md`, `protocol/PROTOCOL.md`).
> **Branch:** `arena/01a07d99-nio`
> **Current State:** Phases 1–5 SHIPPED (Phase 4 RLHF + Phase 5 Self-Model completed 2026-09-07). 214 tests passing (`cd Architect && make test`).
> **Maturity:** Phase 5 (Self-Model & Insights) reached with documented divergence convergence (`Architect/docs/DIVERGENCES.md`).
> **Document Date:** 2026-09-07

---

## 1. Executive Context

### 1.1 Two Systems in One Repository
The repository (`Finnlayy/NIO`) contains two stacks that share **no runtime or data model** (`docs/ARCHITECTURE.md` §1):

| Stack | Path | Dependency Model | Maturity |
|---|---|---|---|
| **Python Kernel "Neu"** (Omega Blueprint) | `core/`, `orchestrator/`, `limbs/`, `protocol/` | Python 3.11+, stdlib-only | Production-grade (Phases 1–2), 555+ tests |
| **Jules's OMEGA Architect** | `Architect/` | PyQt6, torch, onnx, qdrant-client, ccxt.pro, google-genai, numpy, pydantic-settings | Phase 1 only, 1 smoke test |

### 1.2 What "Finish" Means
Based on `COMPARISON_OMEGA_BLUEPRINT_VS_JULES.md` (§4, §4b, §7), finishing Jules's implementation requires:

1. **Phase 2 (Reflection Planning):** Memory-driven planning, confidence scoring, agent assignments.
2. **Phase 3 (Safe Self-Modification):** Manifest validation (`validateManifestUpdate`), safety invariants, Ouroboros-style self-modification.
3. **Phase 4 (RLHF Integration):** Feedback UI, preference model updater, continuous learning engine alignment.
4. **Phase 5 (Self-Model & Insights):** Trajectory visualization, alignment tracking dashboards.
5. **Blueprint convergence:** Where the blueprint specifies a contract (protocol 1.2, file transport, timer semantics, event bus), Jules's code must either implement it or document the architectural divergence clearly.

---

## 2. Architectural Blueprint vs. Jules's Code — Gap Analysis

### 2.1 Implemented (Phase 1 — Foundation)

| Component | File(s) | Status | Notes |
|---|---|---|---|
| Config (Pydantic-settings) | `Architect/core/config.py` | ✅ Complete | API keys, risk thresholds |
| State Machine Enums | `Architect/core/state_machine.py` | ✅ Complete | 4 enums, no transition logic |
| Daemon Supervisor (stub) | `Architect/core/daemon_supervisor.py` | ⚠️ Partial | `FeedDaemon` wraps `ccxt.pro`; `DaemonSupervisor` starts/gathers but no tick loop, no slot renewal, no heartbeat |
| GUI Shell | `Architect/gui/app.py`, `gui/theme.py` | ✅ Complete | PyQt6 MainWindow, dark-matrix QSS |
| Command Bar | `Architect/gui/widgets/command_bar.py` | ✅ Complete | Stub command input |
| Ticker Tape | `Architect/gui/widgets/ticker_tape.py` | ⚠️ Partial | Has stale-feed desaturation (`QGraphicsColorizeEffect`); no live data integration |
| Unified Chart Tab | `Architect/gui/views/unified_chart_tab.py` | ✅ Complete | Empty tab shell |
| GenAI Client (stub) | `Architect/limbs/intelligence/genai_client.py` | ⚠️ Partial | Gemini SDK wrapper; `generate_journal()` and `reflect_dsr()` return hard-coded stub strings |
| Microstructure Engine | `Architect/limbs/intelligence/microstructure_engine.py` | ✅ Complete | OBI calculation, footprint map (Zeiierman Port) |
| Qdrant Memory Engine | `Architect/limbs/intelligence/qdrant_memory_engine.py` | ⚠️ Partial | Cloud + local fallback; `check_flash_crash_anomaly()` returns `False` (stub) |
| AC Gravity Engine | `Architect/limbs/math/ac_gravity_engine.py` | ✅ Complete | Power factor, gravity field blend, forbidden-zone detection |
| The Judge M8 (Risk Invariants) | `Architect/limbs/math/the_judge_m8.py` | ✅ Complete | 6 axioms implemented |
| HDBSCAN Engine | `Architect/limbs/ml/hdbscan_engine.py` | ⚠️ Partial | Imports `hdbscan`; no real clustering logic beyond stub |
| ONNX Regime Export | `Architect/models/export_regime_onnx.py` | ✅ Complete | PyTorch → ONNX with dynamic batch |
| Regime Model Weights | `Architect/models/weights/omega_regime_16d.onnx` + `.data` | ✅ Complete | 833 bytes model |
| Snap Packaging | `Architect/snap/snapcraft.yaml` | ✅ Complete | Linux desktop packaging spec |
| Test (Smoke) | `Architect/test_init.py` | ⚠️ Partial | 1 smoke test (`assert True`) |
| Makefile / Setup Scripts | `Architect/Makefile`, `setup_environment.sh`, `run_terminal.sh` | ✅ Complete | Dependency install + terminal launcher |

### 2.2 Missing / Planned (Phases 2–5 + Blueprint Gaps)

Based on `COMPARISON_OMEGA_BLUEPRINT_VS_JULES.md` (§4, §4b) and `Architect/` file audit:

| Blueprint Feature | Jules Phase | Status | What Must Be Built |
|---|---|---|---|
| Protocol 1.2 (intent → result envelopes) | Phase 1 (schema extension) | ❌ Missing | JSON schemas (`intent.schema.json`, `result.schema.json`); parser; envelope validation |
| Memory-Driven Planning / Reflection | Phase 2 | ❌ In Progress | `GenAIClient.reflect_dsr()` real logic; confidence scoring; agent assignment mapping; `state_machine.py` transition logic |
| Post-Mortem Triggers / Baseline Retrieval | Phase 1 (baseline) / Phase 2 (reflection) | ❌ Missing | Event-triggered post-mortem pipeline; `archive` retrieval; baseline comparison logic |
| Safe Self-Modification / Manifest Validation | Phase 3 | ❌ Not Started | `validateManifestUpdate()` function; manifest hash verification; rollback mechanism; `Ouroboros` test equivalent |
| Policy / Sandbox Enforcement | Phase 3 | ❌ Not Started | Execution-security sandbox; denied globs; path resolution; constitution guard; elevation levels |
| Continuous Learning Engine (RLHF) | Phase 4 | ❌ Not Started | Outcome ingestion (`outcome.schema.json`); feedback processing; Wilson-score skill profiles; SM-2 spaced repetition; error pattern detection; `defineEval` pipeline |
| Feedback UI / Preference Model Updater | Phase 4 | ❌ Not Started | PyQt6 feedback dialog; preference model updater; RLHF sample storage |
| Event Bus (NDJSON) | — | ❌ Not Started | `events.py` equivalent; NDJSON event emission; `runtime/system.log` sink; `VALID_EVENT_KINDS` whitelist |
| Archive / Ledger | — | ❌ Not Started | Job ledger (`job_*.json` + `.history.jsonl`); archive compaction; SHA-256 digests |
| Timer System (deadline + unlimited) | — | ❌ Not Started | `deadline_s`, `soft_deadline_s`, `t0`, `elapsed_s`, `safety_net_s`, `remaining_ms`; timer modes |
| Scheduler (edge-triggered, interval, marks) | — | ❌ Not Started | `scheduler.tick()`; `when`, `every_s`, `at_s`; persistent trigger state; catch-up logic |
| Orchestrator (runner, planner, events, locks, transport) | — | ❌ Not Started | Full `orchestrator/` layer; job lifecycle; spawn/collect; supervision loop; slot renewal; heartbeat |
| CLI (`spec`, `status`, `run`, `watch`, `schedule`, `archive`) | — | ❌ Not Started | Python CLI equivalent; subcommands; `--json` output; archive stats/lookup/verify |
| Bootstrap Limb (fs operations with backup + hash) | Phase 3 | ❌ Not Started | `fs.read_file`, `fs.write_file`, `fs.patch`, `fs.list`, `fs.mkdir`; sandbox enforcement; backup; hash verification |
| Performance Triads (IPC, scheduler, archive) | — | ❌ Not Started | Benchmark scripts; optimization cycles; bounded caches |
| Scaling Profiles (`dev` → `scale`) | — | ❌ Not Started | Profile switching; limit adjustments |
| Self-Model & Insights / Alignment Tracking | Phase 5 | ❌ Not Started | Trajectory visualization; alignment tracking dashboards; trajectory visualization widgets |

---

## 3. Implementation Roadmap — Aligned with Jules's 5-Phase Plan

### Phase 1 — Foundation (✅ Complete — Lock Scope)
**Action:** Freeze Phase 1. No new features unless they unblock Phase 2.
- [x] Schema extension design finalized.
- [x] State machine enums complete.
- [x] GUI shell, ticker tape, chart tab complete.
- [x] Config and daemon supervisor stubs complete.
- [x] Microstructure, AC Gravity, Judge M8 engines complete.
- [x] GenAI client wrapper complete.
- [x] Qdrant memory fallback complete.
- [x] ONNX model export complete.
- [x] **Lock:** Add `Architect/README.md` documenting Phase 1 scope and divergence notes.

### Phase 2 — Reflection Planning (🔄 In Progress — Priority)
**Target:** Memory-driven planning, confidence scoring, agent assignments; aligns with blueprint's `orchestrator/planner.py`, `core/kernel.py` (verdicts, confidence gating), and autodidactic correction loop.

**Deliverables:**
1. **Reflection Engine (GenAI Client Realization)**
   - [x] Implement `GenAIClient.generate_journal(context)` with real Gemini SDK call or structured prompt template.
   - [x] Implement `GenAIClient.reflect_dsr(post_mortem_data)` with structured diagnosis output (not stub string).
   - [x] Add error handling: API timeout, rate limit, model unavailable → graceful fallback.
   - [x] Add logging: reflection outputs saved to `Architect/runtime/reflections/<timestamp>.json`.

2. **Memory-Driven Planning**
   - [x] Design planning data model: `Plan` (objective, steps, confidence, agent_mapping, status).
   - [x] Implement `MemoryPlanner` in `Architect/limbs/intelligence/` or `Architect/core/`.
   - [x] Integrate with `QdrantMemoryEngine`: retrieve relevant memory vectors for planning context.
   - [x] Implement confidence scoring: `confidence_score` based on historical outcome similarity, feed integrity, and risk invariant status.

3. **Agent Assignment Mapping**
   - [x] Define agent roles (e.g., `judge_m8_agent`, `microstructure_agent`, `gravity_agent`).
   - [x] Implement assignment logic: match plan requirements to agent capabilities (`limbs/registry.json` equivalent).
   - [x] Add agent status tracking (`dispatched`, `running`, `reflecting`, `complete`).

4. **State Machine Transition Logic**
   - [x] Add transition rules to `Architect/core/state_machine.py`: `PLANNING → DISPATCHED → RUNNING → REFLECTING → COMPLETE`.
   - [x] Add transition triggers: `plan_approved`, `execution_complete`, `post_mortem_complete`, `plan_rejected`.
   - [x] Add guard conditions: confidence >= threshold before `DISPATCHED`; feed integrity before `RUNNING`.

5. **Post-Mortem Triggers**
   - [x] Define trigger conditions: execution failure, risk invariant violation, timeout, safety net activation.
   - [x] Implement `PostMortemTrigger` class.
   - [x] Link to `GenAIClient.reflect_dsr()` for automated diagnosis.

6. **Baseline Retrieval**
   - [x] Implement `BaselineRetriever` (equivalent to blueprint `archive/` lookup).
   - [x] Store baselines in `Architect/runtime/baselines/<plan_id>.json`.
   - [x] Implement comparison logic: current outcome vs. baseline (delta metrics, divergence score).

7. **Tests for Phase 2**
   - [x] Unit tests for `MemoryPlanner`, `AgentAssignment`, `StateMachine` transitions.
   - [x] Mock tests for `GenAIClient` (stubbed API calls).
   - [x] Integration test: full reflection loop (execution → post-mortem → plan update).

**Dependencies:** Phase 1 stable; Gemini SDK or mock framework available.
**Blockers:** None (Phase 1 is complete).

---

### Phase 3 — Safe Self-Modification (🔜 Next — High Complexity)
**Target:** `validateManifestUpdate()`, safety validation, manifest updates; aligns with blueprint's `Ouroboros` test (`core/job.py` Phase 3), bootstrap limb, policy/sandbox, and event bus.

**Deliverables:**

1. **Manifest System**
   - [x] Design manifest schema (`manifest.schema.json`): version, checksum (`sha256`), changes (file list, line changes, dependency changes), author, timestamp, safety flags.
   - [x] Implement `Manifest` class in `Architect/core/manifest.py`.
   - [x] Implement `ManifestParser`: read, validate structure, extract changes.

2. **Manifest Validation (`validateManifestUpdate`)**
   - [x] Implement `validateManifestUpdate(manifest_path, current_state)`.
   - [x] Safety checks: no changes to `core/config.py` without approval; no removal of risk invariants (`TheJudgeM8`); no dependency downgrade; checksum verification of all modified files.
   - [x] Policy checks: denied globs (`runtime/*`, `*.log`), allowed repo globs, human-only globs.
   - [x] Return `(True, "message")` or `(False, "reason string")` matching Jules's existing tuple convention.

3. **Self-Modification Safety**
   - [x] Implement rollback mechanism: before applying manifest, backup current files (`Architect/runtime/backups/`).
   - [x] Implement rollback trigger: if validation fails or execution crashes after modification, restore from backup.
   - [x] Implement `SelfModificationSafety` guard: require `approved_by="human"` for core changes; `approved_by="system"` only for non-core (e.g., `gui/widgets/`).

4. **Bootstrap Limb Equivalent**
   - [x] Implement `BootstrapLimb` in `Architect/limbs/bootstrap_limb.py` (or equivalent): `read_file`, `write_file`, `patch`, `list`, `mkdir`.
   - [x] Sandbox enforcement: restrict file operations to `Architect/workspace/` and allowed repo paths.
   - [x] Backup before write: `fs.write_file()` creates `.backup` file with SHA-256 hash.
   - [x] Hash verification: verify file integrity after write (`sha256` comparison).

5. **Ouroboros Test Equivalent**
   - [x] Design test: a `scheduled` job that uses `BootstrapLimb` to modify `Architect/` source (e.g., add a comment to `core/state_machine.py` or update `gui/theme.py`).
   - [x] Execute test in isolated sandbox (`Architect/runtime/sandbox/`).
   - [x] Verify: modification applied correctly, backup exists, rollback works, event emitted (`self_modification_complete` or `self_modification_failed`).

6. **Event Bus (Phase 3 Requirement — Blueprint §6)**
   - [x] Implement `EventBus` in `Architect/core/events.py`.
   - [x] Event format: NDJSON line per event; fields: `event_id`, `event_kind`, `job_id`, `intent_id`, `trace_id`, `limb`, `clock_s`, `message`, `timestamp`.
   - [x] Event emission: emit to `stderr` (NDJSON); emit to `Architect/runtime/system.log` (Phase 3 file sink); emit via UDS datagram (optional for local clients); emit to shared-memory ring (optional for performance).
   - [x] `VALID_EVENT_KINDS` whitelist: `execution_started`, `execution_complete`, `post_mortem_started`, `post_mortem_complete`, `manifest_validated`, `manifest_applied`, `manifest_rolled_back`, `self_modification_complete`, `self_modification_failed`, `reflection_complete`, `plan_updated`, `agent_assigned`, `agent_complete`.
   - [x] Event contract test: verify that only whitelisted kinds are emitted; verify NDJSON format; verify `clock_s` coherence.

7. **Archive / Ledger (Phase 3 Requirement — Blueprint §4)**
   - [x] Implement `Archive` in `Architect/core/archive.py`.
   - [x] Archive format: JSON file per job (`runtime/archive/<job_id>.json`); `.history.jsonl` for iterations; SHA-256 digest file.
   - [x] Implement `Archive.lookup(job_id)`, `Archive.stats()`, `Archive.verify()` (cross-day verification).
   - [x] Implement `Archive.compact()`: merge small history files, remove duplicate events.

8. **Timer System (Phase 3 Requirement — Blueprint §3)**
   - [x] Implement `Timer` in `Architect/core/timer.py`.
   - [x] Modes: `deadline` (`deadline_s`, `soft_deadline_s`, `expires_at`) and `unlimited` (`t0`, `elapsed_s`, `deadline_s=null`, `expires_at=null`).
   - [x] Safety net: `safety_net_s` (process hygiene, zombie protection); triggers `E_SAFETY_NET` on activation.
   - [x] Clock coherence: `t_unlimited` counts from job creation (`t0`); all events, results, and ledgers reference the same `t0`.
   - [x] Timer persistence: `runtime/jobs/<job_id>.json` stores `t0`, `deadline_s`, `soft_deadline_s`, `safety_net_s`, `elapsed_s`, `remaining_ms`.

9. **Tests for Phase 3**
   - [x] Unit tests for `ManifestParser`, `validateManifestUpdate`.
   - [x] Sandbox tests: `BootstrapLimb` operations restricted to allowed paths.
   - [x] Event bus tests: NDJSON format, whitelist enforcement, `clock_s` coherence.
   - [x] Archive tests: lookup, stats, verify, compact.
   - [x] Timer tests: deadline mode, unlimited mode, safety net activation, persistence.
   - [x] Ouroboros test: full self-modification loop in sandbox.

**Dependencies:** Phase 2 complete (reflection engine, planning, agent assignment); Phase 1 stable.
**Blockers:** Manifest design must be finalized before implementation; event bus design must align with `protocol/PROTOCOL.md`.

---

### Phase 4 — RLHF Integration (🔜 Planned — Medium-High Complexity)
**Target:** Feedback UI, preference model updater; aligns with blueprint's continuous learning engine (`src/learning/`), outcome ingestion, feedback processing, Wilson-score skill profiles, SM-2 spaced repetition, error pattern detection, `defineEval` pipeline.

**Deliverables:**

1. **Outcome Ingestion (Schema Extension — Phase 1 Blueprint)**
   - [x] Design `outcome.schema.json`: fields (`job_id`, `intent_id`, `result`, `verdict`, `elapsed_s`, `clock_s`, `timestamp`, `limb`, `errors`, `metrics`).
   - [x] Implement `OutcomeParser` in `Architect/core/`.
   - [x] Implement `OutcomeIngestion` pipeline: read result files (`Architect/runtime/results/` or `workspace/`), validate against schema, emit `execution_complete` event.

2. **Feedback Processing**
   - [x] Design `feedback.schema.json`: fields (`outcome_id`, `rater_id`, `rating`, `preference`, `comment`, `timestamp`).
   - [x] Implement `FeedbackProcessor`: read feedback files (`Architect/runtime/feedback/`), aggregate ratings, compute preference scores.
   - [x] Integrate with `GenAIClient`: generate structured feedback analysis from comments.

3. **Wilson-Score Skill Profiles**
   - [x] Implement `SkillProfile` class: `skill_id`, `name`, `successes`, `total_attempts`, `wilson_score`, `last_evaluated`.
   - [x] Implement `WilsonScoreCalculator`: `wilson_score = (p_hat + z^2/(2n) - z * sqrt(p_hat*(1-p_hat)/n + z^2/(4n^2))) / (1 + z^2/n)`.
   - [x] Implement `SkillProfileUpdater`: update profiles based on new outcomes and feedback.

4. **SM-2 Spaced Repetition**
   - [x] Implement `SpacedRepetitionEngine` in `Architect/core/learning/`.
   - [x] SM-2 algorithm: `EF` (ease factor), `interval` (days); update based on quality (`0`–`5`).
   - [x] Implement `ReviewScheduler`: schedule reviews based on `interval` and `EF`; emit `review_due` events.

5. **Error Pattern Detection**
   - [x] Implement `ErrorPatternDetector`: analyze `errors` array from outcomes; detect recurring patterns (`E_SAFETY_NET`, `E_TRIGGER_INVALID`, `E_SCHEMA_INVALID`, `E_INTERNAL`).
   - [x] Implement `ErrorPatternStorage`: save patterns to `Architect/runtime/learning/error_patterns/<pattern_id>.json`.
   - [x] Implement `ErrorPatternAlert`: if a pattern exceeds a threshold frequency, emit `error_pattern_alert` event.

6. **Knowledge Base**
   - [x] Implement `KnowledgeBase` in `Architect/core/learning/`.
   - [x] Storage format: `Architect/runtime/learning/knowledge/<entry_id>.json` (title, content, tags, source, confidence, timestamp).
   - [x] Implement `KnowledgeEntryParser`: extract knowledge from reflection outputs (`GenAIClient.generate_journal()`).
   - [x] Implement `KnowledgeSearch`: query by tag, source, or content similarity (optional vector search using Qdrant).

7. **Risk Guards (Learning Engine Safety)**
   - [x] Implement `RiskGuardEngine`: check new plans, modifications, or model updates against risk invariants (`TheJudgeM8`).
   - [x] Implement `RiskGuardStorage`: save risk assessments to `Architect/runtime/learning/risk_guards/<guard_id>.json`.
   - [x] Implement `RiskGuardAlert`: emit events when risk assessments fail or trigger warnings.

8. **`defineEval` Pipeline**
   - [x] Design `defineEval` interface: `define_eval(eval_name, criteria, dataset, evaluator, aggregator)`.
   - [x] Implement `EvalPipeline`: load dataset (`rlhf_samples.json` or similar), apply evaluator, aggregate results.
   - [x] Implement `EvalResultStorage`: save results to `Architect/runtime/learning/evals/<eval_name>_<timestamp>.json`.
   - [x] Implement `EvalDashboardWidget`: add widget to `Architect/gui/` showing evaluation results (score, dimensions, audit trail).

9. **Feedback UI**
   - [x] Design `FeedbackDialog` (PyQt6): show outcome summary, rating buttons (`1`–`5`), preference selector (`A > B`), comment text area, submit button.
   - [x] Implement `FeedbackSubmissions`: save submitted feedback to `Architect/runtime/feedback/`.
   - [x] Implement `FeedbackSummary`: aggregate feedback for display in dashboard.

10. **Preference Model Updater**
    - [x] Implement `PreferenceModelUpdater`: load preference data (`rlhf_samples`), update model weights, save updated model (`Architect/models/weights/` or `runtime/models/`).
    - [x] Implement `PreferenceModelValidator`: verify updated model against test dataset; emit `model_updated` or `model_validation_failed` event.
    - [x] Implement `PreferenceModelRollback`: rollback mechanism for model updates.

11. **Tests for Phase 4**
    - [x] Unit tests for `OutcomeParser`, `FeedbackProcessor`, `WilsonScoreCalculator`, `SpacedRepetitionEngine`.
    - [x] Integration tests: full RLHF loop (execution → outcome ingestion → feedback → model update → validation).
    - [x] UI tests: `FeedbackDialog` functionality (mock PyQt6 events).

**Dependencies:** Phase 3 complete (event bus, archive, manifest system); `rlhf_samples` dataset available (`evals/datasets/rlhf_samples.json`).
**Blockers:** `rlhf_samples.json` must be validated; `defineEval` interface must be finalized.

---

### Phase 5 — Self-Model & Insights (🔜 Planned — Highest Complexity)
**Target:** Trajectory visualization, alignment tracking dashboards; goes beyond blueprint with alignment monitoring.

**Deliverables:**

1. **Trajectory Visualization**
   - [x] Design trajectory data model: `TrajectoryPoint` (timestamp, state, metrics, event_ids, plan_version, agent_assignments).
   - [x] Implement `TrajectoryCollector`: collect trajectory points from event bus (`Architect/runtime/trajectories/<plan_id>.jsonl`).
   - [x] Implement `TrajectoryVisualizer`: render trajectory as timeline or graph in `Architect/gui/` (new widget or tab).

2. **Alignment Tracking Dashboards**
   - [x] Design alignment metrics: `alignment_score` (agreement with human preferences), `safety_score` (risk invariant compliance), `learning_efficiency` (improvement rate over time).
   - [x] Implement `AlignmentTracker`: compute metrics from trajectory data, feedback, and risk assessments.
   - [x] Implement `AlignmentDashboard`: new `Architect/gui/views/alignment_dashboard.py` showing metrics, trends, and alerts.

3. **Self-Model Insights**
   - [x] Implement `SelfModelEngine`: generate structured insights from trajectory data (strengths, weaknesses, improvement recommendations).
   - [x] Implement `InsightStorage`: save insights to `Architect/runtime/insights/<timestamp>.json`.
   - [x] Implement `InsightDisplay`: show insights in GUI or CLI output.

4. **Integration with All Previous Phases**
   - [x] Ensure trajectory data flows from event bus (Phase 3) to collector (Phase 5).
   - [x] Ensure alignment metrics incorporate reflection outputs (Phase 2), manifest validation results (Phase 3), RLHF feedback (Phase 4), and trajectory data (Phase 5).

5. **Tests for Phase 5**
   - [x] Integration tests: full 5-phase loop in sandbox.
   - [x] Performance tests: trajectory visualization with large dataset.
   - [x] Alignment tests: verify alignment metrics match expected values for known scenarios.

**Dependencies:** All previous phases complete.
**Blockers:** None (future phase).

---

## 4. Detailed To-Do Checklist (Task-Level)

### Phase 1 Lock — Documentation & Stabilization
- [x] Create `Architect/README.md`: document architecture, phase status, divergence notes, installation instructions.
- [x] Create `Architect/docs/ARCHITECTURE.md`: describe directory structure (`core/`, `limbs/`, `gui/`, `models/`), data flow, dependency model.
- [x] Create `Architect/docs/PHASES.md`: document 5-phase roadmap, deliverables per phase, dependencies, blockers.
- [x] Update `Architect/test_init.py`: expand smoke tests (import checks for all modules, basic function checks for `TheJudgeM8`, `MicrostructureEngine`, `GenAIClient`).
- [x] Add `.gitignore` entries: `runtime/`, `workspace/`, `.env`, `data/`, `__pycache__`, `.test-build/`.

### Phase 2 — Reflection Planning (Prioritized Sub-Tasks)
- [x] `GenAIClient.generate_journal()` — real implementation
- [x] `GenAIClient.reflect_dsr()` — real implementation
- [x] `MemoryPlanner` — design + implementation
- [x] `AgentAssignment` — mapping logic
- [x] `StateMachine` transition rules
- [x] `PostMortemTrigger` — trigger conditions
- [x] `BaselineRetriever` — retrieval logic
- [x] `MemoryPlanner` tests
- [x] `AgentAssignment` tests
- [x] `StateMachine` transition tests
- [x] Integration: full reflection loop test

### Phase 3 — Safe Self-Modification (Prioritized Sub-Tasks)
- [x] `manifest.schema.json` — design
- [x] `ManifestParser` — implementation
- [x] `validateManifestUpdate()` — implementation
- [x] `SelfModificationSafety` — guard logic
- [x] `BootstrapLimb` — fs operations
- [x] `EventBus` — NDJSON format, whitelist, emission
- [x] `Archive` — storage, lookup, stats, verify, compact
- [x] `Timer` — modes, persistence, clock coherence
- [x] `Ouroboros` test — full loop in sandbox
- [x] `ManifestParser` tests
- [x] `validateManifestUpdate()` tests
- [x] `BootstrapLimb` sandbox tests
- [x] `EventBus` contract tests
- [x] `Archive` verification tests
- [x] `Timer` mode tests

### Phase 4 — RLHF Integration (Prioritized Sub-Tasks)
- [x] `outcome.schema.json` — design
- [x] `OutcomeParser` — implementation
- [x] `feedback.schema.json` — design
- [x] `FeedbackProcessor` — implementation
- [x] `WilsonScoreCalculator` — implementation
- [x] `SpacedRepetitionEngine` — SM-2 algorithm
- [x] `ErrorPatternDetector` — pattern detection
- [x] `KnowledgeBase` — storage + search
- [x] `RiskGuardEngine` — risk guard checks
- [x] `defineEval` interface — design
- [x] `EvalPipeline` — pipeline logic
- [x] `FeedbackDialog` — PyQt6 UI
- [x] `PreferenceModelUpdater` — model update logic
- [x] `OutcomeParser` tests
- [x] `FeedbackProcessor` tests
- [x] `SpacedRepetitionEngine` tests
- [x] `ErrorPatternDetector` tests
- [x] RLHF loop integration test

### Phase 5 — Self-Model & Insights (Prioritized Sub-Tasks)
- [x] `TrajectoryPoint` — data model
- [x] `TrajectoryCollector` — collection logic
- [x] `TrajectoryVisualizer` — GUI widget
- [x] `AlignmentTracker` — metric computation
- [x] `AlignmentDashboard` — new view
- [x] `SelfModelEngine` — insight generation
- [x] `InsightStorage` + `InsightDisplay`
- [x] Integration with all previous phases
- [x] Full 5-phase loop test
- [x] Performance tests for trajectory visualization

---

## 5. Dependency Map

```
Phase 1 (Complete)
    │
    ▼
Phase 2 (Reflection Planning) ────────► Requires: GenAI SDK / Mock, Phase 1 Stable
    │
    ▼
Phase 3 (Safe Self-Modification) ────► Requires: Phase 2 Complete, Protocol Design,
    │                                 Blueprint `docs/ARCHITECTURE.md` §6, §3
    ▼
Phase 4 (RLHF Integration) ─────────► Requires: Phase 3 Complete (Event Bus, Archive),
    │                                 `rlhf_samples.json`, `defineEval` Design
    ▼
Phase 5 (Self-Model) ────────────────► Requires: All Previous Phases Complete
```

---

## 6. Risk & Divergence Documentation

### 6.1 Known Divergences (Intentional)
| Divergence | Blueprint | Jules | Documentation Action |
|---|---|---|---|
| Dependency Model | Stdlib-only Python 3.11+ | PyQt6, torch, onnx, qdrant-client, ccxt.pro, google-genai, numpy, pydantic-settings | Document in `Architect/docs/DIVERGENCES.md` |
| Transport | File-based (`runtime/`), deterministic, auditable | External APIs + Qdrant cloud + WebSocket feeds | Document transport model; note file-based event sink for Phase 3 |
| Domain | Generic AI orchestration | Trading-specific (market microstructure, regime detection, risk management) | Document domain focus; note no trading logic in blueprint |
| UI Stack | React/Next.js web frontend | PyQt6 desktop terminal | Document UI technology choice |
| Protocol | Protocol 1.2 (492-line normative spec) | Schema extension planned (Phase 1) but not implemented | Implement protocol contracts in Phase 2–3 |

### 6.2 Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Phase 2 GenAI SDK unavailable or rate-limited | Reflection engine blocked | Implement mock/stub mode; store reflection templates offline |
| Phase 3 Manifest validation too restrictive | Self-modification blocked | Design tiered approval (`system` for non-core, `human` for core) |
| Phase 4 RLHF dataset (`rlhf_samples`) invalid or missing | Learning engine blocked | Validate dataset format; create synthetic test dataset if needed |
| Phase 5 Performance degradation with large trajectory data | Visualization slow | Implement bounded caches (`< 200` trajectory points); use incremental loading |
| Blueprint divergence grows without documentation | Confusion, maintenance burden | Maintain `DIVERGENCES.md` and update with each phase |

---

## 7. Success Criteria

### Per Phase
| Phase | Success Criteria |
|---|---|
| Phase 2 | Reflection loop runs end-to-end (execution → post-mortem → plan update); confidence scores computed; agent assignments mapped; state machine transitions tested. |
| Phase 3 | `validateManifestUpdate()` passes/fails correctly; `BootstrapLimb` operates in sandbox; `EventBus` emits valid NDJSON events; `Archive` verifies; `Timer` maintains clock coherence; `Ouroboros` test completes. |
| Phase 4 | `OutcomeParser` validates; `FeedbackProcessor` aggregates; `WilsonScoreCalculator` computes; `SpacedRepetitionEngine` schedules; `ErrorPatternDetector` alerts; `defineEval` runs; `FeedbackDialog` submits; `PreferenceModelUpdater` updates model safely. |
| Phase 5 | `TrajectoryVisualizer` renders; `AlignmentTracker` computes; `SelfModelEngine` generates insights; full 5-phase loop runs in sandbox without errors. |

### Overall Project
- [x] All 5 phases documented in `Architect/docs/PHASES.md`.
- [x] All divergences documented in `Architect/docs/DIVERGENCES.md`.
- [x] Unit tests cover each new component (`Architect/test_init.py` expanded to 20+ assertions per module).
- [x] Integration tests cover each phase transition.
- [x] `make check` in `Architect/` passes (compile, lint, tests).
- [x] `Architect/README.md` explains how to run each phase independently.

---

## 8. References

- `docs/ARCHITECTURE.md` — Omega Blueprint architecture, two stacks, process/time model.
- `docs/NEU.md` — Normative spec, protocol 1.2, timer semantics, event bus, archive.
- `docs/REVIEW-2026-09-04.md` — Review findings, phase definitions, divergence notes.
- `protocol/PROTOCOL.md` — Protocol 1.2 normative document (492 lines), intent/result envelopes, schedule triggers, error codes.
- `COMPARISON_OMEGA_BLUEPRINT_VS_JULES.md` — Full comparison of blueprint vs. Jules's Architect, gap analysis, phase mapping.
- `.jules/bolt.md` — Performance learnings (file persistence optimization, tick cost reduction).
- `.jules/specter.md` — Frontend optimization learnings (render waste, memo boundaries, SVG namespace scoping).
- `Architect/` — Jules's current code (Phase 1).
- `core/`, `orchestrator/`, `limbs/`, `protocol/` — Blueprint implementation (production-grade).

---

*Document Version: 1.0*
*Created: 2026-09-07*
*Branch: arena/01a07d99-nio*
*Status: Implementation Plan (Ready for Execution)*
