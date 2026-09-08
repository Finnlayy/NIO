import sys
import asyncio
from core.state_machine import SystemExecutionState, MarketRegimeState

try:
    from core.daemon_supervisor import DaemonSupervisor
    DAEMON_AVAILABLE = True
except ImportError:  # ccxt.pro not installed (headless environment)
    DaemonSupervisor = None
    DAEMON_AVAILABLE = False

def test_imports():
    print("Testing core imports...")
    assert SystemExecutionState.PLANNING.name == "PLANNING"
    assert SystemExecutionState.DISPATCHED.name == "DISPATCHED"
    assert SystemExecutionState.RUNNING.name == "RUNNING"
    assert SystemExecutionState.REFLECTING.name == "REFLECTING"
    assert SystemExecutionState.COMPLETE.name == "COMPLETE"
    assert MarketRegimeState.BTC_SATELLITE.name == "BTC_SATELLITE"
    assert MarketRegimeState.CHOP_REACTIVE_NOISE.name == "CHOP_REACTIVE_NOISE"
    # Transition rules (Phase 2)
    from core.state_machine import TRANSITION_MAP
    assert SystemExecutionState.PLANNING in TRANSITION_MAP
    assert "plan_approved" in TRANSITION_MAP[SystemExecutionState.PLANNING]["triggers"]
    # Event bus whitelist (Phase 3/4/5 kinds)
    from core.events import EventBus, VALID_EVENT_KINDS
    for kind in ("execution_complete", "feedback_submitted", "model_updated",
                 "trajectory_collected", "alignment_updated", "review_due",
                 "risk_guard_failed"):
        assert kind in VALID_EVENT_KINDS
    bus = EventBus(system_log_path="/tmp/nio_smoke_system.log")
    assert bus.emit(bus.build_event(event_kind="execution_started", job_id="smoke")) is True
    assert bus.emit(bus.build_event(event_kind="not_a_real_kind")) is False
    # Learning engine math (Phase 4)
    from core.learning.skill_profiles import WilsonScoreCalculator
    assert 0.0 < WilsonScoreCalculator.compute(5, 5) < 1.0
    assert WilsonScoreCalculator.compute(0, 0) == 0.0
    from core.learning.spaced_repetition import SpacedRepetitionEngine
    assert abs(SpacedRepetitionEngine.update_ease_factor(2.5, 5) - 2.6) < 1e-9
    assert SpacedRepetitionEngine.update_interval(6.0, 2.5, 2) == 1.0
    # Outcome/feedback schemas parse (Phase 4)
    from core.outcome_parser import OutcomeParser
    parser = OutcomeParser()
    assert "verdict" in parser.schema["properties"]
    from core.feedback_processor import FeedbackProcessor
    assert FeedbackProcessor.aggregate(None, [])["count"] == 0
    # defineEval pipeline (Phase 4)
    from core.evaluation.define_eval import define_eval, mean_aggregator
    cfg = define_eval("smoke", {}, "evals/datasets/rlhf_samples.json", lambda s: 100.0)
    assert cfg.eval_name == "smoke"
    assert mean_aggregator([100.0, 50.0]) == 75.0
    # Phase 5 collectors/engines import cleanly
    from core.trajectory.trajectory_collector import TrajectoryCollector, TrajectoryPoint
    point = TrajectoryPoint(timestamp="t", state="RUNNING")
    assert point.state == "RUNNING"
    from core.alignment.alignment_tracker import AlignmentTracker
    assert AlignmentTracker().compute_learning_efficiency([]) == 0.0
    from core.self_model.self_model_engine import Insight
    assert Insight(category="strength", content="ok").insight_id.startswith("ins_")
    # Risk invariants (Judge M8)
    from limbs.math.the_judge_m8 import TheJudgeM8
    class _Limits:
        MAX_TOTAL_LEVERAGE = 5.0
        MAX_SLIPPAGE_BPS = 15.0
        MIN_VAULT_RESERVE_RATIO = 0.10
    ok, _ = TheJudgeM8(_Limits()).check_invariants(1.0, 1.0, 0.95, 0.5, False, True)
    assert ok is True
    print("Core imports OK.")

async def dummy_daemon():
    await asyncio.sleep(0.1)

async def test_daemon():
    if not DAEMON_AVAILABLE:
        print("ccxt not installed; skipping DaemonSupervisor smoke test.")
        return
    print("Testing DaemonSupervisor...")
    ds = DaemonSupervisor()
    ds.add_daemon(dummy_daemon)
    ds.stop()
    print("DaemonSupervisor OK.")

def test_gui():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("PyQt6 not installed; skipping GUI smoke test.")
        return
    from gui.app import GMTMainWindow
    print("Testing GUI initialization...")
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    window = GMTMainWindow()
    assert window is not None
    # Phase 5 tabs present in the full environment
    assert hasattr(window, "chart")
    print("GUI initialized OK.")

if __name__ == "__main__":
    test_imports()
    asyncio.run(test_daemon())
    test_gui()
    print("All tests passed.")
