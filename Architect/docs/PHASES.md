# OMEGA Architect — 5-Phase Roadmap Status

> Last updated: 2026-09-07 (Phase 4 + Phase 5 shipped)
> Source plan: `OMEGA_JULES_IMPLEMENTATION_PLAN.md` · Task list: `OMEGA_JULES_TODO.md`

| Phase | Scope | Status | Test coverage |
|---|---|---|---|
| 1 — Foundation | Config, state enums, GUI shell, engines, ONNX export | ✅ Complete | `test_init.py` smoke |
| 2 — Reflection Planning | Memory-driven planning, confidence, agent assignment, state transitions, post-mortem, baselines | ✅ Complete | 11 test files |
| 3 — Safe Self-Modification | Manifest validation, policy/sandbox, bootstrap limb, event bus, archive, timer, Ouroboros | ✅ Complete | 9 test files |
| 4 — RLHF Integration | Outcome ingestion, feedback processing, Wilson skill profiles, SM-2, error patterns, knowledge base, risk guards, `defineEval`, feedback UI, preference model | ✅ Complete | 11 test files |
| 5 — Self-Model & Insights | Trajectory collector + visualizer, alignment tracker + dashboard, self-model engine, insight display | ✅ Complete | 4 test files (incl. full 5-phase loop) |

Run everything: `cd Architect && make test` (stdlib-only; PyQt6 widget tests skip automatically when PyQt6 is absent).

---

## Phase 4 — RLHF Integration (shipped)

**Data flow:** `execution → outcome ingestion → feedback → model update → validation`

| Deliverable | File | Notes |
|---|---|---|
| Outcome schema | `schemas/outcome.schema.json` | job_id, intent_id, limb, verdict (`accept/reject/escalate/timeout`), errors, metrics, elapsed_s, clock_s, timestamp |
| Outcome parser + ingestion pipeline | `core/outcome_parser.py` | `OutcomeParser.parse()` raises `SchemaInvalid`; `OutcomeIngestion` persists to `runtime/learning/outcomes/` and emits `execution_complete` |
| Feedback schema | `schemas/feedback.schema.json` | outcome_id, rater_id, rating 1–5, preference {chosen, rejected} or null, comment |
| Feedback processor | `core/feedback_processor.py` | `load_feedback`, `aggregate` (avg rating, preference ratio, themes), `save_aggregate` |
| Wilson-score skill profiles | `core/learning/skill_profiles.py` | `WilsonScoreCalculator.compute` = exact TODO/blueprint formula; `SkillProfile` persistence; `SkillProfileUpdater` |
| SM-2 spaced repetition | `core/learning/spaced_repetition.py` | classic EF update (floor 1.3); `interval*EF` on q>=3 else reset; `review_due` events |
| Error pattern detection | `core/learning/error_patterns.py` | taxonomy (`E_SAFETY_NET`, `E_TRIGGER_INVALID`, `E_SCHEMA_INVALID`, `E_INTERNAL`, ...), persistence, `error_pattern_alert` events |
| Knowledge base | `core/learning/knowledge_base.py` | deterministic tag/substring search; `KnowledgeEntryParser.extract_from_reflection` (journal + DSR) |
| Risk guards | `core/learning/risk_guards.py` | `TheJudgeM8` invariants + `Policy.check_schedule` + constitution guard + error memory; `risk_guard_failed` / `risk_guard_warning` events |
| `defineEval` pipeline | `core/evaluation/define_eval.py` | `define_eval(...)` → `EvalConfig`; `EvalPipeline.run/save_result` with audit trail; datasets: list or `{"samples": []}` |
| Reference evaluators | `core/evaluation/evaluators.py` | `correctness_evaluator` (token F1 vs expectedOutcome / feedbackScore), `safety_evaluator`, `consistency_evaluator`, `weighted_aggregator` |
| Feedback UI | `gui/views/feedback_dialog.py` | PyQt6 `FeedbackDialog` (guarded import) over headless `FeedbackSubmission` |
| Preference model updater | `core/learning/preference_model_updater.py` | logistic model over hashed bag-of-words (stdlib; see DIVERGENCES.md); `update`/`validate`/`rollback`; `model_updated` / `model_validation_failed` events |

Loop test: `tests/test_rlhf_loop_integration.py`.

## Phase 5 — Self-Model & Insights (shipped)

**Data flow:** `event bus (system.log) → trajectory collector → visualizer / alignment tracker → self-model engine → insights`

| Deliverable | File | Notes |
|---|---|---|
| Trajectory point + collector | `core/trajectory/trajectory_collector.py` | projects event kinds onto `PLANNING→DISPATCHED→RUNNING→REFLECTING→COMPLETE`; `.jsonl` per plan; idempotent (line-hash dedupe); meta events excluded |
| Trajectory visualizer | `gui/views/trajectory_visualizer.py` | QPainter timeline (no pyqtgraph dependency); headless `TrajectoryModel` (points, transitions, event highlighting) |
| Alignment metrics | `core/alignment/alignment_tracker.py` | formulas below; `compute_alignment_score` / `compute_safety_score` / `compute_learning_efficiency` / `compute_all` |
| Alignment dashboard service | `core/alignment/alignment_dashboard.py` | snapshots `runtime/alignment/<plan_id>_<ts>.json`; time-series aggregation; `alignment_updated` events |
| Alignment dashboard tab | `gui/views/alignment_dashboard.py` | PyQt6 tab wired into `GMTMainWindow`; headless `AlignmentDashboardModel` |
| Self-model engine | `core/self_model/self_model_engine.py` | deterministic strengths / weaknesses / recommendations as `Insight` records |
| Insight display | `core/self_model/insight_display.py` | load + CLI/GUI formatting |
| Full 5-phase loop test | `tests/test_full_phase_loop.py` | plan → execute → post-mortem → manifest → RLHF → trajectory → alignment → insights, all in sandbox |

### Alignment metric formulas

```
alignment_score    = 0.5 * feedback_preference_ratio
                   + 0.3 * risk_guard_pass_rate
                   + 0.2 * learning_efficiency

safety_score       = (# clean risk-guard assessments + clean executions) / total

learning_efficiency = clamp01(0.5 + 5 * slope)   # least-squares slope over the
                                                  # trajectory window (normalized
                                                  # time 0..1); error_* metrics inverted
```

`feedback_preference_ratio` falls back to `average_rating_normalized` (rating/5) when no pairwise preferences exist. No evidence ⇒ 0.0 (never inflated).

### Event kinds added in Phases 4–5
`risk_guard_failed`, `risk_guard_warning` (all other Phase 4/5 kinds were pre-whitelisted in Phase 3: `error_pattern_alert`, `feedback_submitted`, `model_updated`, `model_validation_failed`, `trajectory_collected`, `alignment_updated`, `review_due`).

---

## Optional Phase 5 dependencies

`matplotlib`/`pyqtgraph` are **not** required: `TrajectoryVisualizer` paints with Qt's `QPainter`. Keep the core dependency model light; do not add them to `requirements.txt`.
