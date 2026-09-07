"""Integration test: full Phase 4 RLHF loop.

    execution -> outcome ingestion -> feedback -> skill/learning updates
              -> eval pipeline -> preference model update -> validation

Runs end-to-end in a sandboxed tempdir with stubbed AI supply (no network).
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.events import EventBus
from core.outcome_parser import OutcomeIngestion, OutcomeParser
from core.feedback_processor import FeedbackProcessor
from core.learning.skill_profiles import SkillProfileUpdater, WilsonScoreCalculator
from core.learning.spaced_repetition import SpacedRepetitionEngine
from core.learning.error_patterns import ErrorPatternDetector, ErrorPatternStorage
from core.learning.knowledge_base import KnowledgeBase, KnowledgeEntryParser
from core.learning.preference_model_updater import PreferenceModelUpdater
from core.evaluation.define_eval import define_eval, EvalPipeline
from core.evaluation.evaluators import correctness_evaluator

REPO_ROOT = Path(__file__).resolve().parents[2]
RLHF_DATASET = str(REPO_ROOT / "evals" / "datasets" / "rlhf_samples.json")


class MockConfig:
    GEMINI_API_KEY = ""
    GEMINI_MODEL_FAST = "gemini-2.5-flash"
    GEMINI_MODEL_DEEP = "gemini-2.5-pro"
    LM_STUDIO_ENABLED = False
    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
    LM_STUDIO_MODEL = "local-model"
    LM_STUDIO_API_KEY = "not-needed"
    LM_STUDIO_TIMEOUT = 30.0


class TestRLHFLoopIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.system_log = self.tmpdir / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}

        self.results_dir = self.tmpdir / "results"
        self.results_dir.mkdir()

        self.ingestion = OutcomeIngestion(event_bus=self.bus,
                                          outcomes_dir=str(self.tmpdir / "outcomes"))
        self.feedback = FeedbackProcessor(
            feedback_dir=str(self.tmpdir / "feedback"),
            aggregates_dir=str(self.tmpdir / "aggregates"),
            event_bus=self.bus,
        )
        self.skills = SkillProfileUpdater(skills_dir=str(self.tmpdir / "skills"), event_bus=self.bus)
        self.repetition = SpacedRepetitionEngine(reviews_dir=str(self.tmpdir / "reviews"), event_bus=self.bus)
        self.patterns = ErrorPatternDetector(
            event_bus=self.bus,
            storage=ErrorPatternStorage(patterns_dir=str(self.tmpdir / "patterns")),
        )
        self.kb = KnowledgeBase(kb_dir=str(self.tmpdir / "knowledge"))
        self.model_updater = PreferenceModelUpdater(models_dir=str(self.tmpdir / "models"), event_bus=self.bus)
        self.pipeline = EvalPipeline(evals_dir=str(self.tmpdir / "evals"))

    def _write_result_file(self, job_id, verdict, errors, metrics):
        path = self.results_dir / f"{job_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "job_id": job_id,
                "intent_id": f"intent_{job_id}",
                "limb": "microstructure_agent",
                "verdict": verdict,
                "errors": errors,
                "metrics": metrics,
                "elapsed_s": 4.2,
                "clock_s": 9.0,
                "timestamp": "2026-09-07T12:00:00Z",
            }, f)
        return path

    def test_full_rlhf_loop(self):
        # 1. Execution produces result files.
        good = self._write_result_file("job_g1", "accept", [], {"success_rate": 1.0})
        bad = self._write_result_file("job_b1", "reject",
                                      ["E_SAFETY_NET: feed stale", "E_SAFETY_NET: feed stale"],
                                      {"success_rate": 0.2, "error_rate": 0.8})

        # 2. Outcome ingestion validates + persists + emits events.
        outcome_good = self.ingestion.ingest_file(good)
        outcome_bad = self.ingestion.ingest_file(bad)
        self.assertEqual(outcome_good["verdict"], "accept")
        self.assertTrue((self.tmpdir / "outcomes" / "job_g1.json").exists())

        # 3. Human feedback over the outcomes.
        feedback_records = [
            {"outcome_id": "job_g1", "rater_id": "human", "rating": 5,
             "preference": {"chosen": "A", "rejected": "B"},
             "comment": "clean execution, tight latency", "timestamp": "2026-09-07T12:01:00Z"},
            {"outcome_id": "job_b1", "rater_id": "human", "rating": 1,
             "preference": {"chosen": "B", "rejected": "A"},
             "comment": "stale feed again, risk guard ignored", "timestamp": "2026-09-07T12:02:00Z"},
        ]
        for record in feedback_records:
            self.feedback.save_feedback(record)
        aggregate_good = self.feedback.aggregate_for_outcome("job_g1", feedback_records)
        aggregate_bad = self.feedback.aggregate_for_outcome("job_b1", feedback_records)
        self.assertEqual(aggregate_good["average_rating"], 5.0)
        self.assertEqual(aggregate_bad["average_rating"], 1.0)
        self.feedback.save_aggregate("job_g1", aggregate_good)
        self.feedback.save_aggregate("job_b1", aggregate_bad)

        # 4. Skill profiles updated from outcomes.
        skill_good = self.skills.record_outcome("skill_micro", True, name="Microstructure")
        skill_bad = self.skills.record_outcome("skill_micro", False)
        self.assertEqual(skill_bad.total_attempts, 2)
        self.assertAlmostEqual(skill_bad.wilson_score,
                               WilsonScoreCalculator.compute(1, 2), places=6)

        # 5. Error pattern detection from the failed outcome.
        patterns = self.patterns.detect_and_store(outcome_bad["errors"])
        self.assertEqual(patterns[0].error_type, "E_SAFETY_NET")
        self.assertEqual(patterns[0].frequency, 2)

        # 6. Reflection output -> knowledge base.
        reflection = {
            "structured_reflection": {
                "diagnosis": "Feed went stale mid-execution",
                "summary": "Safety net fired after stale ticks",
                "recommendation": "Watchdog the tick loop and de-risk on stall",
                "confidence": 0.75,
                "risk_flags": ["stale_feed"],
            }
        }
        for entry in KnowledgeEntryParser.extract_from_reflection(reflection):
            self.kb.save(entry)
        hits = self.kb.search(query_tags=["dsr"])
        self.assertEqual(len(hits), 1)

        # 7. Spaced repetition schedules a review of the new knowledge.
        review = self.repetition.review(hits[0]["entry"]["entry_id"], quality=4)
        self.assertEqual(review["repetitions"], 1)
        self.assertGreater(review["interval_days"], 1.0)

        # 8. defineEval pipeline over the real historical rlhf samples.
        eval_config = define_eval("rlhf_correctness", {"correctness": 1.0}, RLHF_DATASET,
                                  correctness_evaluator, threshold=30.0)
        eval_result = self.pipeline.run(eval_config, rlhf_context=feedback_records)
        self.assertEqual(eval_result["dataset_size"], 4)
        self.assertTrue(eval_result["passed"])
        saved_eval = self.pipeline.save_result(eval_result)
        self.assertTrue(Path(saved_eval).exists())

        # 9. Preference model update + validation.
        update_result = self.model_updater.update(RLHF_DATASET)
        self.assertEqual(update_result["trained_samples"], 4)
        validation = self.model_updater.validate(update_result["model_path"], RLHF_DATASET)
        self.assertTrue(validation["passed"])

        # 10. All emitted events were whitelisted (emit returns True; nothing rejected).
        log_lines = [json.loads(line) for line in
                     self.system_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        kinds = {e["event_kind"] for e in log_lines}
        self.assertIn("execution_complete", kinds)
        self.assertIn("feedback_submitted", kinds)
        self.assertIn("model_updated", kinds)

        # 11. Rollback safety: a retrain can be rolled back.
        self.model_updater.update(RLHF_DATASET)
        rollback = self.model_updater.rollback()
        self.assertTrue(rollback["rolled_back"])

    def test_invalid_outcome_rejected_from_loop(self):
        bad_file = self.results_dir / "broken.json"
        with open(bad_file, "w", encoding="utf-8") as f:
            json.dump({"job_id": "broken", "verdict": "nonsense"}, f)
        from core.schema_utils import SchemaInvalid
        with self.assertRaises(SchemaInvalid):
            self.ingestion.ingest_file(bad_file)


if __name__ == "__main__":
    unittest.main()
