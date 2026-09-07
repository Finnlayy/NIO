import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.outcome_parser import OutcomeParser, OutcomeIngestion
from core.schema_utils import SchemaInvalid

VALID_OUTCOME = {
    "job_id": "job_100",
    "intent_id": "intent_100",
    "limb": "judge_m8_agent",
    "verdict": "accept",
    "errors": [],
    "metrics": {"success_rate": 1.0},
    "elapsed_s": 12.5,
    "clock_s": 42.0,
    "timestamp": "2026-09-07T12:00:00Z",
}


class TestOutcomeParser(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.parser = OutcomeParser()
        self.valid_file = Path(self.tmpdir) / "valid_outcome.json"
        with open(self.valid_file, "w", encoding="utf-8") as f:
            json.dump(VALID_OUTCOME, f)

    def _write(self, payload, name="t.json"):
        path = Path(self.tmpdir) / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def test_parse_valid_file(self):
        outcome = self.parser.parse(self.valid_file)
        self.assertEqual(outcome["job_id"], "job_100")
        self.assertEqual(outcome["verdict"], "accept")

    def test_parse_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.parser.parse(Path(self.tmpdir) / "missing.json")

    def test_missing_required_field_raises(self):
        bad = dict(VALID_OUTCOME)
        del bad["verdict"]
        with self.assertRaises(SchemaInvalid) as ctx:
            self.parser.validate_dict(bad)
        self.assertIn("verdict", str(ctx.exception))

    def test_invalid_verdict_enum_raises(self):
        bad = dict(VALID_OUTCOME, verdict="maybe")
        with self.assertRaises(SchemaInvalid):
            self.parser.validate_dict(bad)

    def test_negative_elapsed_raises(self):
        bad = dict(VALID_OUTCOME, elapsed_s=-1.0)
        with self.assertRaises(SchemaInvalid):
            self.parser.validate_dict(bad)

    def test_errors_array_type_checked(self):
        bad = dict(VALID_OUTCOME, errors="not_a_list")
        with self.assertRaises(SchemaInvalid):
            self.parser.validate_dict(bad)

    def test_extra_fields_allowed(self):
        extended = dict(VALID_OUTCOME, success="success", correctness_score=0.99)
        self.parser.validate_dict(extended)  # should not raise

    def test_malformed_json_raises(self):
        path = Path(self.tmpdir) / "malformed.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.parser.parse(path)


class TestOutcomeIngestion(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_dir = Path(self.tmpdir) / "outcomes"
        from core.events import EventBus
        self.system_log = Path(self.tmpdir) / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.ingestion = OutcomeIngestion(event_bus=self.bus, outcomes_dir=str(self.outcomes_dir))

    def test_ingest_persists_and_emits(self):
        outcome = self.ingestion.ingest(dict(VALID_OUTCOME))
        self.assertEqual(outcome["job_id"], "job_100")
        stored = self.outcomes_dir / "job_100.json"
        self.assertTrue(stored.exists())
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("execution_complete", log_text)

    def test_ingest_file(self):
        src = Path(self.tmpdir) / "result_file.json"
        with open(src, "w", encoding="utf-8") as f:
            json.dump(dict(VALID_OUTCOME, job_id="job_200"), f)
        outcome = self.ingestion.ingest_file(src)
        self.assertEqual(outcome["job_id"], "job_200")
        self.assertTrue((self.outcomes_dir / "job_200.json").exists())

    def test_ingest_directory_skips_invalid(self):
        results = Path(self.tmpdir) / "results"
        results.mkdir()
        with open(results / "ok.json", "w", encoding="utf-8") as f:
            json.dump(dict(VALID_OUTCOME, job_id="job_ok"), f)
        with open(results / "bad.json", "w", encoding="utf-8") as f:
            json.dump({"job_id": "bad"}, f)  # missing required fields
        ingested = self.ingestion.ingest_directory(results)
        self.assertEqual([o["job_id"] for o in ingested], ["job_ok"])


if __name__ == "__main__":
    unittest.main()
