# Jules OMEGA Architect — Detailed To-Do List (Granular Tasks)

> **Branch:** `arena/01a07d99-nio`  
> **Repo:** `Finnlayy/NIO`  
> **Target:** Complete `Architect/` against Omega Blueprint (`docs/ARCHITECTURE.md`, `docs/NEU.md`, `protocol/PROTOCOL.md`)  
> **Format:** Each item is a verifiable action with file path, task description, acceptance criteria, and estimated phase.

---

## Legend
- `[P1]` = Phase 1 Lock (stabilization / documentation)
- `[P2]` = Phase 2 Reflection Planning
- `[P3]` = Phase 3 Safe Self-Modification
- `[P4]` = Phase 4 RLHF Integration
- `[P5]` = Phase 5 Self-Model & Insights
- `✅` = Complete  
- `⏳` = In Progress  
- `❌` = Not Started  

---

## Phase 1 Lock — Stabilization (Priority: Before Phase 2 Starts)

### Documentation
- [ ] `[P1]` `Architect/README.md` — Create. Must include: directory map (`core/`, `limbs/`, `gui/`, `models/`), installation (`pip install -r requirements.txt`), phase status table, divergence notes, how to run (`python -m gui.app` or `make run`), how to test (`python test_init.py`).
- [ ] `[P1]` `Architect/docs/ARCHITECTURE.md` — Create. Describe: dependency model (PyQt6, torch, onnx, qdrant, ccxt.pro, google-genai, numpy, pydantic-settings), transport model (external APIs + WebSocket feeds vs. blueprint file transport), data flow (`daemon → GUI`, `limb → workspace`), directory contract.
- [ ] `[P1]` `Architect/docs/PHASES.md` — Create. 5-phase table: phase number, status, deliverables, dependencies, blockers, estimated timeline.
- [ ] `[P1]` `Architect/docs/DIVERGENCES.md` — Create. Document every intentional divergence from blueprint: dependency model (external services vs. stdlib-only), transport (APIs vs. file-based), domain (trading vs. generic orchestration), UI (PyQt6 vs. React/Next.js), protocol (planned vs. 492-line spec).

### Testing & Quality
- [ ] `[P1]` `Architect/test_init.py` — Expand from 1 smoke assertion to 20+. Must cover: import of `core.config`, `core.state_machine`, `core.daemon_supervisor`, `limbs.math.the_judge_m8`, `limbs.math.ac_gravity_engine`, `limbs.intelligence.microstructure_engine`, `gui.app`. Must include basic function assertions (e.g., `TheJudgeM8.check_invariants(...)` returns `(True, ...)` for valid inputs; returns `(False, ...)` for invalid leverage/slippage/zone/feed).
- [ ] `[P1]` `Architect/Makefile` — Add `test` target (`python test_init.py`) and `lint` target (`ruff check .` or `flake8 .` if available).
- [ ] `[P1]` `.gitignore` — Verify entries: `runtime/`, `workspace/`, `.env`, `data/`, `__pycache__/`, `.test-build/`, `*.pyc`, `*.log`.

---

## Phase 2 — Reflection Planning (Immediate Priority After P1 Lock)

### GenAI Client (Real Implementation)
- [ ] `[P2]` `Architect/limbs/intelligence/genai_client.py` — Line 32 (`generate_journal`): Replace `return "Stub journal entry."` with real Gemini SDK call: `self.client.models.generate_content(model=self.model_deep, contents=...)`. Must handle `api_key` empty (raise or log warning). Must save output to `Architect/runtime/reflections/<timestamp>_journal.json`.
- [ ] `[P2]` `Architect/limbs/intelligence/genai_client.py` — Line 36 (`reflect_dsr`): Replace `return "Stub DSR reflection."` with structured output: JSON or dict with fields (`diagnosis`, `root_cause`, `recommended_action`, `confidence`). Must use `post_mortem_data` input (dict or JSON string). Must handle API errors gracefully (`try/except` around SDK call → return `{"error": "API unavailable", "fallback": "manual_review_required"}`).
- [ ] `[P2]` `Architect/limbs/intelligence/genai_client.py` — Add `__all__`, docstrings, type hints (`context: dict`, `post_mortem_data: dict` → `str` or `dict`).

### Memory-Driven Planning
- [ ] `[P2]` `Architect/limbs/intelligence/memory_planner.py` — Create. Must implement:
  - `MemoryPlanner.__init__(qdrant_engine)` — receive `QdrantMemoryEngine` instance.
  - `MemoryPlanner.create_plan(objective, context_vectors)` — retrieve memory from Qdrant (`qdrant_engine.search(query_vector=...)` or equivalent), generate plan with fields (`plan_id`, `objective`, `steps` (list of dicts: `{step_id, action, agent, confidence}`), `status` (`draft`/`approved`/`rejected`/`executed`), `timestamp`).
  - `MemoryPlanner.update_plan(plan_id, updates)` — modify plan steps, update status.
  - `MemoryPlanner.get_plan(plan_id)` — retrieve plan from storage (`Architect/runtime/plans/<plan_id>.json`).
- [ ] `[P2]` `Architect/core/planning_config.py` — Create (optional): planning thresholds (`min_confidence_for_dispatch`, `max_steps_per_plan`, `agent_capabilities_mapping`).

### Agent Assignment
- [ ] `[P2]` `Architect/core/agent_assignment.py` — Create. Must implement:
  - `AgentAssignment.map_agent_to_task(task_description, agent_capabilities)` — match task to agent based on capability keywords.
  - `AgentAssignment.assign_agents(plan)` — iterate plan steps, assign agents, return updated plan.
  - Agent capabilities registry (`limbs/registry.json` equivalent): `judge_m8_agent` (`the_judge_m8`), `microstructure_agent` (`microstructure_engine`), `gravity_agent` (`ac_gravity_engine`), `genai_agent` (`genai_client`), `memory_agent` (`qdrant_memory_engine`).

### State Machine Transitions
- [ ] `[P2]` `Architect/core/state_machine.py` — Add transition rules. Must implement:
  - `SystemExecutionState` transition map: `PLANNING` → `DISPATCHED` (trigger: `plan_approved`), `DISPATCHED` → `RUNNING` (trigger: `execution_started`), `RUNNING` → `REFLECTING` (trigger: `execution_complete` or `post_mortem_triggered`), `REFLECTING` → `COMPLETE` (trigger: `reflection_complete`), `COMPLETE` → `PLANNING` (optional loop for iterative planning).
  - `TrancheLifecycleState` transition: `T1` → `T2` → `T3` → `FREE_ROLL` (trigger: time-based or event-based; document in `docs/PHASES.md`).
  - `FeedConnectionState` transition: `CONNECTED_LIVE` → `STALE_CACHE_DEGRADED` (trigger: feed timeout `> 15.0` seconds; `StaleCacheDegraded` event).
- [ ] `[P2]` `Architect/core/state_machine.py` — Add guard conditions: `plan_approved` requires `confidence >= min_confidence_for_dispatch` (use `core/config.py` value or default `0.7`); `execution_started` requires `feed_live == True` (`TheJudgeM8` Axiom 1).

### Post-Mortem Triggers
- [ ] `[P2]` `Architect/core/post_mortem_trigger.py` — Create. Must implement:
  - `PostMortemTrigger.check_conditions(execution_result)` — evaluate `execution_result` (dict or result file content) for failure conditions: `verdict` == `rejected`, `errors` non-empty, `timeout` occurred, `safety_net` activated, `risk_invariants` failed.
  - `PostMortemTrigger.trigger(post_mortem_data)` — emit event (`post_mortem_started`), call `GenAIClient.reflect_dsr()`, save output.

### Baseline Retrieval
- [ ] `[P2]` `Architect/core/baseline_retriever.py` — Create. Must implement:
  - `BaselineRetriever.load_baseline(plan_id)` — load `Architect/runtime/baselines/<plan_id>.json`.
  - `BaselineRetriever.compare(current_plan, baseline_plan)` — compute delta: added/removed steps, changed confidence scores, changed agent assignments. Return comparison dict.
- [ ] `[P2]` `Architect/runtime/baselines/` — Create directory (add to `.gitignore`? No — baselines should persist but not be versioned. Add `.gitignore` entry: `runtime/baselines/*.json`? Or keep them tracked? Decision: add `.gitignore` for `runtime/` and document in `README.md`. Baselines are runtime artifacts, not source code.)

### Phase 2 Tests
- [ ] `[P2]` `tests/test_memory_planner.py` — Create. Must cover: `create_plan`, `update_plan`, `get_plan`, Qdrant integration mock.
- [ ] `[P2]` `tests/test_agent_assignment.py` — Create. Must cover: mapping logic, capability registry.
- [ ] `[P2]` `tests/test_state_machine_transitions.py` — Create. Must cover: all valid transitions, guard conditions, invalid transitions blocked.
- [ ] `[P2]` `tests/test_post_mortem_trigger.py` — Create. Must cover: trigger conditions, event emission, `GenAIClient` integration mock.
- [ ] `[P2]` `tests/test_baseline_retriever.py` — Create. Must cover: load, compare, missing baseline handling.

---

## Phase 3 — Safe Self-Modification (Next After P2)

### Manifest System
- [ ] `[P3]` `Architect/core/manifest.py` — Create. Must implement:
  - `Manifest.__init__(manifest_path)` — read JSON/YAML manifest.
  - `Manifest.parse()` — validate structure (required fields: `version`, `changes`, `checksum`, `author`, `timestamp`, `safety_flags`).
  - `Manifest.extract_changes()` — return list of file paths and change descriptions.
  - `Manifest.verify_checksum()` — compute SHA-256 of each changed file, compare with manifest checksum.
- [ ] `[P3]` `Architect/schemas/manifest.schema.json` — Create. JSON Schema (2020-12). Fields: `manifest_version` (string, enum: [`1.0`]), `author` (string), `timestamp` (ISO8601), `changes` (array of objects: `{file_path, change_type, line_numbers, checksum_before, checksum_after}`), `safety_flags` (object: `{core_change, dependency_change, model_update}`), `approval_level` (string: [`system`, `human`]).

### Manifest Validation (`validateManifestUpdate`)
- [ ] `[P3]` `Architect/core/manifest_validation.py` — Create. Must implement:
  - `validate_manifest_update(manifest_path, current_state_path)` — read manifest and current state file (`Architect/runtime/current_state.json` or derived from file hashes). Return `(bool, str)` tuple.
  - Safety checks: `core_change == True` → require `approval_level == "human"`; `dependency_change == True` → verify dependency version not downgraded; `model_update == True` → verify model file exists and checksum matches.
  - Policy checks: `file_path` must not match denied globs (`runtime/*`, `*.log`); `file_path` must match allowed repo globs (`Architect/core/*`, `Architect/limbs/*`, `Architect/gui/*`, `Architect/models/*`).
  - Checksum verification: compute SHA-256 of each changed file; compare with `checksum_after`.

### Self-Modification Safety
- [ ] `[P3]` `Architect/core/self_modification_safety.py` — Create. Must implement:
  - `SelfModificationSafety.create_backup(file_path)` — copy file to `Architect/runtime/backups/<filename>_<timestamp>.bak`. Compute SHA-256 of original and backup. Save hash comparison to `Architect/runtime/backups/<filename>_hash.json`.
  - `SelfModificationSafety.rollback(file_path)` — restore file from backup; verify restored file hash matches backup hash.
  - `SelfModificationSafety.apply_modification(manifest)` — apply changes from manifest (patch files, write new files). Before applying, create backups. After applying, verify file hashes match manifest `checksum_after`. If verification fails, trigger rollback.
  - `SelfModificationSafety.validate_after_apply()` — verify all modified files, all new files, all backups exist and match hashes.

### Bootstrap Limb Equivalent
- [ ] `[P3]` `Architect/limbs/bootstrap_limb.py` — Create. Must implement:
  - `BootstrapLimb.read_file(file_path)` — read file within sandbox (`Architect/workspace/` or allowed repo paths). Return content string or dict (if JSON).
  - `BootstrapLimb.write_file(file_path, content, backup=True)` — write file; if `backup=True`, create `.bak` file with SHA-256 hash verification.
  - `BootstrapLimb.patch(file_path, patch_content, backup=True)` — apply patch; create backup; verify hash.
  - `BootstrapLimb.list_files(directory)` — list files in allowed directory; filter by allowed globs.
  - `BootstrapLimb.mkdir(directory)` — create directory within sandbox.
  - Sandbox enforcement: `resolve_path(file_path)` must check `allowed_repo_globs` and `denied_globs`. If file is outside sandbox (`Architect/workspace/`) and not in allowed repo paths, raise `SandboxViolation` exception.
- [ ] `[P3]` `Architect/core/policy.py` — Create (or extend from blueprint design). Must implement:
  - `Policy.resolve_path(path)` — resolve relative to allowed base (`Architect/`); apply `denied_globs`; apply `allowed_repo_globs`; apply `human_only_globs`.
  - `Policy.check_schedule(schedule)` — check trigger validity; fail fast before execution.
  - `Policy.constitution_guard(action)` — check `human_only_globs` for core changes; require `approved_by="human"`.
  - `Policy.sandbox_root()` — return `Architect/workspace/` path.

### Ouroboros Test Equivalent
- [ ] `[P3]` `tests/test_ouroboros.py` — Create. Must implement:
  - `test_ouroboros_full_loop()` — create isolated sandbox (`Architect/runtime/sandbox/test_ouroboros/`); create `manifest.json` modifying `Architect/gui/theme.py` (add a comment or change a color); run `SelfModificationSafety.apply_modification()`; verify file changed; verify backup exists; verify rollback restores original; verify event emitted (`self_modification_complete`); clean up sandbox.
  - `test_ouroboros_rollback_on_failure()` — modify manifest with incorrect checksum; apply; verify rollback triggered; verify original file restored; verify event emitted (`self_modification_failed`).

### Event Bus (Phase 3 Requirement — Blueprint §6)
- [ ] `[P3]` `Architect/core/events.py` — Create. Must implement:
  - `EventBus.__init__()` — initialize event sinks: `stderr` (NDJSON stream), `file_sink` (`Architect/runtime/system.log`), optional `uds_sink`, optional `shared_memory_ring`.
  - `EventBus.emit(event_dict)` — validate event against `VALID_EVENT_KINDS` whitelist; serialize to NDJSON (`json.dumps(event_dict, separators=(',', ':'))` — compact, no indent, matching `.jules/bolt.md` optimization); emit to all active sinks.
  - `EventBus.build_event(event_kind, job_id, intent_id, trace_id, limb, clock_s, message, **extra)` — create event dict with required fields; add `timestamp` (ISO8601); add `clock_s` (float or int, matching `t_unlimited`).
  - `VALID_EVENT_KINDS` — list of allowed event kinds (see `OMEGA_JULES_IMPLEMENTATION_PLAN.md` §3.3 for list).
- [ ] `[P3]` `Architect/runtime/system.log` — Create directory/file? No — file created by event bus at first emission. Add `.gitignore`: `runtime/system.log`, `runtime/*.log`.
- [ ] `[P3]` `tests/test_event_bus.py` — Create. Must cover: NDJSON format, whitelist validation (invalid kind rejected), `clock_s` coherence (same `t0` referenced), emission to stderr/file, event structure validation.

### Archive / Ledger
- [ ] `[P3]` `Architect/core/archive.py` — Create. Must implement:
  - `Archive.save(job_id, job_data, history_lines)` — save `runtime/archive/<job_id>.json` (pretty-printed for CLI readability? No — blueprint says machine format compact; CLI uses `json.dumps` with indent for human view. For archive: compact format `separators=(',', ':'))` for performance; CLI `archive lookup` pretty-prints). Must include `sha256_digest` of content.
  - `Archive.lookup(job_id)` — load archive file; verify digest; return content.
  - `Archive.stats()` — count archive files, total size, oldest/newest job IDs.
  - `Archive.verify()` — verify all archive file digests; return list of failures.
  - `Archive.compact()` — merge `.history.jsonl` lines into archive file; remove history file; update digest.
- [ ] `[P3]` `tests/test_archive.py` — Create. Must cover: save/lookup, digest verification, stats, verify failures, compact operation.

### Timer System
- [ ] `[P3]` `Architect/core/timer.py` — Create. Must implement:
  - `Timer.__init__(mode, deadline_s=None, soft_deadline_s=None, safety_net_s=None, t0=None)` — initialize timer. `mode` is `deadline` or `unlimited`. `t0` is timestamp (float) of job creation.
  - `Timer.tick()` — advance time; if mode is `deadline`, compute `remaining_ms`; if `remaining_ms <= 0`, trigger timeout (`deadline_s` exceeded); if `soft_deadline_s` exceeded, emit warning event. If `safety_net_s` exceeded, trigger `E_SAFETY_NET` (escalate, kill limb).
  - `Timer.get_state()` — return dict: `mode`, `deadline_s`, `soft_deadline_s`, `safety_net_s`, `t0`, `elapsed_s`, `remaining_ms`, `expires_at` (ISO8601 or null for unlimited).
  - `Timer.save()` — save state to `Architect/runtime/jobs/<job_id>.json`.
  - `Timer.load(job_id)` — load state from file.
- [ ] `[P3]` `tests/test_timer.py` — Create. Must cover: `deadline` mode (remaining time decreases, timeout triggered), `unlimited` mode (`elapsed_s` increases, `remaining_ms` is `null`), `safety_net_s` activation (escalation event emitted), persistence (save/load preserves state), clock coherence (`t0` same across all references).

---

## Phase 4 — RLHF Integration (After P3)

### Outcome Ingestion (Schema)
- [ ] `[P4]` `Architect/schemas/outcome.schema.json` — Create. Fields: `job_id` (string), `intent_id` (string), `limb` (string), `result` (object: `{verdict, errors, metrics}`), `verdict` (string: [`accept`, `reject`, `escalate`, `timeout`]), `errors` (array of strings), `metrics` (object), `elapsed_s` (float), `clock_s` (float), `timestamp` (ISO8601).
- [ ] `[P4]` `Architect/core/outcome_parser.py` — Create. Implement `OutcomeParser.parse(file_path)` — read result file (JSON); validate against `outcome.schema.json`; return `Outcome` object or raise `SchemaInvalid`.

### Feedback Processing
- [ ] `[P4]` `Architect/schemas/feedback.schema.json` — Create. Fields: `outcome_id` (string), `rater_id` (string), `rating` (int, 1–5), `preference` (object: `{chosen: string, rejected: string}` or `null`), `comment` (string), `timestamp` (ISO8601).
- [ ] `[P4]` `Architect/core/feedback_processor.py` — Create. Implement:
  - `FeedbackProcessor.load_feedback(file_path)` — load feedback file; validate against schema.
  - `FeedbackProcessor.aggregate(feedback_list)` — compute average rating, preference ratio, common themes from comments (optional: use `GenAIClient.generate_journal()` for theme extraction).
  - `FeedbackProcessor.save_aggregate(outcome_id, aggregate_result)` — save to `Architect/runtime/feedback/aggregates/<outcome_id>.json`.

### Wilson-Score Skill Profiles
- [ ] `[P4]` `Architect/core/learning/skill_profiles.py` — Create. Implement:
  - `SkillProfile.__init__(skill_id, name)` — initialize with `successes=0`, `total_attempts=0`, `wilson_score=0.0`, `last_evaluated=null`.
  - `SkillProfile.update(success)` — increment `successes` or `total_attempts`; recompute `wilson_score`.
  - `WilsonScoreCalculator.compute(successes, total_attempts, confidence=0.95)` — return Wilson score lower bound (or point estimate, depending on design).
  - `SkillProfile.save()` / `load(skill_id)` — persist to `Architect/runtime/learning/skills/<skill_id>.json`.
- [ ] `[P4]` `tests/test_skill_profiles.py` — Create. Must cover: update logic, Wilson score computation, persistence.

### SM-2 Spaced Repetition
- [ ] `[P4]` `Architect/core/learning/spaced_repetition.py` — Create. Implement:
  - `SpacedRepetitionEngine.__init__()` — initialize SM-2 parameters (`EF_default=2.5`, `interval_default=1`).
  - `SpacedRepetitionEngine.review(item, quality)` — `quality` is 0–5. Compute new `EF` (`EF = EF + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))`); compute new `interval` (`interval = interval * EF` if quality >= 3, else `interval = 1`).
  - `SpacedRepetitionEngine.schedule_review(item)` — return next review timestamp (`current_time + interval_days`).
  - `SpacedRepetitionEngine.save_reviews()` — save review schedule to `Architect/runtime/learning/reviews/<item_id>.json`.
- [ ] `[P4]` `tests/test_spaced_repetition.py` — Create. Must cover: SM-2 algorithm correctness (compare with reference), schedule computation, persistence.

### Error Pattern Detection
- [ ] `[P4]` `Architect/core/learning/error_patterns.py` — Create. Implement:
  - `ErrorPatternDetector.detect(errors)` — group errors by type (`E_SAFETY_NET`, `E_TRIGGER_INVALID`, `E_SCHEMA_INVALID`, `E_INTERNAL`, `E_FORBIDDEN_ZONE`, etc.); return `ErrorPattern` objects (`pattern_id`, `error_type`, `frequency`, `first_seen`, `last_seen`).
  - `ErrorPatternDetector.alert_if_threshold_exceeded(pattern, threshold)` — emit event (`error_pattern_alert`) if `frequency > threshold`.
  - `ErrorPatternStorage.save(pattern)` — save to `Architect/runtime/learning/error_patterns/<pattern_id>.json`.
- [ ] `[P4]` `tests/test_error_patterns.py` — Create. Must cover: detection logic, frequency counting, alert emission.

### Knowledge Base
- [ ] `[P4]` `Architect/core/learning/knowledge_base.py` — Create. Implement:
  - `KnowledgeBase.save(entry)` — save `entry` (dict: `entry_id`, `title`, `content`, `tags`, `source`, `confidence`, `timestamp`) to `Architect/runtime/learning/knowledge/<entry_id>.json`.
  - `KnowledgeBase.search(query_tags, query_content, limit=10)` — search by tag or content substring; return matching entries.
  - `KnowledgeEntryParser.extract_from_reflection(reflection_output)` — parse reflection output (string or JSON) for key insights; extract `title`, `content`, `tags`, `source` (`reflection`); create `KnowledgeBase` entry.
- [ ] `[P4]` `tests/test_knowledge_base.py` — Create. Must cover: save/search, extraction logic.

### Risk Guards (Learning Engine Safety)
- [ ] `[P4]` `Architect/core/learning/risk_guards.py` — Create. Implement:
  - `RiskGuardEngine.check(plan_or_update, current_state)` — evaluate plan or modification against `TheJudgeM8.check_invariants()` and `Policy.check_schedule()`; return `RiskGuardResult` (`passed`, `failed`, `warnings`, `assessment_timestamp`).
  - `RiskGuardStorage.save(guard_result)` — save to `Architect/runtime/learning/risk_guards/<guard_id>.json`.
  - `RiskGuardAlert.emit_if_failed(guard_result)` — emit event (`risk_guard_failed`) if `passed == False`; emit `risk_guard_warning` for warnings.
- [ ] `[P4]` `tests/test_risk_guards.py` — Create. Must cover: guard checks against invariants, storage, alert emission.

### `defineEval` Pipeline
- [ ] `[P4]` `Architect/core/evaluation/define_eval.py` — Create. Implement:
  - `define_eval(eval_name, criteria, dataset_path, evaluator_func, aggregator_func)` — design interface. Must return `EvalConfig` object.
  - `EvalPipeline.run(eval_config)` — load dataset (`evals/datasets/rlhf_samples.json` or other); apply `evaluator_func` to each sample; aggregate results with `aggregator_func`; return `EvalResult` (dict: `eval_name`, `dataset_size`, `results`, `aggregate_score`, `audit_trail`).
  - `EvalPipeline.save_result(eval_result, output_path)` — save to `Architect/runtime/learning/evals/<eval_name>_<timestamp>.json`.
- [ ] `[P4]` `Architect/core/evaluation/evaluators.py` — Create (optional): reference evaluators (`correctness_evaluator`, `safety_evaluator`, `consistency_evaluator`).
- [ ] `[P4]` `tests/test_define_eval.py` — Create. Must cover: `define_eval` interface, `EvalPipeline.run()`, result format, audit trail.

### Feedback UI (PyQt6)
- [ ] `[P4]` `Architect/gui/views/feedback_dialog.py` — Create. Must implement:
  - `FeedbackDialog.__init__(parent, outcome_summary)` — initialize dialog with: label showing outcome (`job_id`, `verdict`, `elapsed_s`, `errors` summary); `QSlider` or `QSpinBox` for rating (`1`–`5`); `QComboBox` for preference (`A > B`, `A == B`, `B > A`, or `null`); `QTextEdit` for comment; `QPushButton` (`submit`, `cancel`).
  - `FeedbackDialog.submit()` — validate inputs (rating required, preference optional); save feedback to `Architect/runtime/feedback/<timestamp>_<outcome_id>.json`; emit event (`feedback_submitted`); close dialog.
  - `FeedbackDialog.get_result()` — return feedback dict (matching `feedback.schema.json`).
- [ ] `[P4]` `tests/test_feedback_dialog.py` — Create (optional, mock PyQt6): test submit logic, input validation, file output format.

### Preference Model Updater
- [ ] `[P4]` `Architect/core/learning/preference_model_updater.py` — Create. Implement:
  - `PreferenceModelUpdater.load_model()` — load current model (`Architect/models/weights/omega_regime_16d.onnx` or updated version from `runtime/models/`).
  - `PreferenceModelUpdater.update(preference_data_path)` — load preference data (`rlhf_samples.json` or aggregated feedback); update weights; save updated model to `Architect/runtime/models/updated_<timestamp>.onnx`.
  - `PreferenceModelUpdater.validate(updated_model_path, test_dataset_path)` — validate updated model against test dataset; return validation score; emit event (`model_updated` or `model_validation_failed`).
  - `PreferenceModelUpdater.rollback()` — rollback to previous model (from `runtime/models/backups/`).
- [ ] `[P4]` `tests/test_preference_model_updater.py` — Create. Must cover: load/update/validate/rollback logic; event emission.

---

## Phase 5 — Self-Model & Insights (Future — After P4)

### Trajectory Visualization
- [ ] `[P5]` `Architect/core/trajectory/trajectory_collector.py` — Create. Must implement:
  - `TrajectoryPoint.__init__()` — fields: `timestamp`, `state` (`SystemExecutionState`), `metrics` (dict), `event_ids` (list of event IDs from event bus), `plan_version`, `agent_assignments`.
  - `TrajectoryCollector.collect()` — read event stream (`Architect/runtime/system.log` or event bus); filter events by `plan_id`; create `TrajectoryPoint` for each event; save trajectory to `Architect/runtime/trajectories/<plan_id>.jsonl` (line-delimited JSON for incremental updates).
  - `TrajectoryCollector.load_trajectory(plan_id)` — load trajectory file; return list of points.
- [ ] `[P5]` `Architect/gui/views/trajectory_visualizer.py` — Create. Must implement:
  - `TrajectoryVisualizer.__init__(parent)` — create widget showing trajectory timeline (horizontal axis: time; vertical axis: state or metric value). Use `matplotlib` or `pyqtgraph` (optional dependency for Phase 5 only; document in `docs/PHASES.md`).
  - `TrajectoryVisualizer.update(trajectory_points)` — render trajectory points; highlight state transitions (`PLANNING` → `RUNNING` → `REFLECTING` → `COMPLETE`).
  - `TrajectoryVisualizer.show_events(event_ids)` — highlight events on timeline.
- [ ] `[P5]` `tests/test_trajectory_collector.py` — Create. Must cover: collection from event stream, trajectory file format, load logic.

### Alignment Tracking Dashboards
- [ ] `[P5]` `Architect/core/alignment/alignment_tracker.py` — Create. Must implement:
  - `AlignmentTracker.compute_alignment_score(trajectory_points, feedback_aggregates, risk_guards)` — compute `alignment_score` (`0`–`1`). Design formula (example): `alignment_score = 0.5 * (feedback_preference_ratio) + 0.3 * (risk_guard_pass_rate) + 0.2 * (learning_efficiency)`. Document formula in `docs/ARCHITECTURE.md` or `docs/PHASES.md`.
  - `AlignmentTracker.compute_safety_score(risk_guards, execution_results)` — compute `safety_score`: ratio of executions with all invariants passed.
  - `AlignmentTracker.compute_learning_efficiency(trajectory_points)` — compute improvement rate: compare `metrics` (e.g., `execution_time`, `error_rate`) over time; compute slope.
- [ ] `[P5]` `Architect/core/alignment/alignment_dashboard.py` — Create. Must implement:
  - `AlignmentDashboard.save_metrics(alignment_result)` — save to `Architect/runtime/alignment/<plan_id>_<timestamp>.json`.
  - `AlignmentDashboard.load_metrics(plan_id)` — load and aggregate metrics over time.
- [ ] `[P5]` `Architect/gui/views/alignment_dashboard.py` — Create. Must implement:
  - `AlignmentDashboardTab.__init__()` — new tab in `GMTMainWindow` (add to `Architect/gui/app.py`). Show: current `alignment_score`, `safety_score`, `learning_efficiency`; trend charts (optional); recent `alignment` results; risk guard status.
  - `AlignmentDashboardTab.refresh()` — load latest metrics; update labels and charts.

### Self-Model Insights
- [ ] `[P5]` `Architect/core/self_model/self_model_engine.py` — Create. Must implement:
  - `SelfModelEngine.generate_insights(trajectory_points, alignment_metrics)` — analyze trajectory and metrics; generate structured insights (`strengths`, `weaknesses`, `recommendations`). Must return list of `Insight` objects (`insight_id`, `category`, `content`, `confidence`, `timestamp`, `related_events`, `related_plans`).
  - `SelfModelEngine.save_insights(insights)` — save to `Architect/runtime/insights/<timestamp>.json`.
- [ ] `[P5]` `Architect/core/self_model/insight_display.py` — Create. Must implement:
  - `InsightDisplay.load_insights()` — load from `runtime/insights/`.
  - `InsightDisplay.format_for_display(insight)` — format for CLI (`python -c ...`) or GUI widget (`QLabel`, `QTextEdit`).

---

## Cross-Phase Integration Tasks (Must Be Done Per Phase)

### Documentation Updates (Every Phase)
- [ ] After each phase: Update `Architect/docs/PHASES.md` — change status (`Complete`/`In Progress`/`Not Started`), add completed deliverables, update blockers, update timeline.
- [ ] After Phase 3: Update `Architect/docs/DIVERGENCES.md` — document event bus transport divergence (external APIs + NDJSON vs. file-based), archive divergence (JSON files vs. NDJSON events), protocol divergence (planned schema extension vs. 492-line spec).
- [ ] After Phase 4: Update `Architect/docs/ARCHITECTURE.md` — describe RLHF integration data flow (`execution → outcome ingestion → feedback → model update → validation`), learning engine components (`skill_profiles`, `spaced_repetition`, `error_patterns`, `knowledge_base`, `risk_guards`, `define_eval`).
- [ ] After Phase 5: Update `Architect/docs/ARCHITECTURE.md` — describe trajectory data flow (`event bus → trajectory collector → visualizer`), alignment tracking metrics, self-model insights.

### CI / Quality Gate Updates (Every Phase)
- [ ] After Phase 2: Add `tests/test_memory_planner.py`, `tests/test_agent_assignment.py`, `tests/test_state_machine_transitions.py`, `tests/test_post_mortem_trigger.py`, `tests/test_baseline_retriever.py` to `Architect/Makefile` (`test` target: `python -m unittest discover -s tests -t .`).
- [ ] After Phase 3: Add `tests/test_ouroboros.py`, `tests/test_event_bus.py`, `tests/test_manifest_parser.py`, `tests/test_manifest_validation.py`, `tests/test_archive.py`, `tests/test_timer.py` to `Makefile`.
- [ ] After Phase 4: Add `tests/test_outcome_parser.py`, `tests/test_feedback_processor.py`, `tests/test_skill_profiles.py`, `tests/test_spaced_repetition.py`, `tests/test_error_patterns.py`, `tests/test_knowledge_base.py`, `tests/test_risk_guards.py`, `tests/test_define_eval.py` to `Makefile`.
- [ ] After Phase 5: Add `tests/test_trajectory_collector.py`, `tests/test_alignment_tracker.py`, `tests/test_self_model_engine.py` to `Makefile`.

### Dependency & Environment Updates (Every Phase)
- [ ] After Phase 2: Verify `Architect/requirements.txt` includes any new dependencies (`google-genai` for real GenAI calls; optional mock libraries for tests). If `google-genai` is already listed, confirm version compatibility.
- [ ] After Phase 3: Verify `requirements.txt` includes `hdbscan` (if not already present; `Architect/limbs/ml/hdbscan_engine.py` imports it). If not present, add it.
- [ ] After Phase 4: Verify `requirements.txt` includes `numpy` (already present for `MicrostructureEngine`, `ACGravityEngine`), `pydantic-settings` (already present), `scipy` (optional for SM-2 or statistical calculations; add if needed).
- [ ] After Phase 5: Verify optional dependencies for visualization (`matplotlib` or `pyqtgraph`) documented but not added to `requirements.txt` by default (to keep core dependency model light; document in `docs/PHASES.md`).

---

## Verification Checklist (How to Confirm Completion)

### Phase 1 Lock
- [ ] `ls Architect/docs/` shows `ARCHITECTURE.md`, `PHASES.md`, `DIVERGENCES.md`.
- [ ] `cat Architect/README.md` shows directory map, installation, phase status, divergence notes.
- [ ] `python Architect/test_init.py` exits `0` with 20+ assertions passing (no `AssertionError`).
- [ ] `cat .gitignore` includes `runtime/`, `.env`, `workspace/`, `data/`.

### Phase 2 Completion
- [ ] `python -m unittest discover -s tests -t .` passes all new Phase 2 tests (no `FAIL` or `ERROR`).
- [ ] `python -c "from limbs.intelligence.genai_client import GenAIClient; c = GenAIClient(config=config); print('GenAI OK')"` runs without exception (stub mode acceptable for Phase 2 if SDK unavailable).
- [ ] `Architect/runtime/plans/` exists (directory created by `MemoryPlanner`).
- [ ] `Architect/core/state_machine.py` contains transition rules (search for `transition_map` or similar).
- [ ] `tests/test_memory_planner.py` exists and passes.

### Phase 3 Completion
- [ ] `tests/test_ouroboros.py` passes (`test_ouroboros_full_loop` exits `0`; `test_ouroboros_rollback_on_failure` exits `0`).
- [ ] `tests/test_event_bus.py` passes (`VALID_EVENT_KINDS` enforced; NDJSON format verified).
- [ ] `tests/test_manifest_validation.py` passes (`validate_manifest_update` returns `(True, ...)` for valid manifest; `(False, ...)` for invalid checksum or illegal file change).
- [ ] `tests/test_timer.py` passes (deadline mode timeout triggered; unlimited mode `elapsed_s` increases; `safety_net_s` activation emits event; persistence works).
- [ ] `tests/test_archive.py` passes (archive lookup, stats, verify, compact all work).
- [ ] `Architect/runtime/system.log` exists (created by event bus emission in test or manual run).
- [ ] `Architect/runtime/backups/` exists (created by `SelfModificationSafety` backup logic).

### Phase 4 Completion
- [ ] `tests/test_define_eval.py` passes (`define_eval` interface works; `EvalPipeline.run()` returns valid `EvalResult`).
- [ ] `tests/test_feedback_dialog.py` passes (submit logic works; file saved in correct format).
- [ ] `tests/test_preference_model_updater.py` passes (update, validate, rollback all work; events emitted correctly).
- [ ] `tests/test_spaced_repetition.py` passes (SM-2 intervals computed correctly; review schedule saved).
- [ ] `tests/test_skill_profiles.py` passes (Wilson score computed; persistence works).
- [ ] `tests/test_error_patterns.py` passes (patterns detected; alerts emitted for threshold exceeded).
- [ ] `tests/test_knowledge_base.py` passes (knowledge entries saved; search works; extraction from reflection output works).
- [ ] `tests/test_risk_guards.py` passes (risk assessments match `TheJudgeM8` invariants; events emitted for failures/warnings).

### Phase 5 Completion
- [ ] `tests/test_trajectory_collector.py` passes (trajectory collected from event stream; file format `jsonl`; load logic works).
- [ ] `tests/test_alignment_tracker.py` passes (alignment metrics computed from trajectory + feedback + risk guards; results saved in correct format).
- [ ] `Architect/gui/app.py` updated (new `AlignmentDashboardTab` added to `GMTMainWindow`; `TrajectoryVisualizer` or `AlignmentDashboard` referenced or added).
- [ ] `tests/test_self_model_engine.py` passes (insights generated; saved in correct format; format for display works).

---

*Note: This checklist is designed to be used with a task tracker (e.g., GitHub Issues, Notion, or a local markdown file). Each `[P2]`–`[P5]` item can be converted to an individual issue or PR branch (`feat/phase2-memory-planner`, `feat/phase3-event-bus`, etc.).*