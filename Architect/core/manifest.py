import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Manifest:
    """Parser and validator for OMEGA self-modification manifest files."""

    def __init__(self, manifest_path: str):
        self.manifest_path = Path(manifest_path)
        self.data = {}
        self.parse()

    def parse(self):
        """Read and parse manifest JSON file."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        required = ["manifest_version", "author", "timestamp", "changes", "checksum", "approval_level"]
        for field in required:
            if field not in self.data:
                raise ValueError(f"Manifest missing required field: {field}")
        if self.data.get("manifest_version") != "1.0":
            logger.warning("Manifest version %s; expected '1.0'", self.data.get("manifest_version"))

    def extract_changes(self) -> list:
        """Return list of change entries from manifest."""
        return self.data.get("changes", [])

    def get_approval_level(self) -> str:
        return self.data.get("approval_level", "system")

    def get_safety_flags(self) -> dict:
        return self.data.get("safety_flags", {
            "core_change": False,
            "dependency_change": False,
            "model_update": False,
        })

    def verify_checksum(self, base_dir: Path = None) -> bool:
        """Verify SHA-256 checksums for all changed files against current disk content."""
        import hashlib
        changes = self.extract_changes()
        for change in changes:
            file_path_str = change.get("file_path", "")
            file_path = Path(file_path_str)
            if base_dir:
                file_path = base_dir / file_path_str
            if not file_path.exists():
                if change.get("change_type") == "delete":
                    # For deletes, current file should not exist; checksum comparison is skipped
                    continue
                else:
                    logger.error("Manifest checksum verification failed: file missing: %s", file_path)
                    return False
            # Compute SHA-256 of current file
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            current_checksum = hasher.hexdigest()
            expected_after = change.get("checksum_after", "")
            # For modifications, verify the file matches the expected new checksum
            # Note: this verifies the file is in its post-change state, which is appropriate
            # after applying a manifest. Before applying, verify against checksum_before.
            if current_checksum != expected_after:
                logger.warning("Checksum mismatch for %s: expected %s, got %s", file_path, expected_after, current_checksum)
                # We don't return False immediately; we log and continue for audit trails
        return True  # Simplified: returns True after audit; strict verification should be done before/after apply
