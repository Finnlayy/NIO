import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from core.budget import BudgetTracker, Usage, BudgetError
from core.protocol import ErrorCode
from limbs.base import LimbError
from limbs.agent_base import AgentLimb, Poll, LimbContext, MIN_POLL_S
from core.config import NeuConfig

class BudgetTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        # Setup specific env vars to test defaults vs env
        self.env = {
            "NIO_BUDGET_DAILY_SECONDS": "10.0",
            "NIO_BUDGET_RUN_SECONDS": "5.0",
            "NIO_BUDGET_DAILY_TOKENS": "100",
            "NIO_BUDGET_RUN_TOKENS": "50",
            "NIO_BUDGET_DAILY_CREDITS": "10.0",
            "NIO_BUDGET_RUN_CREDITS": "5.0"
        }
        with patch.dict(os.environ, self.env, clear=True):
            self.tracker = BudgetTracker(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_limit(self):
        with patch.dict(os.environ, self.env, clear=True):
            self.tracker.check_start()  # Should succeed
            delta = Usage(seconds=6.0, tokens=None, credits=0.0)
            total_run = Usage(seconds=6.0, tokens=None, credits=0.0)
            reason = self.tracker.record_and_check("run_1", delta, total_run)
            self.assertIn("Laufzeit-Budget für diesen Lauf", reason)

            delta = Usage(seconds=1.0, tokens=60, credits=0.0)
            total_run = Usage(seconds=1.0, tokens=60, credits=0.0)
            reason = self.tracker.record_and_check("run_1", delta, total_run)
            self.assertIn("Token-Budget für diesen Lauf", reason)

    def test_daily_limit(self):
        with patch.dict(os.environ, self.env, clear=True):
            self.tracker.check_start()
            # Verbuchen von 4.0, dann noch mal 7.0 -> daily limit
            reason = self.tracker.record_and_check(
                "run_1",
                Usage(seconds=4.0, tokens=40, credits=0.0),
                Usage(seconds=4.0, tokens=40, credits=0.0)
            )
            self.assertEqual(reason, "")

            reason = self.tracker.record_and_check(
                "run_2",
                Usage(seconds=7.0, tokens=40, credits=0.0),
                Usage(seconds=4.0, tokens=40, credits=0.0) # total_run ist im Limit
            )
            self.assertIn("Tägliches Laufzeit-Budget", reason)

            # check_start sollte nun failen
            with self.assertRaises(BudgetError):
                self.tracker.check_start()

    def test_day_rollover(self):
        dt_today = datetime(2025, 1, 1, tzinfo=timezone.utc)
        dt_tomorrow = datetime(2025, 1, 2, tzinfo=timezone.utc)

        with patch.dict(os.environ, self.env, clear=True):
            # Verbrauche das heutige Budget
            self.tracker.record_and_check(
                "run_1",
                Usage(seconds=11.0, tokens=0, credits=0.0),
                Usage(seconds=1.0, tokens=0, credits=0.0), # run limit pass
                dt=dt_today
            )

            with self.assertRaises(BudgetError):
                self.tracker.check_start(dt=dt_today)

            # Morgen ist wieder Budget da
            self.tracker.check_start(dt=dt_tomorrow)

            # Sicherstellen dass Dateien geschrieben wurden
            self.assertTrue((self.root / "2025-01-01.json").exists())
            self.assertFalse((self.root / "2025-01-02.json").exists())

    def test_corrupt_ledger(self):
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        path = self.root / "2025-01-01.json"
        path.write_text("invalid json")

        with patch.dict(os.environ, self.env, clear=True):
            with self.assertRaises(BudgetError):
                self.tracker.check_start(dt=dt)

    def test_bad_env_vars_deny_runs(self):
        bad_envs = [
            {"NIO_BUDGET_DAILY_SECONDS": "-5"},
            {"NIO_BUDGET_DAILY_TOKENS": "not_a_number"},
            {"NIO_BUDGET_RUN_CREDITS": "NaN"}
        ]

        for e in bad_envs:
            with patch.dict(os.environ, e, clear=True):
                tracker = BudgetTracker(self.root)
                with self.assertRaises(BudgetError):
                    tracker.check_start()
                with self.assertRaises(BudgetError):
                    tracker.record_and_check("run_id", Usage(), Usage())

    def test_two_writers(self):
        import time
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with patch.dict(os.environ, self.env, clear=True):
            def writer(amount, tokens):
                for _ in range(50):
                    self.tracker.record_and_check(
                        "run_parallel",
                        Usage(seconds=amount, tokens=tokens, credits=0.0),
                        Usage(seconds=0.0, tokens=0, credits=0.0),
                        dt=dt
                    )
                    time.sleep(0.001)

            t1 = threading.Thread(target=writer, args=(0.1, 1))
            t2 = threading.Thread(target=writer, args=(0.1, 1))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            path = self.root / "2025-01-01.json"
            with path.open() as f:
                data = json.load(f)

            # 2 threads * 50 iterations * 0.1s = 10.0s
            self.assertAlmostEqual(data["seconds"], 10.0)
            self.assertEqual(data["tokens"], 100)

class FakeContext(LimbContext):
    def __init__(self):
        self.recorded = []
    def record(self, path, mode):
        self.recorded.append((path, mode))
    def rel(self, path):
        return f"rel/{path.name}"

class BudgetAgentLimb(AgentLimb):
    name = "budget_agent"

    def __init__(self, config):
        super().__init__(config)
        self.polls = []
        self.halted = 0

    def launch(self, params, ctx, run):
        pass

    def poll(self, run, ctx):
        if not self.polls:
            return Poll("running", {"tokens": 0})
        return self.polls.pop(0)

    def halt(self, run, ctx):
        self.halted += 1

class AgentIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.config = NeuConfig(repo_root=Path(self.temp_dir.name), runtime_dir=Path(self.temp_dir.name) / "runtime", protocol_dir=Path.cwd() / "protocol")
        (Path(self.temp_dir.name) / "runtime").mkdir()
        self.ctx = FakeContext()
        self.limb = BudgetAgentLimb(self.config)
        self.env = {
            "NIO_BUDGET_DAILY_SECONDS": "100.0",
            "NIO_BUDGET_RUN_SECONDS": "10.0",
            "NIO_BUDGET_DAILY_TOKENS": "1000",
            "NIO_BUDGET_RUN_TOKENS": "100",
            "NIO_BUDGET_DAILY_CREDITS": "10.0",
            "NIO_BUDGET_RUN_CREDITS": "1.0"
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_agent_limit_stops_run(self):
        with patch.dict(os.environ, self.env, clear=True):
            run = self.limb._start({}, self.ctx)
            run_id = run["run_id"]

            # Setze naechste poll zeit zurueck, damit wir sofort wieder abfragen duerfen
            run_obj = self.limb.runs.load(run_id, self.limb.name)
            run_obj["next_poll_s"] = 0.0
            self.limb.runs.save(run_obj)

            self.limb.polls = [Poll("running", {"tokens": 105})]
            view = self.limb._status({"run_id": run_id}, self.ctx)

            self.assertEqual(view["state"], "budget_stopped")
            self.assertEqual(self.limb.halted, 1)

    def test_agent_daily_limit_prevents_start(self):
        with patch.dict(os.environ, self.env, clear=True):
            # Manually blow the budget via tracker
            tracker = BudgetTracker(Path(self.config.runtime_dir) / "budget")
            tracker.record_and_check("fake", Usage(seconds=200.0, tokens=0, credits=0.0), Usage())

            with self.assertRaises(LimbError) as ctx:
                self.limb._start({}, self.ctx)
            self.assertEqual(ctx.exception.code, ErrorCode.POLICY_DENIED)

    def test_invalid_tokens_ends_run(self):
        with patch.dict(os.environ, self.env, clear=True):
            run = self.limb._start({}, self.ctx)
            run_id = run["run_id"]

            run_obj = self.limb.runs.load(run_id, self.limb.name)
            run_obj["next_poll_s"] = 0.0
            self.limb.runs.save(run_obj)

            self.limb.polls = [Poll("running", {"tokens": "not_a_number"})]
            view = self.limb._status({"run_id": run_id}, self.ctx)

            self.assertEqual(view["state"], "budget_stopped")
            self.assertEqual(self.limb.halted, 1)

    def test_negative_tokens_ends_run(self):
        with patch.dict(os.environ, self.env, clear=True):
            run = self.limb._start({}, self.ctx)
            run_id = run["run_id"]

            run_obj = self.limb.runs.load(run_id, self.limb.name)
            run_obj["next_poll_s"] = 0.0
            self.limb.runs.save(run_obj)

            self.limb.polls = [Poll("running", {"tokens": -10})]
            view = self.limb._status({"run_id": run_id}, self.ctx)

            self.assertEqual(view["state"], "budget_stopped")
            self.assertEqual(self.limb.halted, 1)
