import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.events import EventBus
from core.alignment.alignment_tracker import AlignmentTracker
from core.alignment.alignment_dashboard import AlignmentDashboard
from gui.views.alignment_dashboard import AlignmentDashboardModel, PYQT6_AVAILABLE


class _Point:
    """Dict-like trajectory point stub with attribute access."""

    def __init__(self, metrics):
        self.metrics = metrics


class TestSafetyScore(unittest.TestCase):
    def setUp(self):
        self.tracker = AlignmentTracker()

    def test_all_passed(self):
        guards = [{"passed": True}, {"passed": True}]
        self.assertEqual(self.tracker.compute_safety_score(guards), 1.0)

    def test_mixed(self):
        guards = [{"passed": True}, {"passed": False}]
        self.assertEqual(self.tracker.compute_safety_score(guards), 0.5)

    def test_empty_is_zero(self):
        self.assertEqual(self.tracker.compute_safety_score([]), 0.0)

    def test_execution_results_count(self):
        guards = [{"passed": True}]
        executions = [{"verdict": "accept", "errors": []},
                      {"verdict": "reject", "errors": ["E_INTERNAL: x"]}]
        # 1 clean guard + 1 clean execution out of 3 assessments.
        self.assertAlmostEqual(self.tracker.compute_safety_score(guards, executions), 2 / 3, places=4)


class TestLearningEfficiency(unittest.TestCase):
    def setUp(self):
        self.tracker = AlignmentTracker()

    def test_improving_success_rate(self):
        points = [_Point({"success_rate": r}) for r in (0.4, 0.6, 0.8, 1.0)]
        self.assertEqual(self.tracker.compute_learning_efficiency(points), 1.0)

    def test_declining_success_rate(self):
        points = [_Point({"success_rate": r}) for r in (1.0, 0.6, 0.2)]
        self.assertEqual(self.tracker.compute_learning_efficiency(points), 0.0)

    def test_flat_is_neutral(self):
        points = [_Point({"success_rate": 0.7})] * 4
        self.assertAlmostEqual(self.tracker.compute_learning_efficiency(points), 0.5, places=6)

    def test_error_rate_inverted(self):
        improving = [_Point({"error_rate": r}) for r in (0.8, 0.5, 0.2)]
        self.assertEqual(self.tracker.compute_learning_efficiency(improving), 1.0)

    def test_fewer_than_two_points_is_zero(self):
        self.assertEqual(self.tracker.compute_learning_efficiency([_Point({"success_rate": 0.9})]), 0.0)
        self.assertEqual(self.tracker.compute_learning_efficiency([]), 0.0)

    def test_explicit_metric_key(self):
        points = [_Point({"quality": q}) for q in (0.2, 0.8)]
        self.assertEqual(self.tracker.compute_learning_efficiency(points, metric_key="quality"), 1.0)

    def test_dict_points_supported(self):
        points = [{"metrics": {"success_rate": 0.1}}, {"metrics": {"success_rate": 0.9}}]
        self.assertEqual(self.tracker.compute_learning_efficiency(points), 1.0)


class TestAlignmentScore(unittest.TestCase):
    def setUp(self):
        self.tracker = AlignmentTracker()

    def test_known_scenario_formula(self):
        # preference=0.8, guard pass rate=2/3, efficiency=1.0
        # alignment = 0.5*0.8 + 0.3*(2/3) + 0.2*1.0 = 0.4 + 0.2 + 0.2 = 0.8
        trajectory = [{"metrics": {"success_rate": 0.1}}, {"metrics": {"success_rate": 0.9}}]
        feedback = [{"preference_ratio": 0.8}]
        guards = [{"passed": True}, {"passed": True}, {"passed": False}]
        result = self.tracker.compute_alignment_score(trajectory, feedback, guards)
        self.assertAlmostEqual(result["alignment_score"], 0.8, places=3)
        self.assertAlmostEqual(result["components"]["feedback_preference_ratio"], 0.8, places=4)
        self.assertAlmostEqual(result["components"]["risk_guard_pass_rate"], 2 / 3, places=4)
        self.assertEqual(result["components"]["learning_efficiency"], 1.0)

    def test_alignment_with_rating_fallback(self):
        # No preference ratios: falls back to normalized average rating (4/5 = 0.8).
        trajectory = [{"metrics": {"success_rate": 0.5}}] * 3
        feedback = [{"average_rating_normalized": 0.8}]
        guards = [{"passed": True}]
        result = self.tracker.compute_alignment_score(trajectory, feedback, guards)
        self.assertAlmostEqual(result["components"]["feedback_preference_ratio"], 0.8, places=4)

    def test_weights_sum(self):
        from core.alignment.alignment_tracker import ALIGNMENT_WEIGHTS
        self.assertAlmostEqual(sum(ALIGNMENT_WEIGHTS.values()), 1.0)

    def test_compute_all_includes_safety(self):
        trajectory = [{"metrics": {"success_rate": 0.9}}]
        result = self.tracker.compute_all(
            trajectory, [{"preference_ratio": 1.0}],
            [{"passed": True}], execution_results=[{"verdict": "accept", "errors": []}])
        self.assertIn("safety_score", result)
        self.assertEqual(result["safety_score"], 1.0)
        self.assertIn("computed_at", result)


class TestAlignmentDashboard(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.system_log = self.tmpdir / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.service = AlignmentDashboard(alignment_dir=str(self.tmpdir / "alignment"), event_bus=self.bus)

    def _snapshot(self, score):
        return {
            "alignment_score": score,
            "safety_score": min(1.0, score + 0.1),
            "learning_efficiency": max(0.0, score - 0.1),
            "components": {},
        }

    def test_save_and_load_metrics(self):
        self.service.save_metrics("plan_x", self._snapshot(0.7))
        snapshots = self.service.load_metrics("plan_x")
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["plan_id"], "plan_x")

    def test_latest(self):
        self.service.save_metrics("plan_x", self._snapshot(0.6))
        self.service.save_metrics("plan_x", self._snapshot(0.8))
        self.assertEqual(self.service.latest("plan_x")["alignment_score"], 0.8)
        self.assertEqual(self.service.latest("plan_none"), {})

    def test_aggregate_metrics(self):
        for score in (0.5, 0.7, 0.9):
            self.service.save_metrics("plan_x", self._snapshot(score))
        aggregate = self.service.aggregate_metrics("plan_x")
        self.assertEqual(aggregate["snapshot_count"], 3)
        self.assertEqual(aggregate["alignment_score_stats"]["min"], 0.5)
        self.assertEqual(aggregate["alignment_score_stats"]["max"], 0.9)
        self.assertAlmostEqual(aggregate["alignment_score_stats"]["mean"], 0.7, places=4)
        self.assertEqual(len(aggregate["history"]), 3)

    def test_save_emits_alignment_updated(self):
        self.service.save_metrics("plan_x", self._snapshot(0.7))
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("alignment_updated", log_text)

    def test_headless_dashboard_model(self):
        self.service.save_metrics("plan_x", self._snapshot(0.75))
        from core.learning.risk_guards import RiskGuardStorage
        risk_storage = RiskGuardStorage(guards_dir=str(self.tmpdir / "guards"))
        risk_storage.save({"guard_id": "rg_1", "passed": True})
        model = AlignmentDashboardModel(alignment_service=self.service,
                                        risk_storage=risk_storage, plan_id="plan_x")
        data = model.compose()
        rows = dict(data["rows"])
        self.assertEqual(rows["alignment_score"], 0.75)
        self.assertEqual(rows["risk_guards_passed"], "1/1")
        summary = model.format_summary()
        self.assertIn("alignment_score: 0.75", summary)


@unittest.skipUnless(PYQT6_AVAILABLE, "PyQt6 not installed")
class TestAlignmentDashboardTab(unittest.TestCase):
    def test_tab_refresh(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from gui.views.alignment_dashboard import AlignmentDashboardTab
        tmpdir = Path(tempfile.mkdtemp())
        service = AlignmentDashboard(alignment_dir=str(tmpdir / "alignment"))
        service.save_metrics("plan_x", {"alignment_score": 0.8, "safety_score": 0.9,
                                        "learning_efficiency": 0.7, "components": {}})
        tab = AlignmentDashboardTab(model=AlignmentDashboardModel(
            alignment_service=service, plan_id="plan_x"))
        tab.refresh()
        self.assertIn("0.8", tab.metrics_labels["alignment_score"].text())


if __name__ == "__main__":
    unittest.main()
