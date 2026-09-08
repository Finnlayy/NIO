import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.feedback_processor import FeedbackProcessor
from core.schema_utils import SchemaInvalid

VALID_FEEDBACK = {
    "outcome_id": "job_100",
    "rater_id": "human",
    "rating": 4,
    "preference": {"chosen": "A", "rejected": "B"},
    "comment": "Good execution but latency was high",
    "timestamp": "2026-09-07T12:00:01Z",
}


class TestFeedbackProcessor(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.feedback_dir = Path(self.tmpdir) / "feedback"
        self.aggregates_dir = Path(self.tmpdir) / "aggregates"
        from core.events import EventBus
        self.bus = EventBus(system_log_path=str(Path(self.tmpdir) / "system.log"))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.processor = FeedbackProcessor(
            feedback_dir=str(self.feedback_dir),
            aggregates_dir=str(self.aggregates_dir),
            event_bus=self.bus,
        )

    def test_validate_ok(self):
        validated = self.processor.validate_feedback(dict(VALID_FEEDBACK))
        self.assertEqual(validated["rating"], 4)

    def test_rating_bounds_enforced(self):
        for bad_rating in (0, 6, "five", 3.5):
            bad = dict(VALID_FEEDBACK, rating=bad_rating)
            with self.assertRaises(SchemaInvalid):
                self.processor.validate_feedback(bad)

    def test_preference_shape_enforced(self):
        bad = dict(VALID_FEEDBACK, preference={"chosen": "A"})  # missing rejected
        with self.assertRaises(SchemaInvalid):
            self.processor.validate_feedback(bad)
        null_pref = dict(VALID_FEEDBACK, preference=None)
        self.processor.validate_feedback(null_pref)  # allowed

    def test_missing_required_raises(self):
        bad = dict(VALID_FEEDBACK)
        del bad["rater_id"]
        with self.assertRaises(SchemaInvalid):
            self.processor.validate_feedback(bad)

    def test_load_feedback_roundtrip(self):
        path = self.feedback_dir / "fb1.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(VALID_FEEDBACK, f)
        loaded = self.processor.load_feedback(path)
        self.assertEqual(loaded["outcome_id"], "job_100")

    def test_load_feedback_dir_skips_invalid(self):
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        with open(self.feedback_dir / "ok.json", "w", encoding="utf-8") as f:
            json.dump(VALID_FEEDBACK, f)
        with open(self.feedback_dir / "bad.json", "w", encoding="utf-8") as f:
            json.dump({"rating": 99}, f)
        records = self.processor.load_feedback_dir()
        self.assertEqual(len(records), 1)

    def test_save_feedback_persists_and_emits(self):
        self.processor.save_feedback(dict(VALID_FEEDBACK))
        files = list(self.feedback_dir.glob("*.json"))
        self.assertEqual(len(files), 1)
        log_text = (Path(self.tmpdir) / "system.log").read_text(encoding="utf-8")
        self.assertIn("feedback_submitted", log_text)

    def test_aggregate_ratings_and_preferences(self):
        records = [
            dict(VALID_FEEDBACK),
            dict(VALID_FEEDBACK, rating=2, preference=None, comment="slow and risky"),
            dict(VALID_FEEDBACK, rating=5, preference={"chosen": "B", "rejected": "A"}, comment="great"),
        ]
        aggregate_result = self.processor.aggregate(records)
        self.assertEqual(aggregate_result["count"], 3)
        self.assertAlmostEqual(aggregate_result["average_rating"], (4 + 2 + 5) / 3, places=4)
        self.assertEqual(aggregate_result["rating_histogram"], {"2": 1, "4": 1, "5": 1})
        self.assertAlmostEqual(aggregate_result["preference_ratio"], 1.0)  # both preferences favored `chosen`
        self.assertEqual(aggregate_result["preference_count"], 2)
        self.assertIsInstance(aggregate_result["common_themes"], list)

    def test_aggregate_for_outcome_filters(self):
        records = [
            dict(VALID_FEEDBACK, outcome_id="job_A"),
            dict(VALID_FEEDBACK, outcome_id="job_B", rating=1),
        ]
        aggregate_result = self.processor.aggregate_for_outcome("job_A", records)
        self.assertEqual(aggregate_result["count"], 1)
        self.assertEqual(aggregate_result["outcome_id"], "job_A")

    def test_save_aggregate(self):
        aggregate_result = {"count": 1, "average_rating": 4.0}
        path = self.processor.save_aggregate("job_100", aggregate_result)
        self.assertTrue(Path(path).exists())
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["outcome_id"], "job_100")


if __name__ == "__main__":
    unittest.main()
