import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import time
from pathlib import Path
from core.timer import Timer

class TestTimer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.timer_dir = Path(self.tmpdir) / "runtime"
        self.timer_dir.mkdir(parents=True, exist_ok=True)

    def test_deadline_mode(self):
        timer = Timer(mode="deadline", deadline_s=10, soft_deadline_s=5, safety_net_s=30, job_id="timer_001")
        # Before timeout
        status = timer.tick(current_time=timer.t0 + 2)
        self.assertFalse(status["timeout"])
        self.assertTrue(status["remaining_ms"] > 0)
        # After timeout
        status = timer.tick(current_time=timer.t0 + 15)
        self.assertTrue(status["timeout"])
        self.assertTrue(status["remaining_ms"] < 0)

    def test_unlimited_mode(self):
        timer = Timer(mode="unlimited", t0=time.time() - 5, job_id="timer_002")
        status = timer.tick()
        self.assertIsNone(status["remaining_ms"])
        self.assertGreater(status["elapsed_s"], 4)

    def test_safety_net_activation(self):
        timer = Timer(mode="deadline", deadline_s=100, safety_net_s=2, job_id="timer_003")
        status = timer.tick(current_time=timer.t0 + 5)
        self.assertTrue(status["safety_net_triggered"])
        # In deadline mode, remaining time should be computed even if safety net triggered
        self.assertIsNotNone(status.get("remaining_ms"))

    def test_persist_and_load(self):
        timer = Timer(mode="deadline", deadline_s=60, t0=time.time(), job_id="timer_persist")
        timer.runtime_dir = Path(self.tmpdir)
        timer.runtime_dir.mkdir(parents=True, exist_ok=True)
        timer.save()
        # Load into new instance
        timer2 = Timer(mode="deadline", job_id="timer_persist")
        timer2.runtime_dir = timer.runtime_dir
        loaded = timer2.load("timer_persist")
        self.assertTrue(loaded)
        self.assertEqual(timer2.mode, "deadline")
        self.assertIsNotNone(timer2.t0)

if __name__ == "__main__":
    unittest.main()
