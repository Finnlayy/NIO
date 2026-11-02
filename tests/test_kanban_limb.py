import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from core.config import NeuConfig
from core.policy import Policy
from core.protocol import Intent, Operations
from orchestrator.runner import Orchestrator
from orchestrator.kanban.limb_bridge import run_limb_request

class TestLimbBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)
        self.req_file = self.tmp_dir / "limb_request.json"

        # We need actual Operations / Policy / Orchestrator, but we can't easily mock Orchestrator's dispatch.
        # Instead of a full E2E, we can just use a real Echo Limb which is built-in.
        self.cfg = NeuConfig.load()
        self.ops = Operations.load(self.cfg.protocol_dir / "operations.json")
        self.pol = Policy(self.cfg, self.ops)
        self.orch = Orchestrator(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_req(self, data: dict):
        self.req_file.write_text(json.dumps(data), encoding="utf-8")

    def _soul(self, runtime="limb", op="sys.echo"):
        return f"---\nruntime: {runtime}\nlimb_operation: {op}\n---\n## Core Skills\n"

    def test_valid_request_runs_echo(self):
        self._write_req({"operation": "sys.echo", "params": {"message": "hello limb"}})
        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, self.orch, "t1", self._soul("limb", "sys.echo")
        )
        self.assertTrue(success)
        self.assertEqual(reason, "success")
        self.assertIsNotNone(payload)
        self.assertTrue(payload.get("untrusted"))
        self.assertEqual(payload.get("status"), "success")

    def test_operation_mismatch_denied(self):
        self._write_req({"operation": "sys.echo", "params": {"message": "hello"}})
        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, self.orch, "t1", self._soul("limb", "sys.ping")
        )
        self.assertFalse(success)
        self.assertEqual(reason, "operation mismatch denied")

    def test_unknown_operation_denied(self):
        self._write_req({"operation": "sys.unknown", "params": {}})
        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, self.orch, "t1", self._soul("limb", "sys.unknown")
        )
        self.assertFalse(success)
        self.assertIn("unknown operation sys.unknown", reason)

    def test_high_risk_denied(self):
        self._write_req({"operation": "openmanus.start", "params": {"task": "do something"}})
        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, self.orch, "t1", self._soul("limb", "openmanus.start")
        )
        self.assertFalse(success)
        self.assertIn("high risk denied", reason)

    def test_policy_denial_reaches_task(self):
        # We can force a policy denial by setting limits or violating a rule.
        # But wait, policy is evaluated in orchestrator.dispatch. If dispatch rejects,
        # it returns an attempt with status = 'rejected'.
        self._write_req({"operation": "sys.echo", "params": {"message": "hello"}})

        # Let's mock orchestrator.dispatch to return a rejected attempt
        class MockAttempt:
            class MockResult:
                status = "rejected"
                def to_dict(self): return {"status": "rejected", "error": "policy says no"}
            result = MockResult()

        class MockOrchestrator:
            def dispatch(self, intent): return MockAttempt()

        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, MockOrchestrator(), "t1", self._soul("limb", "sys.echo")
        )
        self.assertFalse(success)
        self.assertEqual(reason, "rejected")
        self.assertTrue(payload["untrusted"])

    def test_forged_request_file_denied(self):
        self.req_file.write_bytes(b"a" * (65 * 1024))
        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, self.orch, "t1", self._soul("limb", "sys.echo")
        )
        self.assertFalse(success)
        self.assertIn("too large", reason)


    def test_non_object_request_denied(self):
        self.req_file.write_text("[]", encoding="utf-8")
        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, self.orch, "t1", self._soul("limb", "sys.echo")
        )
        self.assertFalse(success)
        self.assertEqual(reason, "limb request must be a JSON object")

    def test_deadline_timer_set(self):
        self._write_req({"operation": "sys.echo", "params": {"message": "hello"}})
        success, reason, payload = run_limb_request(
            self.req_file, self.ops, self.pol, self.orch, "t1", self._soul("limb", "sys.echo")
        )
        self.assertTrue(success)
        self.assertEqual(payload.get("timer", {}).get("mode"), "deadline")
