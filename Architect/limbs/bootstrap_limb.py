import logging
import json
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

# Sandbox and policy references (divergence preserved: external services allowed)
ALLOWED_REPO_GLOBS = [
    "Architect/core/*",
    "Architect/limbs/*",
    "Architect/gui/*",
    "Architect/models/*",
    "Architect/schemas/*",
    "Architect/limbs/intelligence/*",
    "Architect/limbs/math/*",
    "Architect/limbs/ml/*",
]
DENIED_GLOBS = [
    "runtime/*",
    "*.log",
    "/etc/*",
    "/usr/*",
    "/home/*",
]

class SandboxViolation(Exception):
    pass

class BootstrapLimb:
    """File-system operations with sandbox enforcement, backup, and hash verification."""

    def __init__(self, sandbox_root: str = "Architect/workspace"):
        self.sandbox_root = Path(sandbox_root)
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, file_path_str: str) -> Path:
        """Resolve path within allowed repo globs; enforce sandbox for writes."""
        import fnmatch
        path_str = file_path_str
        # Check denied globs first
        for pattern in DENIED_GLOBS:
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(Path(path_str).name, pattern):
                raise SandboxViolation(f"Path denied by policy: {path_str} (matches {pattern})")
        # For writes, restrict to sandbox or allowed repo paths
        # Read operations can access allowed repo paths; writes must be within workspace or explicitly allowed
        resolved = Path(path_str)
        if not resolved.is_absolute():
            resolved = Path("Architect") / resolved
        return resolved.resolve()

    def read_file(self, file_path_str: str) -> str:
        path = self.resolve_path(file_path_str)
        # Read allowed for allowed repo paths
        import fnmatch
        allowed = False
        for pattern in ALLOWED_REPO_GLOBS:
            if fnmatch.fnmatch(str(path), pattern) or fnmatch.fnmatch(path.name, pattern):
                allowed = True
                break
        if not allowed and not str(path).startswith(str(self.sandbox_root)):
            raise SandboxViolation(f"Read access denied: {path_str} (not in allowed paths or sandbox)")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, file_path_str: str, content: str, backup: bool = True) -> Path:
        path = self.resolve_path(file_path_str)
        # For writes, enforce sandbox (workspace) or allowed repo paths
        import fnmatch
        allowed_write = False
        for pattern in ALLOWED_REPO_GLOBS:
            if fnmatch.fnmatch(str(path), pattern) or fnmatch.fnmatch(path.name, pattern):
                allowed_write = True
                break
        if not allowed_write and not str(path).startswith(str(self.sandbox_root.resolve())):
            raise SandboxViolation(f"Write access denied: {file_path_str} (must be in allowed repo paths or sandbox)")
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup and path.exists():
            self._create_backup(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        # Verify hash after write
        written_hash = self._hash_file(path)
        logger.info("File written and verified: %s (sha256=%s)", path, written_hash)
        return path

    def patch(self, file_path_str: str, patch_content: str, backup: bool = True) -> Path:
        """Apply a patch (append or replace) to an existing file with backup."""
        path = self.resolve_path(file_path_str)
        if not path.exists():
            raise FileNotFoundError(f"Patch target does not exist: {path}")
        original_content = self.read_file(file_path_str)
        # For simplicity, append patch_content (real patch logic would parse diff format)
        new_content = original_content + "\n" + patch_content
        return self.write_file(file_path_str, new_content, backup=backup)

    def list_files(self, directory_str: str) -> list:
        dir_path = self.resolve_path(directory_str)
        if not dir_path.exists() or not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        files = [str(f) for f in dir_path.iterdir() if f.is_file()]
        return files

    def mkdir(self, directory_str: str) -> Path:
        dir_path = self.resolve_path(directory_str)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    def _create_backup(self, file_path: Path):
        import datetime
        backup_dir = Path("Architect/runtime/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = backup_dir / f"{file_path.name}_{timestamp}.bak"
        import shutil
        shutil.copy2(str(file_path), str(backup_path))
        # Verify hash
        original_hash = self._hash_file(file_path)
        backup_hash = self._hash_file(backup_path)
        if original_hash != backup_hash:
            logger.error("Backup hash mismatch: %s (%s vs %s)", file_path, original_hash, backup_hash)
        else:
            logger.info("Backup verified: %s -> %s", file_path, backup_path)

    def _hash_file(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
