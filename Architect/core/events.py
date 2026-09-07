import logging
import json
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_EVENT_KINDS = [
    "execution_started",
    "execution_complete",
    "post_mortem_started",
    "post_mortem_complete",
    "manifest_validated",
    "manifest_applied",
    "manifest_rolled_back",
    "self_modification_complete",
    "self_modification_failed",
    "reflection_complete",
    "plan_updated",
    "agent_assigned",
    "agent_complete",
    "error_pattern_alert",
    "feedback_submitted",
    "model_updated",
    "model_validation_failed",
    "trajectory_collected",
    "alignment_updated",
    "review_due",
    "risk_guard_failed",
    "risk_guard_warning",
]

class EventBus:
    """NDJSON event emission: stderr, file sink (runtime/system.log), optional UDS/shared-memory."""

    def __init__(self, system_log_path: str = "Architect/runtime/system.log"):
        self.system_log_path = Path(system_log_path)
        self.system_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.event_sinks = {"stderr": True, "file": True}
        # Phase 3: optional advanced sinks (UDS, shared-memory ring) not fully implemented
        # Divergence preserved: events are NDJSON-based, matching blueprint spec (§6)
        # but transport uses file + stderr rather than shared-memory ring (to align with Jules's architecture)

    def emit(self, event_dict: dict):
        """Validate and emit an event to all active sinks."""
        event_kind = event_dict.get("event_kind", "")
        if event_kind not in VALID_EVENT_KINDS:
            logger.error("Event kind '%s' not in VALID_EVENT_KINDS whitelist; event rejected.", event_kind)
            return False

        # Enrich with timestamp and clock_s if missing
        if "timestamp" not in event_dict:
            event_dict["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        if "clock_s" not in event_dict:
            event_dict["clock_s"] = None  # Will be bound by orchestrator/job clock

        # Serialize to compact NDJSON (machine format, matching blueprint optimization)
        event_line = json.dumps(event_dict, separators=(",", ":"))

        # Sink 1: stderr (NDJSON stream)
        if self.event_sinks.get("stderr", False):
            import sys
            sys.stderr.write(event_line + "\n")
            sys.stderr.flush()

        # Sink 2: file sink (Phase 3: runtime/system.log)
        if self.event_sinks.get("file", False):
            try:
                with open(self.system_log_path, "a", encoding="utf-8") as f:
                    f.write(event_line + "\n")
            except Exception as exc:
                logger.error("Failed to write event to %s: %s", self.system_log_path, exc)

        logger.info("Event emitted: %s (kind=%s, job_id=%s)", event_dict.get("event_id"), event_kind, event_dict.get("job_id"))
        return True

    def build_event(self, event_kind: str, job_id: str = None, intent_id: str = None,
                    trace_id: str = None, limb: str = None, clock_s: float = None,
                    message: str = "", **extra) -> dict:
        """Build a validated event dictionary."""
        event_dict = {
            "event_id": f"evt_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{job_id or 'system'}",
            "event_kind": event_kind,
            "job_id": job_id,
            "intent_id": intent_id,
            "trace_id": trace_id,
            "limb": limb,
            "clock_s": clock_s,
            "message": message,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }
        event_dict.update(extra)
        return event_dict
