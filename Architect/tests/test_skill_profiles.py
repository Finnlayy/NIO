import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path

from core.learning.skill_profiles import (
    SkillProfile,
    SkillProfileUpdater,
    WilsonScoreCalculator,
    make_skill_id,
)


class TestWilsonScoreCalculator(unittest.TestCase):
    def test_reference_values(self):
        # Wilson lower bound, z=1.96: hand-computed reference values
        # (cross-checked against the standard Wilson interval formula).
        self.assertAlmostEqual(WilsonScoreCalculator.compute(5, 5), 0.5655, places=3)
        self.assertAlmostEqual(WilsonScoreCalculator.compute(1, 1), 0.2065, places=3)
        self.assertAlmostEqual(WilsonScoreCalculator.compute(0, 10), 0.0, places=6)
        self.assertAlmostEqual(WilsonScoreCalculator.compute(50, 50), 0.9287, places=3)

    def test_zero_trials(self):
        self.assertEqual(WilsonScoreCalculator.compute(0, 0), 0.0)

    def test_low_samples_are_uncertain(self):
        # 1/1 successes must NOT read as 1.0 proficiency.
        self.assertLess(WilsonScoreCalculator.compute(1, 1), 0.5)

    def test_more_trials_tighten_bound_upwards(self):
        # Same success ratio, more evidence -> higher lower bound.
        low = WilsonScoreCalculator.compute(8, 10)
        high = WilsonScoreCalculator.compute(80, 100)
        self.assertGreater(high, low)

    def test_confidence_level_changes_margin(self):
        permissive = WilsonScoreCalculator.compute(5, 10, confidence=0.90)
        strict = WilsonScoreCalculator.compute(5, 10, confidence=0.99)
        self.assertGreater(permissive, strict)

    def test_result_bounded(self):
        for successes in range(0, 11):
            score = WilsonScoreCalculator.compute(successes, 10)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


class TestSkillProfile(unittest.TestCase):
    def test_init_defaults(self):
        profile = SkillProfile(skill_id="s1", name="exec")
        self.assertEqual(profile.successes, 0)
        self.assertEqual(profile.total_attempts, 0)
        self.assertEqual(profile.wilson_score, 0.0)
        self.assertIsNone(profile.last_evaluated)

    def test_update_success_and_failure(self):
        profile = SkillProfile(skill_id="s1", name="exec")
        profile.update(True)
        self.assertEqual((profile.successes, profile.total_attempts), (1, 1))
        profile.update(False)
        profile.update(False)
        self.assertEqual((profile.successes, profile.total_attempts), (1, 3))
        self.assertAlmostEqual(
            profile.wilson_score,
            WilsonScoreCalculator.compute(1, 3),
            places=6,
        )
        self.assertIsNotNone(profile.last_evaluated)

    def test_persistence_roundtrip(self):
        tmpdir = tempfile.mkdtemp()
        profile = SkillProfile(skill_id="s2", name="planner")
        profile.update(True)
        profile.update(True)
        path = profile.save(base_dir=tmpdir)
        self.assertTrue(Path(path).exists())
        loaded = SkillProfile.load("s2", base_dir=tmpdir)
        self.assertEqual(loaded.successes, 2)
        self.assertAlmostEqual(loaded.wilson_score, profile.wilson_score, places=6)

    def test_load_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            SkillProfile.load("nope", base_dir=tempfile.mkdtemp())


class TestSkillProfileUpdater(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.updater = SkillProfileUpdater(skills_dir=str(Path(self.tmpdir) / "skills"))

    def test_record_outcome_creates_profile(self):
        profile = self.updater.record_outcome("skill_exec", True, name="Execution")
        self.assertEqual(profile.total_attempts, 1)
        self.assertEqual(profile.name, "Execution")
        self.assertTrue((Path(self.tmpdir) / "skills" / "skill_exec.json").exists())

    def test_record_outcome_accumulates(self):
        self.updater.record_outcome("skill_exec", True)
        self.updater.record_outcome("skill_exec", False)
        profile = self.updater.record_outcome("skill_exec", True)
        self.assertEqual((profile.successes, profile.total_attempts), (2, 3))

    def test_load_all_weakest_strongest(self):
        self.updater.record_outcome("skill_weak", False)
        self.updater.record_outcome("skill_weak", False)
        self.updater.record_outcome("skill_strong", True)
        self.updater.record_outcome("skill_strong", True)
        self.assertEqual(len(self.updater.load_all()), 2)
        self.assertEqual(self.updater.weakest(1)[0].skill_id, "skill_weak")
        self.assertEqual(self.updater.strongest(1)[0].skill_id, "skill_strong")

    def test_make_skill_id_deterministic(self):
        self.assertEqual(make_skill_id("math", "sm2"), make_skill_id("math", "sm2"))
        self.assertNotEqual(make_skill_id("math"), make_skill_id("math", "sm2"))


if __name__ == "__main__":
    unittest.main()
