import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.agent_assignment import AgentAssignment, AGENT_REGISTRY

class TestAgentAssignment(unittest.TestCase):
    def setUp(self):
        self.assignment = AgentAssignment()

    def test_registry_has_agents(self):
        self.assertIn("judge_m8_agent", AGENT_REGISTRY)
        self.assertIn("microstructure_agent", AGENT_REGISTRY)
        self.assertIn("gravity_agent", AGENT_REGISTRY)
        self.assertIn("genai_agent", AGENT_REGISTRY)
        self.assertIn("memory_agent", AGENT_REGISTRY)
        self.assertIn("ml_agent", AGENT_REGISTRY)

    def test_map_agent_to_task_with_capabilities(self):
        agent = self.assignment.map_agent_to_task("evaluate risk invariants", ["risk_invariant_check"])
        self.assertEqual(agent, "judge_m8_agent")

    def test_map_agent_to_task_by_description(self):
        agent = self.assignment.map_agent_to_task("calculate orderbook imbalance and footprint map")
        # Should match microstructure_agent based on keywords
        self.assertTrue(agent in ["microstructure_agent", "judge_m8_agent"])

    def test_assign_agents_updates_plan(self):
        plan = {
            "plan_id": "test_assign",
            "steps": [
                {"step_id": "step_01", "action": "evaluate_risk"},
                {"step_id": "step_02", "action": "generate_reflection"},
            ],
        }
        updated = self.assignment.assign_agents(plan)
        self.assertTrue(updated.get("agent_assignments_mapped"))
        for step in updated["steps"]:
            self.assertIn("agent", step)
            self.assertNotEqual(step["agent"], "manual_review_agent")

    def test_get_agent_info(self):
        info = self.assignment.get_agent_info("judge_m8_agent")
        self.assertIn("capabilities", info)
        self.assertIn("module", info)
        self.assertIn("description", info)

    def test_get_agent_info_unknown(self):
        info = self.assignment.get_agent_info("unknown_agent")
        self.assertEqual(info["capabilities"], ["unknown"])

if __name__ == "__main__":
    unittest.main()
