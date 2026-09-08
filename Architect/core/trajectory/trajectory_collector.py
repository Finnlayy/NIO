"""Trajectory collector (Phase 5 — Self-Model & Insights).

Reads the event-bus NDJSON stream (`Architect/runtime/system.log`), filters
events for a plan, and projects them onto `TrajectoryPoint`s persisted as
line-delimited JSON (`Architect/runtime/trajectories/<plan_id>.jsonl`) for
incremental appends.

Data flow (OMEGA_JULES_TODO.md Phase 5):  event bus -> trajectory collector
-> visualizer / alignment tracker.
"""

import json
import hashlib
import logging
import datetime
from pathlib import Path

from core.state_machine import SystemExecutionState

logger = logging.getLogger(__name__)

# event_kind -> SystemExecutionState projection
KIND_TO_STATE = {
    "plan_updated": SystemExecutionState.PLANNING,
    "agent_assigned": SystemExecutionState.DISPATCHED,
    "execution_started": SystemExecutionState.RUNNING,
    "manifest_validated": SystemExecutionState.RUNNING,
    "manifest_applied": SystemExecutionState.RUNNING,
    "self_modification_complete": SystemExecutionState.RUNNING,
    "post_mortem_started": SystemExecutionState.REFLECTING,
    "reflection_complete": SystemExecutionState.REFLECTING,
    "execution_complete": SystemExecutionState.COMPLETE,
    "self_modification_failed": SystemExecutionState.REFLECTING,
    "manifest_rolled_back": SystemExecutionState.REFLECTING,
    "post_mortem_complete": SystemExecutionState.COMPLETE,
    "agent_complete": SystemExecutionState.COMPLETE,
}


class TrajectoryPoint:
    """One step of a plan's execution trajectory."""

    def __init__(self, timestamp: str, state, metrics: dict = None,
                 event_ids: list = None, plan_version: int = 1, agent_assignments: list = None,
                 event_kind: str = None, message: str = ""):
        self.timestamp = timestamp
        # Accept SystemExecutionState or a plain string.
        if isinstance(state, SystemExecutionState):
            state = state.name
        self.state = state
        self.metrics = metrics or {}
        self.event_ids = event_ids or []
        self.plan_version = plan_version
        self.agent_assignments = agent_assignments or []
        self.event_kind = event_kind
        self.message = message

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "state": self.state,
            "metrics": self.metrics,
            "event_ids": self.event_ids,
            "plan_version": self.plan_version,
            "agent_assignments": self.agent_assignments,
            "event_kind": self.event_kind,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrajectoryPoint":
        return cls(
            timestamp=data.get("timestamp", ""),
            state=data.get("state", "PLANNING"),
            metrics=data.get("metrics") or {},
            event_ids=data.get("event_ids") or [],
            plan_version=int(data.get("plan_version", 1)),
            agent_assignments=data.get("agent_assignments") or [],
            event_kind=data.get("event_kind"),
            message=data.get("message", ""),
        )


class TrajectoryCollector:
    """Collect plan trajectories from the event stream into `.jsonl` files."""

    def __init__(self, events_log_path: str = "Architect/runtime/system.log",
                 trajectories_dir: str = "Architect/runtime/trajectories", event_bus=None):
        self.events_log_path = Path(events_log_path)
        self.trajectories_dir = Path(trajectories_dir)
        self.trajectories_dir.mkdir(parents=True, exist_ok=True)
        self.event_bus = event_bus

    # ---- Event stream ---------------------------------------------------------

    def _read_event_lines(self, source_path=None) -> list:
        """Parse the NDJSON event stream into (line_hash, event) pairs.

        Line hashes are the collection identity: bus event_ids have
        second-granularity timestamps and can collide for same-second events.
        """
        path = Path(source_path) if source_path else self.events_log_path
        if not path.exists():
            return []
        pairs = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed event line in %s", path)
                    continue
                line_hash = "ln_" + hashlib.sha1(line.encode("utf-8")).hexdigest()[:16]
                pairs.append((line_hash, event))
        return pairs

    def _read_events(self, source_path=None) -> list:
        """Parse the NDJSON event stream; tolerates torn/partial lines."""
        return [event for _hash, event in self._read_event_lines(source_path)]

    @staticmethod
    def _matches_plan(event: dict, plan_id: str) -> bool:
        return (event.get("plan_id") == plan_id
                or event.get("job_id") == plan_id
                or event.get("intent_id") == plan_id)

    def _event_to_point(self, event: dict, plan_version: int = 1) -> TrajectoryPoint:
        kind = event.get("event_kind", "")
        state = KIND_TO_STATE.get(kind, SystemExecutionState.PLANNING)
        metrics = {
            "clock_s": event.get("clock_s"),
        }
        return TrajectoryPoint(
            timestamp=event.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z"),
            state=state,
            metrics=metrics,
            event_ids=[event.get("event_id")] if event.get("event_id") else [],
            plan_version=plan_version,
            agent_assignments=[event.get("limb")] if event.get("limb") else [],
            event_kind=kind,
            message=event.get("message", ""),
        )

    # ---- Collection -------------------------------------------------------------

    def collect(self, plan_id: str, source_path=None, plan_version: int = 1) -> list:
        """Collect trajectory points for `plan_id` from the event stream.

        Appends new points (deduplicated by source-line hash so re-collection
        is idempotent) to `trajectories/<plan_id>.jsonl` and emits a
        `trajectory_collected` event.
        """
        existing_hashes = {pid for point in self.load_trajectory(plan_id) for pid in point.event_ids if pid.startswith("ln_")}
        new_points = []
        for line_hash, event in self._read_event_lines(source_path):
            # Only project execution-lifecycle events; meta events (e.g. this
            # collector's own `trajectory_collected` emission) must not feed
            # back into the trajectory.
            if event.get("event_kind") not in KIND_TO_STATE:
                continue
            if not self._matches_plan(event, plan_id):
                continue
            if line_hash in existing_hashes:
                continue
            point = self._event_to_point(event, plan_version=plan_version)
            # First event id = stable line identity (dedupe), bus event_id kept for correlation.
            point.event_ids = [line_hash] + ([event.get("event_id")] if event.get("event_id") else [])
            existing_hashes.add(line_hash)
            new_points.append(point)

        if new_points:
            trajectory_path = self.trajectory_path(plan_id)
            with open(trajectory_path, "a", encoding="utf-8") as f:
                for point in new_points:
                    f.write(json.dumps(point.to_dict(), separators=(",", ":")) + "\n")
            if self.event_bus:
                self.event_bus.emit(self.event_bus.build_event(
                    event_kind="trajectory_collected",
                    job_id=plan_id,
                    message=f"Collected {len(new_points)} trajectory points for {plan_id}.",
                    plan_id=plan_id,
                    points_added=len(new_points),
                ))
        logger.info("Trajectory collected for %s: %d new point(s).", plan_id, len(new_points))
        return self.load_trajectory(plan_id)

    def append_point(self, plan_id: str, point: TrajectoryPoint):
        """Manually append a trajectory point (used by tests and instrumentation)."""
        trajectory_path = self.trajectory_path(plan_id)
        with open(trajectory_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(point.to_dict(), separators=(",", ":")) + "\n")

    def trajectory_path(self, plan_id: str) -> Path:
        return self.trajectories_dir / f"{plan_id}.jsonl"

    def load_trajectory(self, plan_id: str) -> list:
        """Load trajectory points for a plan (empty list if none)."""
        path = self.trajectory_path(plan_id)
        if not path.exists():
            return []
        points = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    points.append(TrajectoryPoint.from_dict(json.loads(line)))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed trajectory line for %s", plan_id)
        return points
