import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import datetime
from pathlib import Path

from core.learning.spaced_repetition import (
    SpacedRepetitionEngine,
    ReviewScheduler,
    DEFAULT_EASE_FACTOR,
    MIN_EASE_FACTOR,
)


class _FixedClock:
    """Deterministic clock for schedule tests."""

    def __init__(self, start: datetime.datetime):
        self.now_value = start

    def __call__(self) -> datetime.datetime:
        return self.now_value


class TestSM2Algorithm(unittest.TestCase):
    def test_reference_ease_factors(self):
        # Classic SM-2 EF updates from EF=2.5 (hand-checked reference values).
        self.assertAlmostEqual(SpacedRepetitionEngine.update_ease_factor(2.5, 5), 2.6, places=3)
        self.assertAlmostEqual(SpacedRepetitionEngine.update_ease_factor(2.5, 4), 2.5, places=3)
        self.assertAlmostEqual(SpacedRepetitionEngine.update_ease_factor(2.5, 3), 2.36, places=3)
        self.assertAlmostEqual(SpacedRepetitionEngine.update_ease_factor(2.5, 0), 1.7, places=3)

    def test_ease_factor_floor(self):
        self.assertEqual(SpacedRepetitionEngine.update_ease_factor(1.3, 0), MIN_EASE_FACTOR)

    def test_interval_grows_on_success(self):
        # interval' = interval * EF' when quality >= 3
        ef = SpacedRepetitionEngine.update_ease_factor(2.5, 5)   # 2.6
        self.assertAlmostEqual(SpacedRepetitionEngine.update_interval(1.0, ef, 5), 2.6, places=3)
        self.assertAlmostEqual(SpacedRepetitionEngine.update_interval(2.6, ef, 5), 6.76, places=3)

    def test_interval_resets_on_failure(self):
        self.assertEqual(SpacedRepetitionEngine.update_interval(6.0, 2.5, 2), 1.0)
        self.assertEqual(SpacedRepetitionEngine.update_interval(6.0, 2.5, 0), 1.0)

    def test_quality_bounds(self):
        # Fractional / out-of-range quality is clamped, not crashed on.
        ef = SpacedRepetitionEngine.update_ease_factor(2.5, 99)
        self.assertAlmostEqual(ef, SpacedRepetitionEngine.update_ease_factor(2.5, 5), places=6)


class TestSpacedRepetitionEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.reviews_dir = Path(self.tmpdir) / "reviews"
        self.clock = _FixedClock(datetime.datetime(2026, 9, 7, 12, 0, 0))
        self.engine = SpacedRepetitionEngine(reviews_dir=str(self.reviews_dir), clock_fn=self.clock)

    def test_first_review_success(self):
        record = self.engine.review("item_1", 4)
        self.assertEqual(record["repetitions"], 1)
        self.assertAlmostEqual(record["interval_days"], 2.5, places=3)  # 1 * 2.5 (EF unchanged at q=4)
        self.assertEqual(record["next_review_at"], "2026-09-10T00:00:00Z")

    def test_failure_resets_interval_and_repetitions(self):
        self.engine.review("item_1", 5)
        record = self.engine.review("item_1", 1)
        self.assertEqual(record["repetitions"], 0)
        self.assertEqual(record["interval_days"], 1.0)

    def test_ladder_over_multiple_reviews(self):
        self.engine.review("item_2", 5)   # interval 2.6, EF 2.6
        record = self.engine.review("item_2", 5)  # EF -> 2.7, interval 2.6 * 2.7 = 7.02
        self.assertAlmostEqual(record["interval_days"], 7.02, places=3)
        self.assertAlmostEqual(record["ease_factor"], 2.7, places=3)
        self.assertEqual(record["repetitions"], 2)

    def test_schedule_review_future_timestamp(self):
        self.engine.review("item_3", 5)
        next_at = self.engine.schedule_review("item_3")
        expected = self.clock.now_value + datetime.timedelta(days=self.engine.get_review("item_3")["interval_days"])
        self.assertEqual(next_at, expected.isoformat() + "Z")

    def test_due_reviews_and_event(self):
        from core.events import EventBus
        bus = EventBus(system_log_path=str(Path(self.tmpdir) / "system.log"))
        bus.event_sinks = {"stderr": False, "file": True}
        engine = SpacedRepetitionEngine(reviews_dir=str(Path(self.tmpdir) / "r2"),
                                        event_bus=bus, clock_fn=self.clock)
        engine.review("item_due", 5)  # next review ~2.6 days out
        self.assertEqual(engine.due_reviews(), [])
        # Advance the clock past the next review date.
        self.clock.now_value = self.clock.now_value + datetime.timedelta(days=3)
        due = engine.due_reviews()
        self.assertIn("item_due", due)
        log_text = (Path(self.tmpdir) / "system.log").read_text(encoding="utf-8")
        self.assertIn("review_due", log_text)

    def test_persistence_roundtrip(self):
        self.engine.review("item_persist", 5)
        fresh = SpacedRepetitionEngine(reviews_dir=str(self.reviews_dir), clock_fn=self.clock)
        record = fresh.get_review("item_persist")
        self.assertAlmostEqual(record["ease_factor"], 2.6, places=3)
        self.assertAlmostEqual(record["interval_days"], 2.6, places=3)

    def test_scheduler_facade(self):
        scheduler = ReviewScheduler(self.engine)
        scheduler.review_item("item_sched", 5)
        self.assertIsNotNone(scheduler.next_review("item_sched"))
        self.assertEqual(scheduler.items_due(), [])


if __name__ == "__main__":
    unittest.main()
