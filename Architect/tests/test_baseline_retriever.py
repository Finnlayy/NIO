import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.baseline_retriever import BaselineRetriever

class TestBaselineRetriever(unittest.TestCase):
    def setUp(self):
        self.retriever = BaselineRetriever()
        with tempfile.TemporaryDirectory() as tmp:
            self.tmpdir = tmp
            self.retriever.baselines_dir = Path(tmp) / "baselines"
            self.retriever.baselines_dir.mkdir(parents=True, exist_ok=True)

    def test_save_and_load_baseline(self):
        plan = {
            "plan_id": "plan_001",
            "objective": "Test baseline",
            "steps": [{"step_id": "s1", "action": "test"}],
            "confidence_score": 0.78,
        }
        self.retriever.save_baseline(plan)
        loaded = self.retriever.load_baseline("plan_001")
        self.assertEqual(loaded["plan_id"], "plan_001")
        self.assertEqual(loaded["objective"], "Test baseline")
        self.assertEqual(loaded["confidence_score"], 0.78)

    def test_load_missing_baseline(self):
        result = self.retriever.load_baseline("nonexistent_plan_999")
        self.assertEqual(result, {})

    def test_compare_plans(self):
        baseline = {
            "plan_id": "plan_001",
            "steps": [
                {"step_id": "s1", "action": "test", "confidence": 0.7},
                {"step_id": "s2", "action": "run", "confidence": 0.8},
            ],
            "confidence_score": 0.75,
        }
        current = {
            "plan_id": "plan_001",
            "steps": [
                {"step_id": "s1", "action": "test", "confidence": 0.85},
                {"step_id": "s3", "action": "new_step", "confidence": 0.6},
            ],
            "confidence_score": 0.72,
        }
        delta = self.retriever.compare(current, baseline)
        # Added step: s3
        self.assertIn("s3", delta["added_steps"])
        # Removed step: s2
        self.assertIn("s2", delta["removed_steps"])
        # Confidence delta
        self.assertAlmostEqual(delta["confidence_delta"], -0.03, places=2)

    def test_compare_no_changes(self):
        plan = {
            "plan_id": "plan_same",
            "steps": [{"step_id": "s1", "action": "same", "confidence": 0.5}],
            "confidence_score": 0.5,
        }
        delta = self.retriever.compare(plan, plan)
        self.assertEqual(delta["added_steps"], [])
        self.assertEqual(delta["removed_steps"], [])
        self.assertEqual(delta["confidence_delta"], 0.0)

if __name__ == "__main__":
    unittest.main()
