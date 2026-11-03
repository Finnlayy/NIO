import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.events import build_event_bus, FileSink

class TestEvents(unittest.TestCase):
    def test_filesink_rotation(self):
        with TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "system.log"
            # create sink with tiny max size (100 bytes)
            sink = FileSink(log_path, max_bytes=100, backup_count=2)

            # Record > 50 bytes, two writes will exceed 100 bytes
            record = {"seq": 1, "timestamp": "2025", "kind": "test", "job_id": "", "trace_id": "", "intent_id": "", "limb": "", "clock_s": 0, "payload": {"data": "0"*60}}

            sink.write(record)
            self.assertTrue(log_path.exists())
            self.assertFalse(log_path.with_name("system.log.1").exists())

            sink.write(record)
            self.assertTrue(log_path.with_name("system.log.1").exists())

            sink.write(record)
            self.assertTrue(log_path.with_name("system.log.2").exists())

    def test_filesink_unwritable_path(self):
        with TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "system.log"
            log_path.touch(mode=0o400) # Read only

            sink = FileSink(log_path)
            record = {"seq": 1, "timestamp": "2025", "kind": "test", "job_id": "", "trace_id": "", "intent_id": "", "limb": "", "clock_s": 0, "payload": {}}

            # This should not raise an exception
            try:
                sink.write(record)
            except Exception as e:
                self.fail(f"write raised an exception {e}")

            self.assertTrue(sink._reported_error)

class TestAgentLogging(unittest.TestCase):
    def test_agent_log_redaction_and_newline_injection(self):
        from limbs.agent_base import AgentLimb, redact
        from core.config import NeuConfig
        import json

        class MockAgentLimb(AgentLimb):
            name = "mock"
            def secrets(self):
                return ["SUPERSECRET"]
            def gather(self, run, ctx):
                return {"cost": 0.5, "artifacts": [1, 2], "raw": "evil\nnewline\x00controlSUPERSECRET"}

        with TemporaryDirectory() as tmpdir:
            config = NeuConfig(Path(tmpdir), runtime_dir=tmpdir, protocol_dir=str(Path('core').resolve().parent / 'protocol'))

            limb = MockAgentLimb(config)

            run = {
                "run_id": "run_123",
                "state": "running",
                "created_at": "2025-01-01T00:00:00Z",
                "started_s": 0.0,
            }

            payload = limb.gather(run, None)
            limb._log_system_run(run, payload)

            log_path = Path(tmpdir) / "system.log"
            self.assertTrue(log_path.exists())

            lines = log_path.read_text().splitlines()
            self.assertEqual(len(lines), 1)

            data = json.loads(lines[0])
            self.assertEqual(data["kind"], "agent.run.summary")
            self.assertEqual(data["payload"]["cost"], 0.5)
            self.assertEqual(data["payload"]["artifacts"], 2)

            # test redaction and newline stripping in payload

            run["error"] = "bad\nerrorSUPERSECRET"
            limb._log_system_run(run, payload)

            lines = log_path.read_text().splitlines()
            data2 = json.loads(lines[1])
            self.assertEqual(data2["payload"]["error"], "baderror[REDACTED]")

if __name__ == "__main__":
    unittest.main()
