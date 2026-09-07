# OMEGA Architect (Jules Stack)

PyQt6 trading terminal with Gemini / LM-Studio intelligence, Qdrant vector
memory, and a stdlib-only continuous-learning core (RLHF + self-model).

See `docs/ARCHITECTURE.md` (structure + data flows), `docs/PHASES.md`
(roadmap status), `docs/DIVERGENCES.md` (documented divergences).

## Install & run

```bash
cd Architect
./setup_environment.sh        # pip install -r requirements.txt (PyQt6, torch, ...)
./run_terminal.sh             # launch the GMT terminal
```

## Tests

```bash
make test          # 214 stdlib-only tests (PyQt6 widget tests skip when absent)
make test-verbose  # verbose
make test-smoke    # GUI boot smoke (requires the desktop dependencies)
```

## Running each phase independently

| Phase | What it does | Try it |
|---|---|---|
| 1 — Foundation | Terminal shell, engines, ONNX regime model | `python3 test_init.py` (needs PyQt6/pyqtgraph) |
| 2 — Reflection Planning | Plan → agent assignment → state transitions → post-mortem DSR | `python3 -m unittest tests.test_reflection_loop_integration` |
| 3 — Safe Self-Modification | Manifest validation, sandbox fs limb, event bus, archive, timer, Ouroboros | `python3 -m unittest tests.test_ouroboros tests.test_event_bus tests.test_archive tests.test_timer tests.test_manifest_validation` |
| 4 — RLHF Integration | Outcome ingestion → feedback → Wilson skills → SM-2 → error patterns → knowledge → defineEval → preference model | `python3 -m unittest tests.test_rlhf_loop_integration` |
| 5 — Self-Model & Insights | Trajectory collection → alignment metrics → insights | `python3 -m unittest tests.test_full_phase_loop` |

Phase status: **all five phases complete** (see `docs/PHASES.md`).

## Minimal phase-4 example (no external services)

```python
import sys; sys.path.insert(0, "Architect")
from core.outcome_parser import OutcomeIngestion
from core.feedback_processor import FeedbackProcessor
from core.learning.skill_profiles import SkillProfileUpdater

outcome = {
    "job_id": "job_1", "intent_id": "i1", "limb": "judge_m8_agent",
    "verdict": "accept", "errors": [], "metrics": {},
    "elapsed_s": 1.0, "clock_s": 2.0, "timestamp": "2026-09-07T00:00:00Z",
}
OutcomeIngestion().ingest(outcome)
FeedbackProcessor().save_feedback({
    "outcome_id": "job_1", "rater_id": "human", "rating": 5,
    "timestamp": "2026-09-07T00:00:01Z",
})
SkillProfileUpdater().record_outcome("skill_judge", True)
```

## Layout

`core/` kernel-side modules · `limbs/` capability agents · `gui/` PyQt6 terminal ·
`schemas/` JSON schemas · `tests/` unittest suite · `runtime/` gitignored state.
