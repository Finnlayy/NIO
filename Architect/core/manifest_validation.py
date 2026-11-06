import logging
from pathlib import Path, PurePosixPath

from core.manifest import Manifest

logger = logging.getLogger(__name__)

# Policy globs for sandbox/path resolution (divergence preserved: external services allowed)
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
HUMAN_ONLY_GLOBS = [
    "Architect/core/config.py",
    "Architect/core/protocol.py",
    "Architect/core/state_machine.py",
    "Architect/core/daemon_supervisor.py",
    "Architect/limbs/bootstrap_limb.py",
]

def _matches_glob(file_path_str: str, globs: list) -> bool:
    """Simple glob matcher for allowed/denied paths."""
    import fnmatch
    return any(fnmatch.fnmatch(file_path_str, pattern) or fnmatch.fnmatch(Path(file_path_str).name, pattern) for pattern in globs)

def _is_plain_relative(file_path_str: str) -> bool:
    """True for a non-empty relative POSIX path without "..", backslashes or NUL."""
    if not file_path_str or "\\" in file_path_str or "\0" in file_path_str:
        return False
    path = PurePosixPath(file_path_str)
    # Canonical only: "a/./b", "a//b" and "a/" would dodge the human-only globs.
    return not path.is_absolute() and ".." not in path.parts and str(path) == file_path_str

def validate_manifest_update(manifest_path: str, current_state_path: str | None = None) -> tuple:
    """Validate a manifest update before applying. Returns (bool, str)."""
    try:
        manifest = Manifest(manifest_path)
    except Exception as exc:
        return (False, f"Manifest parse error: {exc}")

    approval_level = manifest.get_approval_level()
    changes = manifest.extract_changes()
    flags = manifest.get_safety_flags()

    # Safety checks
    if flags.get("core_change", False) and approval_level != "human":
        return (False, "Core change requires approval_level='human'; got 'system'.")

    # Dependency change validation (simplified: no downgrade allowed)
    # In a full implementation, compare dependency versions with current state.
    # For Phase 3, we enforce that dependency_change must be explicitly approved.
    if flags.get("dependency_change", False) and approval_level != "human":
        return (False, "Dependency change requires approval_level='human'.")

    # Check file paths against allowed/denied globs
    for change in changes:
        file_path_str = change.get("file_path", "")
        # Denied globs check (before allowed)
        if _matches_glob(file_path_str, DENIED_GLOBS):
            return (False, f"File path denied by policy: {file_path_str}")
        # fnmatch's "*" also matches "/" and "..", so the globs alone let
        # "Architect/core/../../x" through. Only plain relative paths are allowed.
        if not _is_plain_relative(file_path_str):
            return (False, f"File path must be relative without '..': {file_path_str}")
        # Allowed repo globs check
        if not _matches_glob(file_path_str, ALLOWED_REPO_GLOBS):
            return (False, f"File path not allowed by repo globs: {file_path_str}")
        # Human-only files follow from the path, not from the caller's safety_flags.
        if _matches_glob(file_path_str, HUMAN_ONLY_GLOBS) and approval_level != "human":
            return (False, f"File requires approval_level='human': {file_path_str}")

    # Checksum verification: verify files exist for create/modify (before applying)
    for change in changes:
        file_path_str = change.get("file_path", "")
        change_type = change.get("change_type", "modify")
        file_path = Path(file_path_str)
        # For creates and modifies, ensure the file path is within allowed scope (already checked)
        if change_type == "delete":
            if not file_path.exists():
                # Deleting a non-existent file is a no-op; valid but note
                logger.info("Delete target does not exist (no-op): %s", file_path_str)
        else:
            # For create/modify: before applying, verify checksum_before matches current file (if file exists)
            # This ensures the manifest is based on the actual current state.
            if file_path.exists():
                import hashlib
                hasher = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        hasher.update(chunk)
                current_checksum = hasher.hexdigest()
                expected_before = change.get("checksum_before", "")
                if expected_before and current_checksum != expected_before:
                    return (False, f"Checksum mismatch for {file_path_str}: expected {expected_before}, found {current_checksum}. Manifest may be stale.")
            else:
                # For creates, file should not exist yet; checksum_before should be empty or null
                expected_before = change.get("checksum_before", "")
                if expected_before:
                    return (False, f"Create target already exists or checksum_before set incorrectly: {file_path_str}")

    return (True, "Manifest validated: safe to apply.")
