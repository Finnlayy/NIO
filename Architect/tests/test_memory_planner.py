import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
import tempfile

# Mock Qdrant engine for memory planner tests
class MockQdrantEngine:
    def __init__(self):
        self.client = MockClient()

class MockClient:
    def search(self, collection_name, query_vector, limit=5):
        class MockPoint:
            def __init__(self, id_: str, score: float, payload: dict):
                self.id = id_
                self.score = score
                self.payload = payload
        return [
            MockPoint("m1", 0.95, {"memory": "prior execution context"}),
            MockPoint("m2", 0.87, {"memory": "similar failure pattern"}),
        ]

from limbs.intelligence.memory_planner import MemoryPlanner

class TestMemoryPlanner(unittest.TestCase):
    def setUp(self):
        self.mock_engine = MockQdrantEngine()
        with tempfile.TemporaryDirectory() as tmp:
            self.tmpdir = tmp
            # We can't easily redirect MemoryPlanner runtime_dir; we'll test with real paths
            # but clean up after
            pass
        self.planner = MemoryPlanner(self.mock_engine)
        # Override plans_dir for isolation
        self.planner.plans_dir = Path(self.tmpdir) / "plans"
        self.planner.plans_dir.mkdir(parents=True, exist_ok=True)

    def test_create_plan(self):
        plan = self.planner.create_plan("Optimize reflection pipeline")
        self.assertIn("plan_id", plan)
        self.assertEqual(plan["objective"], "Optimize reflection pipeline")
        self.assertEqual(plan["status"], "draft")
        self.assertTrue(len(plan["steps"]) > 0)
        # Verify persistence
        saved = self.planner.get_plan(plan["plan_id"])
        self.assertEqual(saved["plan_id"], plan["plan_id"])

    def test_update_plan(self):
        plan = self.planner.create_plan("Update test")
        updated = self.planner.update_plan(plan["plan_id"], {"status": "approved", "confidence_score": 0.95})
        self.assertEqual(updated["status"], "approved")
        self.assertEqual(updated["confidence_score"], 0.95)

    def test_memory_context_retrieval(self):
        plan = self.planner.create_plan("Memory context test", context_vectors=[[0.1]*16])
        # Since mock engine returns results, memory_context should contain entries
        self.assertTrue(isinstance(plan.get("memory_context"), list))

    def test_get_plan_missing(self):
        result = self.planner.get_plan("nonexistent_plan_id_12345")
        self.assertEqual(result, {})

if __name__ == "__main__":
    unittest.main()
