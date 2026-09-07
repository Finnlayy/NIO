import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path

# Mock GenAI client for post-mortem tests
class MockGenAIClient:
    def reflect_dsr(self, post_mortem_data):
        return {
            "structured_reflection": {
                "diagnosis": "Mock diagnosis for test",
                "summary": "Mock summary for test execution.",
                "recommendation": "Run manual review.",
                "confidence": 0.8,
                "risk_flags": ["test_flag"],
            },
            "mode": "mock",
            "source": "mock_genai",
        }

from core.post_mortem_trigger import PostMortemTrigger

class TestPostMortemTrigger(unittest.TestCase):
    def setUp(self):
        self.mock_genai = MockGenAIClient()
        self.trigger = PostMortemTrigger(genai_client=self.mock_genai)
        with tempfile.TemporaryDirectory() as tmp:
            self.tmpdir = tmp
            self.trigger.triggers_dir = Path(tmp) / "post_mortems"
            self.trigger.triggers_dir.mkdir(parents=True, exist_ok=True)

    def test_check_conditions_rejected(self):
        result = self.trigger.check_conditions({"verdict": "rejected"})
        self.assertTrue(result)

    def test_check_conditions_errors(self):
        result = self.trigger.check_conditions({"errors": ["E_INTERNAL", "E_SCHEME"]})
        self.assertTrue(result)

    def test_check_conditions_timeout(self):
        result = self.trigger.check_conditions({"timeout": True})
        self.assertTrue(result)

    def test_check_conditions_safety_net(self):
        result = self.trigger.check_conditions({"safety_net_activated": True})
        self.assertTrue(result)

    def test_check_conditions_clean(self):
        result = self.trigger.check_conditions({"verdict": "accept", "errors": []})
        self.assertFalse(result)

    def test_trigger_saves_result(self):
        pm_data = {"job_id": "job_123", "execution_result": {"verdict": "rejected"}}
        result = self.trigger.trigger(pm_data)
        self.assertTrue(result["triggered"])
        self.assertIn("analysis", result)
        self.assertEqual(result["analysis"]["source"], "mock_genai")
        self.assertIn("saved_to", result)
        # Verify file exists
        self.assertTrue(Path(result["saved_to"]).exists())

    def test_trigger_without_genai_client(self):
        trigger_no_genai = PostMortemTrigger(genai_client=None)
        trigger_no_genai.triggers_dir = self.trigger.triggers_dir
        result = trigger_no_genai.trigger({"job_id": "job_no_ai"})
        self.assertTrue(result["triggered"])
        self.assertIn("analysis", result)

if __name__ == "__main__":
    unittest.main()
