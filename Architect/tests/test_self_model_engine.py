import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.self_model.self_model_engine import SelfModelEngine, Insight
from core.self_model.insight_display import InsightDisplay
from core.trajectory.trajectory_collector import TrajectoryPoint


def _trajectory():
    return [
        TrajectoryPoint(timestamp="2026-09-07T12:00:00Z", state="PLANNING",
                        event_ids=["evt_1"], plan_version=1),
        TrajectoryPoint(timestamp="2026-09-07T12:01:00Z", state="RUNNING",
                        metrics={"success_rate": 0.4}, event_ids=["evt_2"], plan_version=1),
        TrajectoryPoint(timestamp="2026-09-07T12:02:00Z", state="COMPLETE",
                        metrics={"success_rate": 0.9}, event_ids=["evt_3"], plan_version=1),
    ]


ALIGNMENT_GOOD = {
    "alignment_score": 0.82,
    "safety_score": 0.95,
    "learning_efficiency": 0.8,
    "components": {"feedback_preference_ratio": 0.9, "risk_guard_pass_rate": 0.95,
                   "learning_efficiency": 0.8},
}
ALIGNMENT_WEAK = {
    "alignment_score": 0.31,
    "safety_score": 0.4,
    "learning_efficiency": 0.1,
    "components": {"feedback_preference_ratio": 0.4, "risk_guard_pass_rate": 0.4,
                   "learning_efficiency": 0.1},
}


class TestInsight(unittest.TestCase):
    def test_category_validation(self):
        with self.assertRaises(ValueError):
            Insight(category="junk", content="x")

    def test_deterministic_id(self):
        a = Insight(category="strength", content="same", timestamp="t")
        b = Insight(category="strength", content="same", timestamp="t")
        self.assertEqual(a.insight_id, b.insight_id)
        self.assertTrue(a.insight_id.startswith("ins_"))

    def test_confidence_bounded(self):
        insight = Insight(category="weakness", content="x", confidence=9.0)
        self.assertEqual(insight.confidence, 1.0)

    def test_roundtrip(self):
        insight = Insight(category="recommendation", content="do more", confidence=0.7,
                          related_events=["evt_1"], related_plans=["plan_1"])
        restored = Insight.from_dict(insight.to_dict())
        self.assertEqual(restored.content, "do more")
        self.assertEqual(restored.related_plans, ["plan_1"])


class TestSelfModelEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.engine = SelfModelEngine(insights_dir=str(self.tmpdir / "insights"))

    def test_strengths_from_good_alignment(self):
        insights = self.engine.generate_insights(_trajectory(), ALIGNMENT_GOOD)
        categories = {i.category for i in insights}
        self.assertIn("strength", categories)
        self.assertTrue(any("alignment" in i.content for i in insights if i.category == "strength"))

    def test_weaknesses_from_weak_alignment_and_patterns(self):
        insights = self.engine.generate_insights(
            _trajectory(), ALIGNMENT_WEAK,
            skill_profiles=[{"skill_id": "s1", "name": "exec", "wilson_score": 0.2, "total_attempts": 4}],
            error_patterns=[{"error_type": "E_SAFETY_NET", "frequency": 5}])
        weaknesses = [i.content for i in insights if i.category == "weakness"]
        self.assertTrue(any("alignment" in w for w in weaknesses))
        self.assertTrue(any("exec" in w for w in weaknesses))
        self.assertTrue(any("E_SAFETY_NET" in w for w in weaknesses))

    def test_recommendations_for_weak_skills_and_patterns(self):
        insights = self.engine.generate_insights(
            _trajectory(), ALIGNMENT_WEAK,
            skill_profiles=[{"skill_id": "skill_xyz", "name": "planner", "wilson_score": 0.3,
                             "total_attempts": 6}],
            error_patterns=[{"error_type": "E_TRIGGER_INVALID", "frequency": 3}])
        recommendations = " | ".join(i.content for i in insights if i.category == "recommendation")
        self.assertIn("skill_xyz", recommendations)
        self.assertIn("E_TRIGGER_INVALID", recommendations)

    def test_preference_recommendation_when_low(self):
        insights = self.engine.generate_insights(_trajectory(), ALIGNMENT_WEAK)
        recommendations = [i.content for i in insights if i.category == "recommendation"]
        self.assertTrue(any("human feedback" in r for r in recommendations))

    def test_empty_data_falls_back_to_baseline_insight(self):
        insights = self.engine.generate_insights([], {})
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0].category, "recommendation")

    def test_insights_reference_trajectory_events_and_plan(self):
        insights = self.engine.generate_insights(_trajectory(), ALIGNMENT_WEAK, plan_id="plan_z")
        for insight in insights:
            self.assertIsInstance(insight, Insight)
        related_plans = {p for i in insights for p in i.related_plans}
        self.assertIn("plan_z", related_plans)

    def test_save_insights(self):
        insights = self.engine.generate_insights(_trajectory(), ALIGNMENT_GOOD)
        path = self.engine.save_insights(insights)
        self.assertTrue(Path(path).exists())
        self.assertIn("insights", str(path))
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["insight_count"], len(insights))
        self.assertEqual(len(payload["insights"]), len(insights))


class TestInsightDisplay(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.engine = SelfModelEngine(insights_dir=str(self.tmpdir / "insights"))
        self.engine.save_insights(self.engine.generate_insights(_trajectory(), ALIGNMENT_GOOD))
        self.engine.save_insights(self.engine.generate_insights(_trajectory(), ALIGNMENT_WEAK))
        self.display = InsightDisplay(insights_dir=str(self.tmpdir / "insights"))

    def test_load_insights_newest_first(self):
        insights = self.display.load_insights()
        self.assertGreater(len(insights), 0)
        for insight in insights:
            self.assertIn("insight_id", insight)

    def test_format_for_display_cli(self):
        line = InsightDisplay.format_for_display({
            "category": "strength", "content": "Reliable execution", "confidence": 0.8})
        self.assertIn("[+]", line)
        self.assertIn("Reliable execution", line)
        self.assertIn("0.80", line)

    def test_format_for_display_gui(self):
        html = InsightDisplay.format_for_display({
            "category": "weakness", "content": "Slow planner", "confidence": 0.6}, style="gui")
        self.assertIn("<b>", html)
        self.assertIn("WEAKNESS", html)

    def test_format_all_groups_by_category(self):
        formatted = InsightDisplay.format_all(self.display.load_insights())
        self.assertIn("== Strengths ==", formatted)
        self.assertIn("== Recommendations ==", formatted)
        gui_formatted = InsightDisplay.format_all(self.display.load_insights(), style="gui")
        self.assertTrue(gui_formatted.startswith("<html>"))


if __name__ == "__main__":
    unittest.main()
