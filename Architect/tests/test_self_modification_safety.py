import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path

from core.self_modification_safety import SelfModificationSafety

class TestSelfModificationSafety(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.safety = SelfModificationSafety(workspace_root=str(Path(self.tmpdir) / "workspace"))
        # Override backup dir
        self.safety.backup_dir = Path(self.tmpdir) / "backups"
        self.safety.backup_dir.mkdir(parents=True, exist_ok=True)

    def test_create_backup_and_verify(self):
        test_file = Path(self.tmpdir) / "test_file.txt"
        test_file.write_text("Hello, self is a test file for backup verification.")
        backup_path = self.safety.create_backup(test_file)
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.exists())
        # Verify content matches
        original = test_file.read_text()
        backup_content = backup_path.read_text()
        self.assertEqual(original, backup_content)

    def test_rollback(self):
        test_file = Path(self.tmpdir) / "test_rollback.txt"
        test_file.write_text("Original content before rollback.")
        backup_path = self.safety.create_backup(test_file)
        # Modify file
        test_file.write_text("Modified content.")
        # Rollback
        rollback_ok = self.safety.rollback(test_file, backup_file=backup_path)
        self.assertTrue(rollback_ok)
        restored = test_file.read_text()
        self.assertEqual(restored, "Original content before rollback.")

    def test_compute_hash(self):
        test_file = Path(self.tmpdir) / "hash_test.txt"
        test_file.write_text("Hash verification content.")
        hash1 = self.safety._compute_hash(test_file)
        hash2 = self.safety._compute_hash(test_file)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA-256 hex length

if __name__ == "__main__":
    unittest.main()
