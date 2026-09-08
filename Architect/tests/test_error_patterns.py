import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.events import EventBus
from core.learning.error_patterns import (
    ErrorPattern,
    ErrorPatternDetector,
    ErrorPatternStorage,
    classify_error,
)


class TestClassifyError(unittest.TestCase):
    def test_explicit_codes(self):
        self.assertEqual(classify_error("E_SAFETY_NET: feed stale"), "E_SAFETY_NET")
        self.assertEqual(classify_error({"code": "E_TRIGGER_INVALID", "message": "bad cron"}), "E_TRIGGER_INVALID")

    def test_keyword_fallback(self):
        self.assertEqual(classify_error("job timed out after 30s"), "E_TIMEOUT")
        self.assertEqual(classify_error("schema validation failed for envelope"), "E_SCHEMA_INVALID")
        self.assertEqual(classify_error("path denied by sandbox policy"), "E_PERMISSION_DENIED")

    def test_unknown(self):
        self.assertEqual(classify_error("something odd happened"), "E_UNKNOWN")


class TestErrorPatternDetector(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.storage = ErrorPatternStorage(patterns_dir=str(Path(self.tmpdir) / "patterns"))
        self.system_log = Path(self.tmpdir) / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.detector = ErrorPatternDetector(event_bus=self.bus, storage=self.storage)

    def test_groups_by_error_type(self):
        errors = [
            "E_SAFETY_NET: feed stale",
            "E_SAFETY_NET: feed stale again",
            "E_SCHEMA_INVALID: bad envelope",
        ]
        patterns = self.detector.detect(errors)
        by_type = {p.error_type: p for p in patterns}
        self.assertEqual(set(by_type), {"E_SAFETY_NET", "E_SCHEMA_INVALID"})
        self.assertEqual(by_type["E_SAFETY_NET"].frequency, 2)
        self.assertEqual(len(by_type["E_SAFETY_NET"].sample_messages), 2)

    def test_empty_errors(self):
        self.assertEqual(self.detector.detect([]), [])

    def test_pattern_id_deterministic_per_type(self):
        p1 = self.detector.detect(["E_INTERNAL: a"])[0]
        p2 = self.detector.detect(["E_INTERNAL: totally different message"])[0]
        self.assertEqual(p1.pattern_id, p2.pattern_id)

    def test_alert_threshold(self):
        pattern = ErrorPattern(pattern_id="ep_x", error_type="E_INTERNAL", frequency=3)
        self.assertFalse(self.detector.alert_if_threshold_exceeded(pattern, threshold=3))
        pattern.frequency = 4
        self.assertTrue(self.detector.alert_if_threshold_exceeded(pattern, threshold=3))
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("error_pattern_alert", log_text)

    def test_detect_and_store_merges_persisted_frequency(self):
        from core.learning.error_patterns import make_pattern_id
        # First pass: 1 occurrence stored.
        self.detector.detect_and_store(["E_TIMEOUT: job timed out"])
        stored = self.storage.load_all()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].frequency, 1)
        # Second pass: 2 more occurrences -> merged frequency 3.
        self.detector.detect_and_store(["E_TIMEOUT: job timed out", "E_TIMEOUT: again"])
        stored = self.storage.load_all()
        self.assertEqual(stored[0].frequency, 3)
        self.assertEqual(stored[0].pattern_id, make_pattern_id("E_TIMEOUT", []))

    def test_storage_save_load_roundtrip(self):
        pattern = ErrorPattern(pattern_id="ep_abc", error_type="E_INTERNAL", frequency=7,
                               first_seen="2026-09-07T00:00:00Z", last_seen="2026-09-07T01:00:00Z",
                               sample_messages=["boom"], tokens=["boom"])
        path = self.storage.save(pattern)
        self.assertTrue(Path(path).exists())
        loaded = self.storage.load("ep_abc")
        self.assertEqual(loaded.frequency, 7)
        self.assertEqual(loaded.error_type, "E_INTERNAL")
        self.assertIsNone(self.storage.load("missing_id"))

    def test_frequent_filter(self):
        self.detector.detect_and_store(["E_INTERNAL: a", "E_INTERNAL: b", "E_INTERNAL: c"])
        frequent = self.storage.frequent(threshold=2)
        self.assertEqual(len(frequent), 1)
        self.assertEqual(frequent[0].frequency, 3)


if __name__ == "__main__":
    unittest.main()
