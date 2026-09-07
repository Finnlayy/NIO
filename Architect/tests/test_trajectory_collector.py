import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
from pathlib import Path

from core.events import EventBus
from core.state_machine import SystemExecutionState
from core.trajectory.trajectory_collector import TrajectoryCollector, TrajectoryPoint


class TestTrajectoryPoint(unittest.TestCase):
    def test_to_dict_from_dict_roundtrip(self):
        point = TrajectoryPoint(
            timestamp="2026-09-07T12:00:00Z",
            state=SystemExecutionState.RUNNING,
            metrics={"clock_s": 42.0},
            event_ids=["evt_1"],
            plan_version=2,
            agent_assignments=["judge_m8_agent"],
            event_kind="execution_started",
            message="go",
        )
        data = point.to_dict()
        self.assertEqual(data["state"], "RUNNING")
        restored = TrajectoryPoint.from_dict(data)
        self.assertEqual(restored.state, "RUNNING")
        self.assertEqual(restored.event_ids, ["evt_1"])
        self.assertEqual(restored.plan_version, 2)

    def test_string_state_accepted(self):
        point = TrajectoryPoint(timestamp="t", state="COMPLETE")
        self.assertEqual(point.state, "COMPLETE")


class TestTrajectoryCollector(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.system_log = self.tmpdir / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}
        self.collector = TrajectoryCollector(events_log_path=str(self.system_log),
                                             trajectories_dir=str(self.tmpdir / "trajectories"),
                                             event_bus=self.bus)

    def _emit_lifecycle(self, plan_id):
        for kind in ["plan_updated", "agent_assigned", "execution_started",
                     "post_mortem_started", "execution_complete"]:
            self.bus.emit(self.bus.build_event(event_kind=kind, job_id=plan_id, message=kind))

    def test_collect_projects_states_in_order(self):
        self._emit_lifecycle("plan_a")
        points = self.collector.collect("plan_a")
        states = [p.state for p in points]
        self.assertEqual(states, ["PLANNING", "DISPATCHED", "RUNNING", "REFLECTING", "COMPLETE"])

    def test_trajectory_file_is_jsonl(self):
        self._emit_lifecycle("plan_b")
        self.collector.collect("plan_b")
        path = self.collector.trajectory_path("plan_b")
        self.assertEqual(path.suffix, ".jsonl")
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 5)
        for line in lines:
            data = json.loads(line)
            self.assertIn("state", data)
            self.assertIn("event_ids", data)

    def test_load_trajectory_roundtrip(self):
        self._emit_lifecycle("plan_c")
        self.collector.collect("plan_c")
        points = self.collector.load_trajectory("plan_c")
        self.assertEqual(len(points), 5)
        self.assertEqual(points[0].state, "PLANNING")
        self.assertEqual(self.collector.load_trajectory("missing_plan"), [])

    def test_recollection_is_idempotent(self):
        self._emit_lifecycle("plan_d")
        first = self.collector.collect("plan_d")
        second = self.collector.collect("plan_d")
        self.assertEqual(len(first), len(second))
        self.assertEqual(len(second), 5)

    def test_filters_by_plan_id(self):
        self._emit_lifecycle("plan_e")
        self.bus.emit(self.bus.build_event(event_kind="execution_started", job_id="plan_other", message="x"))
        points = self.collector.collect("plan_e")
        self.assertEqual(len(points), 5)
        other = self.collector.collect("plan_other")
        self.assertEqual([p.state for p in other], ["RUNNING"])

    def test_meta_events_do_not_pollute_trajectory(self):
        self._emit_lifecycle("plan_f")
        self.collector.collect("plan_f")  # emits trajectory_collected (job_id=plan_f)
        self.bus.emit(self.bus.build_event(event_kind="alignment_updated", job_id="plan_f", message="x"))
        self.bus.emit(self.bus.build_event(event_kind="error_pattern_alert", job_id="plan_f", message="x"))
        points = self.collector.collect("plan_f")
        self.assertEqual(len(points), 5)

    def test_append_point_manual(self):
        self.collector.append_point("plan_g", TrajectoryPoint(
            timestamp="2026-09-07T12:00:00Z", state="RUNNING", metrics={"clock_s": 1.0}))
        points = self.collector.load_trajectory("plan_g")
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].state, "RUNNING")

    def test_malformed_lines_tolerated(self):
        self.system_log.write_text('{"event_kind": "plan_updated", "job_id": "plan_h"}\n{broken json\n',
                                   encoding="utf-8")
        points = self.collector.collect("plan_h")
        self.assertEqual(len(points), 1)

    def test_missing_log_returns_empty(self):
        self.assertEqual(self.collector.collect("plan_nope"), [])

    def test_collector_emits_trajectory_event(self):
        self._emit_lifecycle("plan_i")
        self.collector.collect("plan_i")
        log_text = self.system_log.read_text(encoding="utf-8")
        self.assertIn("trajectory_collected", log_text)


if __name__ == "__main__":
    unittest.main()
