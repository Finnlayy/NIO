import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path
import json
from core.archive import Archive

class TestArchive(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.archive = Archive(archive_dir=str(Path(self.tmpdir) / "archive"))

    def test_save_and_lookup(self):
        job_data = {"job_id": "job_001", "status": "complete", "metrics": {"elapsed": 12.5}}
        digest = self.archive.save("job_001", job_data)
        self.assertEqual(len(digest), 64)
        loaded = self.archive.lookup("job_001")
        self.assertEqual(loaded.get("job_id"), "job_001")
        self.assertEqual(loaded.get("status"), "complete")

    def test_lookup_missing(self):
        result = self.archive.lookup("nonexistent_job_999")
        self.assertEqual(result, {})

    def test_stats(self):
        self.archive.save("job_001", {"test": True})
        stats = self.archive.stats()
        self.assertIn("archive_file_count", stats)
        self.assertGreaterEqual(stats["archive_file_count"], 1)

    def test_verify(self):
        self.archive.save("job_001", {"test": True})
        failures = self.archive.verify()
        self.assertEqual(failures, [])

    def test_compact_removes_empty(self):
        # Create an empty archive file
        empty_path = self.archive.archive_dir / "empty.json"
        empty_path.write_text("")
        compact_result = self.archive.compact()
        self.assertTrue(compact_result)
        # After compact, empty file should be removed (if compact removes it; our basic implementation removes empty files)
        # Note: our compact only removes empty files; it does not merge history. This aligns with Phase 3 basic requirement.
        self.assertFalse(empty_path.exists())

if __name__ == "__main__":
    unittest.main()
