import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
from pathlib import Path
import json
import hashlib

from core.manifest import Manifest
from core.manifest_validation import validate_manifest_update
from core.self_modification_safety import SelfModificationSafety
from core.policy import Policy

class TestOuroboros(unittest.TestCase):
    """Ouroboros test: full self-modification loop in sandbox using BootstrapLimb + Manifest + Safety."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sandbox = Path(self.tmpdir) / "sandbox"
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.sandbox / "test_manifest.json"
        self.policy = Policy()
        # Create a dummy file to modify
        self.target_file = Path("Architect/core/test_target_ouroboros.py")
        Path("Architect/core").mkdir(parents=True, exist_ok=True)
        self.target_file.write_text("# Original content\n")

    def tearDown(self):
        import shutil
        if self.target_file.exists():
            self.target_file.unlink()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ouroboros_full_loop(self):
        # 1. Create manifest
        import hashlib
        original_content = self.target_file.read_text()
        original_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()
        new_content = original_content + "# Modified by self-modification\n"
        new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
        manifest_data = {
            "manifest_version": "1.0",
            "checksum": "manifest_checksum_12345",
            "author": "system_ouroboros_test",
            "timestamp": "2026-09-08T00:00:00Z",
            "changes": [
                {
                    "file_path": "Architect/core/test_target_ouroboros.py",
                    "change_type": "modify",
                    "line_numbers": [1],
                    "checksum_before": original_hash,
                    "checksum_after": new_hash,
                }
            ],
            "safety_flags": {
                "core_change": False,
                "dependency_change": False,
                "model_update": False,
            },
            "approval_level": "system",
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # 2. Validate manifest
        valid, msg = validate_manifest_update(str(self.manifest_path))
        self.assertTrue(valid, msg)

        # 3. Create backup BEFORE applying modification
        safety = SelfModificationSafety()
        backup_path = safety.create_backup(self.target_file)
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.exists())

        # 4. Apply modification (simulated: we write new content to target file)
        # In a real loop, BootstrapLimb or external process applies the patch.
        # For this test, we directly apply to verify the manifest and safety pipeline.
        self.target_file.write_text(new_content)

        # Verify backup hash matches original
        original_hash_from_backup = hashlib.sha256(original_content.encode("utf-8")).hexdigest()
        # Check backup content equals original
        backup_content = backup_path.read_text()
        self.assertEqual(backup_content, original_content)

        # 5. Verify backup and manifest checksum
        manifest_after = Manifest(str(self.manifest_path))
        current_hash = hashlib.sha256(self.target_file.read_text().encode("utf-8")).hexdigest()
        # Since we wrote new content, checksum_after should match
        self.assertEqual(manifest_after.extract_changes()[0]["checksum_after"], new_hash)
        self.assertEqual(current_hash, new_hash)

        # 6. Verify manifest checksum after apply
        rollback_ok = safety.rollback(self.target_file, backup_file=backup_path)
        self.assertTrue(rollback_ok)
        restored_content = self.target_file.read_text()
        self.assertEqual(restored_content, original_content)

        # 7. Verify event emission (optional: emit event manually)
        from core.events import EventBus
        bus = EventBus()
        event_result = bus.emit(bus.build_event(
            event_kind="self_modification_complete",
            job_id="ouroboros_001",
            message="Ouroboros loop completed successfully.",
        ))
        self.assertTrue(event_result)

    def test_rollback_on_failure(self):
        # Create a manifest with incorrect checksum (stale)
        original_content = self.target_file.read_text()
        original_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()
        manifest_data = {
            "manifest_version": "1.0",
            "checksum": "rollback_checksum_12345",
            "author": "system_rollback_test",
            "timestamp": "2026-09-08T00:00:00Z",
            "changes": [
                {
                    "file_path": "Architect/core/test_target_ouroboros.py",
                    "change_type": "modify",
                    "checksum_before": "wrong_checksum_12345",
                    "checksum_after": "new_checksum_67890",
                }
            ],
            "safety_flags": {"core_change": False, "dependency_change": False, "model_update": False},
            "approval_level": "system",
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # Validation should fail due to checksum mismatch
        valid, msg = validate_manifest_update(str(self.manifest_path))
        self.assertFalse(valid)
        self.assertIn("Checksum mismatch", msg)

if __name__ == "__main__":
    unittest.main()
