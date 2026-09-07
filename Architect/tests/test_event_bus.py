import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path
from core.events import EventBus, VALID_EVENT_KINDS

class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.system_log_path = Path(self.tmpdir) / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log_path))
        self.bus.event_sinks = {"stderr": False, "file": True}  # Only file for test isolation

    def test_valid_event_emission(self):
        event = self.bus.build_event(
            event_kind="execution_started",
            job_id="job_001",
            intent_id="intent_001",
            message="Execution started successfully.",
        )
        result = self.bus.emit(event)
        self.assertTrue(result)
        # Verify file exists
        self.assertTrue(self.system_log_path.exists())

    def test_invalid_event_rejected(self):
        event = self.bus.build_event(
            event_kind="invalid_event_kind_not_in_whitelist",
            job_id="job_bad",
        )
        result = self.bus.emit(event)
        self.assertFalse(result)

    def test_event_contains_required_fields(self):
        event = self.bus.build_event(
            event_kind="post_mortem_complete",
            job_id="job_002",
            limb="judge_m8_agent",
            clock_s=42.5,
        )
        self.assertIn("event_id", event)
        self.assertIn("timestamp", event)
        self.assertIn("clock_s", event)
        self.assertEqual(event["clock_s"], 42.5)

    def test_whitelist_has_expected_events(self):
        expected_events = [
            "execution_started",
            "execution_complete",
            "post_mortem_started",
            "post_mortem_complete",
            "self_modification_complete",
            "self_modification_failed",
        ]
        for evt in expected_events:
            self.assertIn(evt, VALID_EVENT_KINDS)

if __name__ == "__main__":
    unittest.main()
