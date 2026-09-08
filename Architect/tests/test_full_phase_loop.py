"""Integration test: the full 5-phase OMEGA loop in a sandbox.

    Phase 2  plan -> agent assignment -> state machine dispatch -> execution
    Phase 2b post-mortem + DSR reflection on failure -> baseline comparison
    Phase 3  manifest validation of a benign self-modification + event bus
    Phase 4  outcome ingestion -> feedback -> skill profiles -> error patterns
             -> knowledge base -> defineEval -> preference model update
    Phase 5  trajectory collection -> alignment metrics -> self-model insights

Runs fully offline (stub AI supply) inside a tempdir.
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile
import json
import hashlib
from pathlib import Path

from core.events import EventBus
from core.state_machine import SystemExecutionState, TRANSITION_MAP
from core.agent_assignment import AgentAssignment
from core.post_mortem_trigger import PostMortemTrigger
from core.manifest_validation import validate_manifest_update
from core.outcome_parser import OutcomeIngestion
from core.feedback_processor import FeedbackProcessor
from core.learning.skill_profiles import SkillProfileUpdater
from core.learning.error_patterns import ErrorPatternDetector, ErrorPatternStorage
from core.learning.knowledge_base import KnowledgeBase, KnowledgeEntryParser
from core.learning.preference_model_updater import PreferenceModelUpdater
from core.evaluation.define_eval import define_eval, EvalPipeline
from core.evaluation.evaluators import correctness_evaluator
from core.trajectory.trajectory_collector import TrajectoryCollector
from core.alignment.alignment_tracker import AlignmentTracker
from core.alignment.alignment_dashboard import AlignmentDashboard
from core.self_model.self_model_engine import SelfModelEngine
from limbs.intelligence.memory_planner import MemoryPlanner
from limbs.intelligence.genai_client import GenAIClient

REPO_ROOT = Path(__file__).resolve().parents[2]
RLHF_DATASET = str(REPO_ROOT / "evals" / "datasets" / "rlhf_samples.json")


class MockConfig:
    GEMINI_API_KEY = ""
    GEMINI_MODEL_FAST = "gemini-2.5-flash"
    GEMINI_MODEL_DEEP = "gemini-2.5-pro"
    LM_STUDIO_ENABLED = False
    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
    LM_STUDIO_MODEL = "local-model"
    LM_STUDIO_API_KEY = "not-needed"
    LM_STUDIO_TIMEOUT = 30.0


class MockQdrantEngine:
    class _Client:
        def search(self, collection_name, query_vector, limit=5):
            class _Point:
                def __init__(self):
                    self.id = "m1"
                    self.score = 0.9
                    self.payload = {"memory": "prior similar plan succeeded"}
            return [_Point()]
    def __init__(self):
        self.client = MockQdrantEngine._Client()


class TestFullPhaseLoop(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.system_log = self.tmpdir / "system.log"
        self.bus = EventBus(system_log_path=str(self.system_log))
        self.bus.event_sinks = {"stderr": False, "file": True}

        self.planner = MemoryPlanner(MockQdrantEngine())
        self.planner.plans_dir = self.tmpdir / "plans"
        self.planner.plans_dir.mkdir(parents=True, exist_ok=True)

        self.config = MockConfig()
        self.genai = GenAIClient(self.config)
        self.genai.runtime_dir = self.tmpdir / "reflections"
        self.genai.runtime_dir.mkdir(parents=True, exist_ok=True)

        self.post_mortem = PostMortemTrigger(genai_client=self.genai)
        self.post_mortem.triggers_dir = self.tmpdir / "post_mortems"
        self.post_mortem.triggers_dir.mkdir(parents=True, exist_ok=True)

        self.ingestion = OutcomeIngestion(event_bus=self.bus, outcomes_dir=str(self.tmpdir / "outcomes"))
        self.feedback = FeedbackProcessor(feedback_dir=str(self.tmpdir / "feedback"),
                                          aggregates_dir=str(self.tmpdir / "aggregates"),
                                          event_bus=self.bus)
        self.skills = SkillProfileUpdater(skills_dir=str(self.tmpdir / "skills"), event_bus=self.bus)
        self.patterns = ErrorPatternDetector(event_bus=self.bus,
                                             storage=ErrorPatternStorage(str(self.tmpdir / "patterns")))
        self.kb = KnowledgeBase(kb_dir=str(self.tmpdir / "knowledge"))
        self.model_updater = PreferenceModelUpdater(models_dir=str(self.tmpdir / "models"), event_bus=self.bus)
        self.pipeline = EvalPipeline(evals_dir=str(self.tmpdir / "evals"))
        self.collector = TrajectoryCollector(events_log_path=str(self.system_log),
                                             trajectories_dir=str(self.tmpdir / "trajectories"),
                                             event_bus=self.bus)
        self.tracker = AlignmentTracker()
        self.alignment_service = AlignmentDashboard(alignment_dir=str(self.tmpdir / "alignment"),
                                                    event_bus=self.bus)
        self.self_model = SelfModelEngine(insights_dir=str(self.tmpdir / "insights"), event_bus=self.bus)

    def _emit(self, kind, job_id, message, **extra):
        return self.bus.emit(self.bus.build_event(event_kind=kind, job_id=job_id,
                                                  message=message, **extra))

    def _run_execution(self, plan_id, verdict, errors, metrics):
        """Simulate one execution + outcome ingestion (Phase 2/4 seam)."""
        self._emit("execution_started", plan_id, "execution started")
        outcome = self.ingestion.ingest({
            "job_id": plan_id,
            "intent_id": f"intent_{plan_id}",
            "limb": "microstructure_agent",
            "verdict": verdict,
            "errors": errors,
            "metrics": metrics,
            "elapsed_s": 5.0,
            "clock_s": 12.0,
            "timestamp": "2026-09-07T12:00:00Z",
        })
        return outcome

    def test_full_five_phase_loop(self):
        # ---------- Phase 2: planning, assignment, dispatch ----------
        plan = self.planner.create_plan("Execute microstructure scan and adapt", context_vectors=[[0.1] * 16])
        plan_id = plan["plan_id"]
        self._emit("plan_updated", plan_id, "plan created")

        assigned = AgentAssignment().assign_agents(plan)
        self.assertTrue(assigned.get("agent_assignments_mapped"))
        self._emit("agent_assigned", plan_id, "agents assigned")

        guard = TRANSITION_MAP[SystemExecutionState.PLANNING]["guard"]
        self.assertTrue(guard({"plan_approved": True,
                               "confidence_score": assigned["confidence_score"]}))

        # ---------- Phase 2b: failing execution -> post-mortem reflection ----------
        outcome_fail = self._run_execution(plan_id, "reject",
                                           ["E_SAFETY_NET: feed stale", "E_SAFETY_NET: feed stale"],
                                           {"success_rate": 0.2, "error_rate": 0.8})
        self.assertTrue(self.post_mortem.check_conditions(outcome_fail))
        pm_result = self.post_mortem.trigger({"job_id": plan_id, "execution_result": outcome_fail})
        self.assertIsNotNone(pm_result["analysis"])
        self._emit("post_mortem_started", plan_id, "post mortem started")

        # Reflection output -> knowledge base (Phase 4 learning memory).
        knowledge_entries = KnowledgeEntryParser.extract_from_reflection(pm_result["analysis"])
        for entry in knowledge_entries:
            self.kb.save(entry)
        self.assertGreaterEqual(len(self.kb.all()), 1)

        # Recovery execution succeeds.
        outcome_ok = self._run_execution(f"{plan_id}_r2", "accept", [], {"success_rate": 1.0})
        self._emit("execution_complete", f"{plan_id}_r2", "execution complete")

        # ---------- Phase 3: benign self-modification with manifest validation ----------
        target = self.tmpdir / "sandbox_target.py"
        target.write_text("# original\n", encoding="utf-8")
        new_content = "# original\n# adapted by OMEGA loop\n"
        manifest = {
            "manifest_version": "1.0",
            "author": "self_model_engine",
            "timestamp": "2026-09-07T12:00:00Z",
            "approval_level": "system",
            "safety_flags": {"core_change": False, "dependency_change": False, "model_update": False},
            "checksum": "na",
            "changes": [{
                "file_path": str(target),
                "change_type": "modify",
                "checksum_before": hashlib.sha256(b"# original\n").hexdigest(),
                "checksum_after": hashlib.sha256(new_content.encode("utf-8")).hexdigest(),
                "description": "Annotate adapted module",
            }],
        }
        manifest_path = self.tmpdir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        # The Phase 3 validator enforces repo globs; scope them to the sandbox
        # for this offline loop test (no repo files are touched).
        import core.manifest_validation as manifest_validation
        original_globs = list(manifest_validation.ALLOWED_REPO_GLOBS)
        manifest_validation.ALLOWED_REPO_GLOBS = original_globs + [str(self.tmpdir) + "/*"]
        try:
            passed, message = validate_manifest_update(str(manifest_path))
        finally:
            manifest_validation.ALLOWED_REPO_GLOBS = original_globs
        self.assertTrue(passed, message)
        target.write_text(new_content, encoding="utf-8")
        self._emit("manifest_validated", plan_id, "manifest validated")
        self._emit("self_modification_complete", plan_id, "self modification applied")

        # ---------- Phase 4: feedback + skill profiles + eval + preference model ----------
        feedback_records = [
            {"outcome_id": f"{plan_id}_r2", "rater_id": "human", "rating": 5,
             "preference": {"chosen": "A", "rejected": "B"},
             "comment": "recovered cleanly", "timestamp": "2026-09-07T12:05:00Z"},
            {"outcome_id": plan_id, "rater_id": "human", "rating": 2, "preference": None,
             "comment": "stale feed risk again", "timestamp": "2026-09-07T12:06:00Z"},
        ]
        for record in feedback_records:
            self.feedback.save_feedback(record)
        aggregates = [self.feedback.aggregate_for_outcome(f"{plan_id}_r2", feedback_records),
                      self.feedback.aggregate_for_outcome(plan_id, feedback_records)]
        for aggregate in aggregates:
            self.feedback.save_aggregate(aggregate["outcome_id"], aggregate)

        self.skills.record_outcome("skill_micro", False)   # failed run
        self.skills.record_outcome("skill_micro", True)    # recovery run
        patterns = self.patterns.detect_and_store(outcome_fail["errors"])
        self.assertEqual(patterns[0].error_type, "E_SAFETY_NET")
        # Threshold alert path: E_SAFETY_NET fired twice in a single plan.
        self.assertTrue(self.patterns.alert_if_threshold_exceeded(patterns[0], threshold=1))

        eval_config = define_eval("loop_correctness", {"correctness": 1.0}, RLHF_DATASET,
                                  correctness_evaluator, threshold=30.0)
        eval_result = self.pipeline.run(eval_config)
        self.assertTrue(eval_result["passed"])
        self.pipeline.save_result(eval_result)

        update_result = self.model_updater.update(RLHF_DATASET)
        validation = self.model_updater.validate(update_result["model_path"], RLHF_DATASET)
        self.assertTrue(validation["passed"])

        # ---------- Phase 5: trajectory -> alignment -> self-model insights ----------
        trajectory_points = self.collector.collect(plan_id)
        self.assertGreaterEqual(len(trajectory_points), 4)  # plan, assigned, started, complete (+ pm)

        risk_guards = [{"passed": True}, {"passed": True}, {"passed": False}]
        alignment = self.tracker.compute_all(
            [p.to_dict() for p in trajectory_points], aggregates, risk_guards,
            execution_results=[{"verdict": "accept", "errors": []}])
        self.alignment_service.save_metrics(plan_id, alignment)
        self.assertIn("alignment_score", alignment)

        insights = self.self_model.generate_insights(
            trajectory_points, alignment,
            skill_profiles=[p.to_dict() for p in self.skills.load_all()],
            error_patterns=[p.to_dict() for p in patterns],
            plan_id=plan_id)
        self.assertTrue(insights)
        self.self_model.save_insights(insights)

        # ---------- Global invariants ----------
        log_lines = [json.loads(line) for line in
                     self.system_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        kinds = {e["event_kind"] for e in log_lines}
        for expected in ("plan_updated", "agent_assigned", "execution_started", "execution_complete",
                         "post_mortem_started", "manifest_validated", "self_modification_complete",
                         "feedback_submitted", "model_updated", "trajectory_collected",
                         "alignment_updated", "error_pattern_alert"):
            self.assertIn(expected, kinds)

        # Trajectory stays idempotent.
        self.assertEqual(len(self.collector.collect(plan_id)), len(trajectory_points))

        # Artifacts landed in the expected places.
        self.assertTrue((self.tmpdir / "outcomes" / f"{plan_id}.json").exists())
        self.assertTrue((self.tmpdir / "aggregates" / f"{plan_id}_r2.json").exists())
        self.assertTrue((self.tmpdir / "alignment").glob(f"{plan_id}_*.json"))
        self.assertTrue(any((self.tmpdir / "insights").glob("*.json")))
        self.assertTrue(any((self.tmpdir / "models").glob("updated_*.json")))
        self.assertTrue(any((self.tmpdir / "evals").glob("loop_correctness_*.json")))

    def test_failed_guard_blocks_and_rolls_back(self):
        # A manifest touching a denied path must be rejected (Phase 3 safety
        # still governs the Phase 4/5 learning loop).
        manifest = {
            "manifest_version": "1.0",
            "author": "self_model_engine",
            "timestamp": "2026-09-07T12:00:00Z",
            "approval_level": "system",
            "changes": [{
                "file_path": "Architect/core/config.py",
                "change_type": "modify",
                "checksum_before": "",
                "checksum_after": "",
            }],
        }
        manifest_path = self.tmpdir / "bad_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        passed, message = validate_manifest_update(str(manifest_path))
        self.assertFalse(passed)

    def test_alignment_improves_across_iterations(self):
        """Two loop iterations with improving executions -> alignment trend up."""
        for iteration, success_rate in enumerate((0.3, 0.9)):
            plan_id = f"plan_iter_{iteration}"
            self._emit("plan_updated", plan_id, "plan created")
            self._run_execution(plan_id, "accept" if success_rate > 0.5 else "reject",
                                [] if success_rate > 0.5 else ["E_INTERNAL: x"],
                                {"success_rate": success_rate})
            points = self.collector.collect(plan_id)
            alignment = self.tracker.compute_all(
                [p.to_dict() for p in points],
                [{"preference_ratio": 0.5 + success_rate / 4}],
                [{"passed": success_rate > 0.5}])
            self.alignment_service.save_metrics(plan_id, alignment)

        first = self.alignment_service.latest("plan_iter_0")["alignment_score"]
        second = self.alignment_service.latest("plan_iter_1")["alignment_score"]
        self.assertGreater(second, first)


if __name__ == "__main__":
    unittest.main()
