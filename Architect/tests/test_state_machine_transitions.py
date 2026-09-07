import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.state_machine import (
    SystemExecutionState,
    TRANSITION_MAP,
    GUARD_CONDITIONS,
    TrancheLifecycleState,
    FeedConnectionState,
    MarketRegimeState,
)

class TestStateMachineTransitions(unittest.TestCase):
    def test_system_states_exist(self):
        states = list(SystemExecutionState)
        self.assertIn(SystemExecutionState.PLANNING, states)
        self.assertIn(SystemExecutionState.COMPLETE, states)

    def test_planning_to_dispatched_guard(self):
        guard = TRANSITION_MAP[SystemExecutionState.PLANNING]["guard"]
        self.assertTrue(guard({"plan_approved": True}))
        self.assertFalse(guard({"plan_approved": False, "plan_rejected": False}))
        self.assertTrue(guard({"plan_rejected": True}))

    def test_dispatched_to_running_guard(self):
        guard = TRANSITION_MAP[SystemExecutionState.DISPATCHED]["guard"]
        self.assertTrue(guard({"execution_started": True}))
        self.assertFalse(guard({"execution_started": False}))

    def test_running_to_reflecting_guard(self):
        guard = TRANSITION_MAP[SystemExecutionState.RUNNING]["guard"]
        self.assertTrue(guard({"execution_complete": True}))
        self.assertTrue(guard({"post_mortem_triggered": True}))
        self.assertTrue(guard({"timeout": True}))
        self.assertTrue(guard({"safety_net_activated": True}))
        self.assertFalse(guard({}))

    def test_reflecting_to_complete_guard(self):
        guard = TRANSITION_MAP[SystemExecutionState.REFLECTING]["guard"]
        self.assertTrue(guard({"reflection_complete": True}))
        self.assertTrue(guard({"plan_revised": True}))
        self.assertFalse(guard({}))

    def test_guard_conditions_independent(self):
        # Plan approved requires confidence >= 0.7
        self.assertTrue(GUARD_CONDITIONS["plan_approved"]({"confidence_score": 0.85}))
        self.assertFalse(GUARD_CONDITIONS["plan_approved"]({"confidence_score": 0.5}))
        # Execution started requires feed_live
        self.assertTrue(GUARD_CONDITIONS["execution_started"]({"feed_live": True}))
        self.assertFalse(GUARD_CONDITIONS["execution_started"]({"feed_live": False}))
        # Post-mortem trigger checks multiple conditions
        self.assertTrue(GUARD_CONDITIONS["post_mortem_triggered"]({"verdict": "rejected"}))
        self.assertTrue(GUARD_CONDITIONS["post_mortem_triggered"]({"errors": ["E_INTERNAL"]}))
        self.assertTrue(GUARD_CONDITIONS["post_mortem_triggered"]({"timeout": True}))
        self.assertTrue(GUARD_CONDITIONS["post_mortem_triggered"]({"safety_net_activated": True}))

    def test_tranche_states_exist(self):
        self.assertIn(TrancheLifecycleState.T1, list(TrancheLifecycleState))
        self.assertIn(TrancheLifecycleState.FREE_ROLL, list(TrancheLifecycleState))

    def test_feed_states_exist(self):
        self.assertIn(FeedConnectionState.CONNECTED_LIVE, list(FeedConnectionState))
        self.assertIn(FeedConnectionState.STALE_CACHE_DEGRADED, list(FeedConnectionState))

if __name__ == "__main__":
    unittest.main()
