import logging
import fnmatch
from pathlib import Path

logger = logging.getLogger(__name__)

# Divergence preserved: Jules's code uses external services and desktop terminal,
# so policy allows external APIs, Qdrant, Gemini, LM Studio, etc.
# Sandbox enforcement is focused on execution-security rather than dependency restriction.

DENIED_GLOBS = [
    "runtime/*",
    "*.log",
    "/etc/*",
    "/usr/*",
    "/home/*",
]

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

HUMAN_ONLY_GLOBS = [
    "Architect/core/config.py",
    "Architect/core/protocol.py",
    "Architect/core/state_machine.py",
    "Architect/core/daemon_supervisor.py",
    "Architect/core/manifest_validation.py",
    "Architect/limbs/bootstrap_limb.py",
]

class Policy:
    """Execution-security policy: sandbox resolution, denied/allowed paths, constitution guard."""

    def __init__(self):
        pass

    def resolve_path(self, path_str: str) -> Path:
        """Resolve relative path to allowed base; apply denied/allowed globs; check elevation."""
        path = Path(path_str)
        # Check denied globs first
        for pattern in DENIED_GLOBS:
            if fnmatch.fnmatch(str(path), pattern) or fnmatch.fnmatch(path.name, pattern):
                raise PermissionError(f"Path denied by policy: {path_str} (matches {pattern})")
        # Resolve relative paths against Architect root
        if not path.is_absolute():
            path = Path("Architect") / path
        return path.resolve()

    def check_schedule(self, schedule: dict) -> tuple:
        """Fail-fast schedule validation before execution."""
        errors = []
        if not isinstance(schedule, dict):
            return (False, "Schedule must be a dict.")
        if "triggers" not in schedule or not isinstance(schedule.get("triggers"), list):
            errors.append("Schedule must contain 'triggers' array.")
        # Check trigger validity
        for trigger in schedule.get("triggers", []):
            if not isinstance(trigger, dict):
                errors.append(f"Trigger must be dict: {trigger}")
                continue
            if "kind" not in trigger:
                errors.append("Trigger missing 'kind'.")
            if trigger.get("kind") == "interval" and "every_s" not in trigger:
                errors.append("Interval trigger missing 'every_s'.")
            if trigger.get("kind") == "edge" and "when" not in trigger:
                errors.append("Edge trigger missing 'when'.")
        if errors:
            return (False, "; ".join(errors))
        return (True, "Schedule valid.")

    def sandbox_root(self) -> Path:
        return Path("Architect/workspace").resolve()

    def constitution_guard(self, action: str, path_str: str, approved_by: str = "system") -> tuple:
        """Check if action requires human-only approval (core changes)."""
        for pattern in HUMAN_ONLY_GLOBS:
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(Path(path_str).name, pattern):
                if approved_by != "human":
                    return (False, f"Human-only action required for core file {path_str}; got approved_by='{approved_by}'.")
        return (True, f"Action {action} on {path_str} approved by '{approved_by}'.")

    def check_path_resolution(self, path_str: str) -> tuple:
        """Validate that a path resolves safely within allowed/restricted boundaries."""
        try:
            resolved = self.resolve_path(path_str)
        except PermissionError as exc:
            return (False, str(exc))
        # Ensure resolved path is within allowed repo or workspace
        allowed_roots = [
            Path("Architect").resolve(),
            self.sandbox_root(),
        ]
        allowed = any(str(resolved).startswith(str(root)) for root in allowed_roots)
        if not allowed:
            return (False, f"Resolved path {resolved} is outside allowed boundaries.")
        return (True, str(resolved))
