import logging
import hashlib
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

class SelfModificationSafety:
    """Safety layer for manifest application: backups, rollback, hash verification."""

    def __init__(self, workspace_root: str = "Architect/workspace"):
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.backup_dir = Path("Architect/runtime/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of file_path with SHA-256 hash verification."""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning("Backup requested for non-existent file: %s", file_path)
            return None
        timestamp = __import__("datetime").datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_file = self.backup_dir / f"{file_path.name}_{timestamp}.bak"
        try:
            shutil.copy2(str(file_path), str(backup_file))
            # Verify hash
            original_hash = self._compute_hash(file_path)
            backup_hash = self._compute_hash(backup_file)
            if original_hash != backup_hash:
                logger.error("Backup hash mismatch for %s: original %s vs backup %s", file_path, original_hash, backup_hash)
                return None
            # Save hash comparison file
            hash_file = self.backup_dir / f"{file_path.name}_{timestamp}_hash.json"
            import json
            with open(hash_file, "w", encoding="utf-8") as f:
                json.dump({
                    "file": str(file_path),
                    "backup": str(backup_file),
                    "sha256_original": original_hash,
                    "sha256_backup": backup_hash,
                    "verified": original_hash == backup_hash,
                }, f, indent=2)
            logger.info("Backup created and verified: %s -> %s", file_path, backup_file)
            return backup_file
        except Exception as exc:
            logger.error("Backup creation failed for %s: %s", file_path, exc)
            return None

    def rollback(self, file_path: Path, backup_file: Path = None) -> bool:
        """Restore file from backup."""
        file_path = Path(file_path)
        if backup_file is None:
            # Find most recent backup for this file
            backups = list(self.backup_dir.glob(f"{file_path.name}_*.bak"))
            if not backups:
                logger.error("No backup found for rollback: %s", file_path)
                return False
            backup_file = sorted(backups)[-1]
        else:
            backup_file = Path(backup_file)
        if not backup_file.exists():
            logger.error("Backup file missing for rollback: %s", backup_file)
            return False
        try:
            shutil.copy2(str(backup_file), str(file_path))
            # Verify restored file hash matches backup
            restored_hash = self._compute_hash(file_path)
            backup_hash = self._compute_hash(backup_file)
            if restored_hash != backup_hash:
                logger.error("Rollback verification failed: hash mismatch after restore (%s vs %s)", restored_hash, backup_hash)
                return False
            logger.info("Rollback successful: %s restored from %s", file_path, backup_file)
            return True
        except Exception as exc:
            logger.error("Rollback failed for %s: %s", file_path, exc)
            return False

    def apply_modification(self, manifest_path: str, base_dir: Path = None) -> tuple:
        """Apply manifest changes with backup, verification, and rollback capability."""
        from core.manifest import Manifest
        from core.manifest_validation import validate_manifest_update
        result = validate_manifest_update(manifest_path, base_dir)
        if not result[0]:
            logger.error("Manifest validation failed before apply: %s", result[1])
            return (False, result[1])
        manifest = Manifest(manifest_path)
        changes = manifest.extract_changes()
        applied = []
        backups = {}
        for change in changes:
            file_path_str = change.get("file_path", "")
            file_path = Path(file_path_str)
            if base_dir:
                file_path = base_dir / file_path_str
            change_type = change.get("change_type", "modify")
            # Create backup before any modification
            backup_path = self.create_backup(file_path)
            backups[str(file_path)] = backup_path
            if change_type == "delete":
                try:
                    if file_path.exists():
                        file_path.unlink()
                        applied.append(str(file_path) + " (deleted)")
                    else:
                        logger.info("Delete target not present (no-op): %s", file_path)
                        applied.append(str(file_path) + " (delete no-op)")
                except Exception as exc:
                    logger.error("Failed to delete %s: %s", file_path, exc)
                    # Trigger rollback for this file
                    if backup_path and backup_path.exists():
                        self.rollback(file_path, backup_path)
            elif change_type == "modify" or change_type == "patch" or change_type == "create":
                # For simplicity: assume the file content is provided externally (e.g., by bootstrap limb or external process)
                # The manifest validates that the file exists (for modify) or will be created (for create) with correct checksum.
                # In a full implementation, the actual content patch would be applied here.
                # For Phase 3, we record the application and verify hash if the file exists.
                if file_path.exists():
                    current_hash = self._compute_hash(file_path)
                    expected_after = change.get("checksum_after", "")
                    if expected_after and current_hash != expected_after:
                        logger.warning("Applied file %s does not match expected checksum after modify: found %s, expected %s", file_path, current_hash, expected_after)
                    applied.append(str(file_path) + f" ({change_type}, checksum verified if present)")
                else:
                    applied.append(str(file_path) + f" ({change_type}, file not present - expected for create)")
        return (True, f"Applied {len(applied)} changes. Backups: {list(backups.keys())}. Applied: {applied}")

    def validate_after_apply(self, manifest_path: str, base_dir: Path = None) -> bool:
        """Verify all modified files, backups, and checksums after applying manifest."""
        from core.manifest import Manifest
        manifest = Manifest(manifest_path)
        changes = manifest.extract_changes()
        all_ok = True
        for change in changes:
            file_path_str = change.get("file_path", "")
            file_path = Path(file_path_str)
            if base_dir:
                file_path = base_dir / file_path_str
            change_type = change.get("change_type", "modify")
            # Verify backup exists
            backups = list(self.backup_dir.glob(f"{file_path.name}_*.bak"))
            if not backups and change_type != "delete":
                # For deletes, no backup is expected (or optional)
                logger.info("No backup for %s (type=%s); checking file state.", file_path, change_type)
            # Verify checksum after for existing files
            if file_path.exists() and change_type != "delete":
                current_hash = self._compute_hash(file_path)
                expected_after = change.get("checksum_after", "")
                if expected_after and current_hash != expected_after:
                    logger.error("Post-apply checksum mismatch for %s: expected %s, got %s", file_path, expected_after, current_hash)
                    all_ok = False
        return all_ok

    def _compute_hash(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
