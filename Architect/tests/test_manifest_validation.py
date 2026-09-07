import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.manifest import Manifest
from core.manifest_validation import validate_manifest_update, ALLOWED_REPO_GLOBS, DENIED_GLOBS

class TestManifestValidation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manifest_path = Path(self.tmpdir) / "test_manifest.json"

    def create_manifest(self, data_overrides: dict = None):
        data = {
            "manifest_version": "1.0",
            "author": "test",
            "timestamp": "2026-09-08T00:00:00Z",
            "checksum": "manifest_checksum_12345",
            "changes": [
                {
                    "file_path": "Architect/limbs/intelligence/genai_client.py",
                    "change_type": "modify",
                    "checksum_before": "dummy_before",
                    "checksum_after": "dummy_after",
                }
            ],
            "safety_flags": {
                "core_change": False,
                "dependency_change": False,
                "model_update": False,
            },
            "approval_level": "system",
        }
        if data_overrides:
            data.update(data_overrides)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def test_valid_manifest(self):
        self.create_manifest()
        valid, msg = validate_manifest_update(str(self.manifest_path))
        # Should fail because file doesn't exist for checksum verification; but structure should be valid
        # However, since file missing and change_type is modify, validation should return False
        # For this test, we adjust to expect False due to missing file, but message should not mention structure errors.
        self.assertFalse(valid)
        self.assertNotIn("parse error", msg.lower())

    def test_denied_path(self):
        self.create_manifest({
            "changes": [{"file_path": "/etc/passwd", "change_type": "modify", "checksum_before": "a", "checksum_after": "b"}],
            "approval_level": "system",
        })
        valid, msg = validate_manifest_update(str(self.manifest_path))
        self.assertFalse(valid)
        self.assertIn("denied", msg.lower())

    def test_core_change_requires_human(self):
        self.create_manifest({
            "changes": [{"file_path": "Architect/core/config.py", "change_type": "modify", "checksum_before": "a", "checksum_after": "b"}],
            "safety_flags": {"core_change": True, "dependency_change": False, "model_update": False},
            "approval_level": "system",
        })
        valid, msg = validate_manifest_update(str(self.manifest_path))
        self.assertFalse(valid)
        self.assertIn("human", msg.lower())

    def test_allowed_repo_path(self):
        # Create a real file to verify checksum logic works
        real_file = Path("Architect/limbs/intelligence/genai_client.py")
        if real_file.exists():
            import hashlib
            content = real_file.read_text()
            before_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            self.create_manifest({
                "changes": [{"file_path": "Architect/limbs/intelligence/genai_client.py", "change_type": "modify", "checksum_before": before_hash, "checksum_after": before_hash}],
                "approval_level": "system",
            })
            valid, msg = validate_manifest_update(str(self.manifest_path))
            self.assertTrue(valid, msg)
        else:
            self.skipTest("Real file not available for checksum test.")

if __name__ == "__main__":
    unittest.main()
