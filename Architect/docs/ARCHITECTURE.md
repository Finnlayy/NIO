# OMEGA Architect — Architecture (Jules Stack)

> Companion to the blueprint `docs/ARCHITECTURE.md`. This document describes the
> **Jules stack** (`Architect/`): a PyQt6 trading terminal with Gemini/LM-Studio
> intelligence, Qdrant memory, and a stdlib-only continuous-learning core.

## 1. Directory map

```
Architect/
├── core/                      # Kernel-side modules (state, safety, learning)
│   ├── config.py              #   pydantic-settings (API keys, risk thresholds)
│   ├── state_machine.py       #   SystemExecutionState + transition rules (Phase 2)
│   ├── agent_assignment.py    #   capability registry + mapping (Phase 2)
│   ├── post_mortem_trigger.py #   failure triggers -> DSR reflection (Phase 2)
│   ├── baseline_retriever.py  #   plan baselines (Phase 2)
│   ├── manifest.py            #   manifest parser (Phase 3)
│   ├── manifest_validation.py #   validate_manifest_update() (Phase 3)
│   ├── policy.py              #   sandbox globs, constitution guard (Phase 3)
│   ├── self_modification_safety.py  # backups, rollback, apply (Phase 3)
│   ├── bootstrap_limb.py → limbs/   # fs ops with backup + hash (Phase 3)
│   ├── events.py              #   NDJSON event bus (Phase 3)
│   ├── archive.py             #   job ledger + SHA-256 digests (Phase 3)
│   ├── timer.py               #   deadline/unlimited + safety net (Phase 3)
│   ├── schema_utils.py        #   mini JSON-Schema validator (Phase 4)
│   ├── outcome_parser.py      #   outcome ingestion pipeline (Phase 4)
│   ├── feedback_processor.py  #   feedback aggregation (Phase 4)
│   ├── learning/              #   continuous-learning engine (Phase 4)
│   │   ├── skill_profiles.py      # Wilson-score proficiency
│   │   ├── spaced_repetition.py   # SM-2 review scheduling
│   │   ├── error_patterns.py      # recurring failure memory
│   │   ├── knowledge_base.py      # notes/corrections store
│   │   ├── risk_guards.py         # pre-execution learning safety
│   │   └── preference_model_updater.py  # RLHF preference model
│   ├── evaluation/            #   defineEval pipeline + evaluators (Phase 4)
│   ├── trajectory/            #   trajectory collection (Phase 5)
│   ├── alignment/             #   alignment metrics + dashboard service (Phase 5)
│   └── self_model/            #   insight generation + display (Phase 5)
├── limbs/                     # Capability modules (agents)
│   ├── intelligence/          #   GenAI client, memory planner, microstructure, Qdrant
│   ├── math/                  #   AC gravity, Judge M8 risk invariants
│   ├── ml/                    #   HDBSCAN clustering
│   └── bootstrap_limb.py      #   sandboxed fs operations (Phase 3)
├── gui/                       # PyQt6 desktop terminal
│   ├── app.py                 #   GMTMainWindow: command bar + tabs + tape
│   ├── views/                 #   chart, feedback dialog, trajectory, alignment (P4/P5)
│   └── widgets/               #   command bar, ticker tape
├── models/                    # ONNX regime export + weights
├── schemas/                   # manifest / outcome / feedback JSON schemas
├── evals/                     # reserved (root evals/ holds rlhf_samples.json)
├── tests/                     # unittest suite (Phases 2–5)
└── runtime/                   # gitignored state: system.log, learning/, models/, ...
```

## 2. Two-stack context

| | Python Kernel "Neu" (`core/`, `orchestrator/`, ... at repo root) | Jules OMEGA Architect (`Architect/`) |
|---|---|---|
| Dependency model | Python 3.11+, stdlib-only | PyQt6, torch/onnx, qdrant-client, google-genai, ccxt.pro |
| Transport | File-based, deterministic | External APIs + WebSocket feeds (divergence, see DIVERGENCES.md) |
| Domain | Generic AI orchestration | Trading terminal (microstructure, risk, regime) |

The Architect **learning core** (`core/learning`, `core/evaluation`, `core/trajectory`,
`core/alignment`, `core/self_model`) is deliberately stdlib-only, mirroring the
blueprint's dependency philosophy even though the surrounding terminal uses
external services.

## 3. Phase 4 data flow — RLHF integration

```
execution result (JSON)
      │
      ▼
core/outcome_parser.OutcomeIngestion        validate vs schemas/outcome.schema.json
      │   emits execution_complete          persist runtime/learning/outcomes/<job_id>.json
      ▼
core/feedback_processor.FeedbackProcessor   human ratings (schemas/feedback.schema.json)
      │   emits feedback_submitted          aggregates -> runtime/feedback/aggregates/
      ▼
core/learning/*                             parallel learning updates
      ├── skill_profiles:    Wilson lower bound per skill  -> runtime/learning/skills/
      ├── spaced_repetition: SM-2 review schedule          -> runtime/learning/reviews/ (review_due)
      ├── error_patterns:    recurring failure memory      -> runtime/learning/error_patterns/ (error_pattern_alert)
      ├── knowledge_base:    insights from DSR reflections -> runtime/learning/knowledge/
      └── risk_guards:       TheJudgeM8 + Policy + memory  -> runtime/learning/risk_guards/ (risk_guard_failed/warning)
      ▼
core/evaluation/define_eval.EvalPipeline    rlhf_samples.json -> aggregate score -> runtime/learning/evals/
      ▼
core/learning/preference_model_updater      train -> validate -> runtime/models/updated_<ts>.json
      emits model_updated | model_validation_failed    rollback via runtime/models/backups/
```

## 4. Phase 5 data flow — trajectory, alignment, self-model

```
core/events.EventBus  (NDJSON -> runtime/system.log)
      │
      ▼
core/trajectory.TrajectoryCollector          filter by plan_id, project onto
      │   emits trajectory_collected         PLANNING→DISPATCHED→RUNNING→REFLECTING→COMPLETE
      ▼                                      runtime/trajectories/<plan_id>.jsonl
      ├──► gui/views/trajectory_visualizer   QPainter timeline + transition markers
      ▼
core/alignment.AlignmentTracker
      │   alignment = 0.5*preference + 0.3*guard_rate + 0.2*efficiency
      ▼
core/alignment.AlignmentDashboard            runtime/alignment/<plan_id>_<ts>.json
      │   emits alignment_updated            (trend aggregation over snapshots)
      ▼
core/self_model.SelfModelEngine              strengths / weaknesses / recommendations
      ▼                                      runtime/insights/<ts>.json
core/self_model.InsightDisplay               CLI + GUI rendering
```

## 5. GUI composition (`gui/app.py`)

`GMTMainWindow` = CommandBar (top) + `QTabWidget` [Chart | Trajectory | Alignment]
+ TickerTape (bottom). The Phase 5 tabs import-guarded: if PyQt6 (or a Phase 5
module) is unavailable the window falls back to the bare Phase 1 layout.
`FeedbackDialog` is modal and opened against an outcome summary; its submit
logic is the headless `FeedbackSubmission` class.

## 6. Testing & CI

- `make test` — 214 stdlib-only tests (PyQt6 widget tests skip when absent).
- `make test-smoke` — GUI boot smoke (requires `make setup`).
- Tests never touch repo state: all runtime paths are injected tempdirs.
