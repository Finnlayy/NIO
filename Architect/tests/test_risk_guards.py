import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path

from core.events import EventBus
from core.learning.risk_guards import RiskGuardEngine, RiskGuardStorage, RiskGuardAlert, _DefaultRiskLimits

SAFE_PLAN = {
    "plan_id": "plan_safe",
    "risk_parameters": {
        "leverage": 3.0,
        "slippage_bps": 8.0,
        "power_factor": 0.95,
        "vault_ratio": 0.2,
        "in_forbidden_zone": False,
        "feed_live": True,
    },
    "schedule": {"triggers": [{"kind": "interval", "every_s": 30}]},
    "approved_by": "system",
    "file_targets": ["Architect/gui/widgets/command_bar.py"],
    "confidence_score": 0.85,
}


class TestRiskGuardEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.system_log = Path(self.tmpdir) / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.engine = RiskGuardEngine(event_bus=self.bus)

    def test_safe_plan_passes(self):
        result = self.engine.check(SAFE_PLAN)
        self.assertTrue(result["passed"])
        self.assertEqual(result["failed"], [])
        self.assertTrue(result["guard_id"].startswith("rg_"))
        self.assertIn("SAFE", result["recommendation"])

    def test_invariant_violation_fails(self):
        plan = dict(SAFE_PLAN)
        plan["risk_parameters"] = dict(SAFE_PLAN["risk_parameters"], leverage=9.0)
        result = self.engine.check(plan)
        self.assertFalse(result["passed"])
        self.assertTrue(any("judge_m8_invariants" in f for f in result["failed"]))

    def test_invalid_schedule_fails(self):
        plan = dict(SAFE_PLAN)
        plan["schedule"] = {"triggers": [{"kind": "interval"}]}  # missing every_s
        result = self.engine.check(plan)
        self.assertFalse(result["passed"])
        self.assertTrue(any("policy_schedule" in f for f in result["failed"]))

    def test_constitution_guard_blocks_system_approval_on_core_files(self):
        plan = dict(SAFE_PLAN)
        plan["file_targets"] = ["Architect/core/config.py"]  # human-only
        result = self.engine.check(plan)
        self.assertFalse(result["passed"])
        self.assertTrue(any("constitution_guard" in f for f in result["failed"]))
        # Human approval clears the guard.
        human_plan = dict(plan, approved_by="human")
        self.assertTrue(self.engine.check(human_plan)["passed"])

    def test_known_error_patterns_produce_warnings_not_failures(self):
        current_state = {
            "error_patterns": [{"error_type": "E_SAFETY_NET", "frequency": 5}],
            "error_pattern_threshold": 3,
        }
        result = self.engine.check(SAFE_PLAN, current_state=current_state)
        self.assertTrue(result["passed"])
        self.assertTrue(any("E_SAFETY_NET" in w for w in result["warnings"]))

    def test_low_confidence_warns(self):
        plan = dict(SAFE_PLAN, confidence_score=0.4)
        result = self.engine.check(plan)
        self.assertTrue(result["passed"])
        self.assertTrue(any("confidence" in w for w in result["warnings"]))

    def test_non_dict_plan_handled(self):
        result = self.engine.check("raw string plan")
        self.assertTrue(result["passed"])  # nothing checkable -> no failures


class TestRiskGuardStorageAndAlerts(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.system_log = Path(self.tmpdir) / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.storage = RiskGuardStorage(guards_dir=str(Path(self.tmpdir) / "guards"))
        self.alert = RiskGuardAlert(event_bus=self.bus)
        self.engine = RiskGuardEngine(event_bus=self.bus)

    def test_save_and_pass_rate(self):
        failed_plan = dict(SAFE_PLAN, risk_parameters=dict(SAFE_PLAN["risk_parameters"], leverage=9.0))
        failed_result = self.engine.check(failed_plan)
        passed_result = self.engine.check(SAFE_PLAN)
        self.storage.save(failed_result)
        self.storage.save(passed_result)
        self.assertEqual(len(self.storage.load_all()), 2)
        self.assertAlmostEqual(self.storage.pass_rate(), 0.5, places=6)

    def test_alert_emits_failure_and_warning_events(self):
        failed_plan = dict(SAFE_PLAN, confidence_score=0.4,
                           risk_parameters=dict(SAFE_PLAN["risk_parameters"], leverage=9.0))
        result = self.engine.check(failed_plan)
        emitted = self.alert.emit_if_failed(result)
        self.assertIn("risk_guard_failed", emitted)
        self.assertIn("risk_guard_warning", emitted)
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("risk_guard_failed", log_text)
        self.assertIn("risk_guard_warning", log_text)

    def test_alert_pass_is_silent(self):
        result = self.engine.check(SAFE_PLAN)
        self.assertEqual(self.alert.emit_if_failed(result), [])
        log_text = self.system_log.read_text(encoding="utf-8") if self.system_log.exists() else ""
        self.assertNotIn("risk_guard_failed", log_text)


if __name__ == "__main__":
    unittest.main()
