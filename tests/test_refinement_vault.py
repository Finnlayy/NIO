"""Refinement-Vault + Daemon: FSM, Lease/Backoff, Fehlerisolation, CLI.

Kein Cargo, kein Docker, kein LLM: Sandbox und Ciel-Heiler sind Fakes mit
echten Dateien. Geprueft wird der Vertrag (Zustaende, Versionen, Hashes,
FIFO, Quarantaene), nicht eine bestimmte Heil-Strategie.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, timedelta
from datetime import time as day_time
from pathlib import Path

from core.protocol import utc_now
from orchestrator.cli import main as cli_main
from orchestrator.refinement import (
    HEALING_IN_PROGRESS,
    PARKED_PENDING_USER,
    PROMOTED,
    QUARANTINED,
    READY_FOR_REVIEW,
    REFINEMENT_QUEUED,
    InvalidTransition,
    RefinementVault,
    VaultError,
)
from orchestrator.refinement_daemon import (
    CommandSandbox,
    NullHealer,
    RefinementDaemon,
    StepResult,
    in_active_window,
)


class FakeSandbox:
    """Gruen, sobald das Artefakt den Marker enthaelt -- wie ein echter Test."""

    def __init__(self, *, explode: bool = False) -> None:
        self.calls = 0
        self.explode = explode

    def run_tests(self, entry, workdir):
        self.calls += 1
        if self.explode:
            raise RuntimeError("sandbox kaputt")
        text = (workdir / entry.artifact_filename).read_text(encoding="utf-8")
        if "FIXED" in text:
            return StepResult.success("test")
        return StepResult.failure("test", "test_failed", "Marker FIXED fehlt", "compiler: error[E0308]")


class MarkerHealer:
    """Ciel-Ersatz: schreibt genau einen kleinen Patch (Marker anhaengen)."""

    def __init__(self) -> None:
        self.seen_failures: list[StepResult] = []

    def heal(self, entry, workdir, failure):
        self.seen_failures.append(failure)
        patched = workdir / "patched" / entry.artifact_filename
        patched.parent.mkdir(parents=True, exist_ok=True)
        patched.write_text((workdir / entry.artifact_filename).read_text(encoding="utf-8") + "\nFIXED\n", encoding="utf-8")
        return patched


class VaultCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nio-refine-")
        self.root = Path(self._tmp.name)
        self.vault = RefinementVault(self.root / "vault")
        self.source = self.root / "libnio_limb.rs"
        self.source.write_text("fn main() {}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def park(self, limb_id: str = "limb-a", **kwargs) -> object:
        return self.vault.park(self.source, limb_id=limb_id, test_command=("check", "{artifact}"), **kwargs)


class FsmTest(VaultCase):
    def test_park_creates_meta_artifact_and_version_snapshot(self) -> None:
        entry = self.park()
        self.assertEqual(entry.state, PARKED_PENDING_USER)
        self.assertTrue(self.vault.meta_path("limb-a").is_file())
        self.assertEqual(self.vault.artifact_path(entry).read_text(encoding="utf-8"), "fn main() {}\n")
        self.assertEqual(self.vault.version_path(entry, 1).read_text(encoding="utf-8"), "fn main() {}\n")
        self.assertEqual(len(entry.sha256), 64)
        loaded = self.vault.get("limb-a")
        self.assertEqual(loaded.to_dict()["artifact"]["sha256"], entry.sha256)

    def test_illegal_transition_and_bad_ids_are_loud(self) -> None:
        self.park()
        with self.assertRaises(VaultError):
            self.park()  # doppelt parken
        with self.assertRaises(VaultError):
            self.vault.park(self.source, limb_id="../escape")
        entry = self.vault.get("limb-a")
        with self.assertRaises(InvalidTransition):
            self.vault.complete_healing("limb-a", worker_id="w1")
        self.assertEqual(entry.state, PARKED_PENDING_USER)

    def test_human_loop_reject_claim_heal_review_approve(self) -> None:
        self.park()
        queued = self.vault.reject("limb-a", feedback="Lifetime-Fehler in FFI")
        self.assertEqual(queued.state, REFINEMENT_QUEUED)
        self.assertIn("Lifetime", queued.user_feedback)

        claimed = self.vault.claim_next(worker_id="daemon-1")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.state, HEALING_IN_PROGRESS)
        with self.assertRaises(VaultError):
            self.vault.complete_healing("limb-a", worker_id="fremder-worker")

        ready = self.vault.complete_healing("limb-a", worker_id="daemon-1")
        self.assertEqual(ready.state, READY_FOR_REVIEW)

        baseline = self.root / "baseline" / "libnio_limb.rs"
        promoted = self.vault.approve("limb-a", promote_to=baseline)
        self.assertEqual(promoted.state, PROMOTED)
        self.assertEqual(baseline.read_text(encoding="utf-8"), "fn main() {}\n")

    def test_ready_can_be_rejected_again(self) -> None:
        self.park()
        self.vault.reject("limb-a")
        self.vault.claim_next(worker_id="w")
        self.vault.complete_healing("limb-a", worker_id="w")
        again = self.vault.reject("limb-a", feedback="immer noch nicht")
        self.assertEqual(again.state, REFINEMENT_QUEUED)

    def test_final_reject_quarantines_and_human_can_requeue(self) -> None:
        self.park()
        self.assertEqual(self.vault.reject("limb-a", final=True).state, QUARANTINED)
        self.assertEqual(self.vault.requeue("limb-a").state, REFINEMENT_QUEUED)
        self.assertEqual(self.vault.get("limb-a").attempts, 0)


class FailureIsolationTest(VaultCase):
    def test_fail_healing_backoff_then_quarantine(self) -> None:
        self.park(max_attempts=2)
        self.vault.reject("limb-a")
        self.vault.claim_next(worker_id="w")
        failed = self.vault.fail_healing("limb-a", worker_id="w", step="test", kind="test_failed", message="E0308", now=utc_now())
        self.assertEqual(failed.state, REFINEMENT_QUEUED)
        self.assertEqual(failed.attempts, 1)
        self.assertTrue(failed.next_attempt_at)
        self.assertIsNone(self.vault.claim_next(worker_id="w"))  # Backoff wirkt

        later = utc_now() + timedelta(hours=2)
        self.assertIsNotNone(self.vault.claim_next(worker_id="w", now=later))
        dead = self.vault.fail_healing("limb-a", worker_id="w", step="test", kind="test_failed", message="E0308", now=later)
        self.assertEqual(dead.state, QUARANTINED)
        self.assertIsNone(self.vault.claim_next(worker_id="w", now=later + timedelta(days=1)))

    def test_stale_lease_is_recovered_and_counts_as_attempt(self) -> None:
        self.park()
        self.vault.reject("limb-a")
        self.vault.claim_next(worker_id="toter-worker", lease_s=10)
        recovered = self.vault.recover_stale_leases(now=utc_now() + timedelta(minutes=5))
        self.assertEqual([entry.limb_id for entry in recovered], ["limb-a"])
        entry = self.vault.get("limb-a")
        self.assertEqual(entry.state, REFINEMENT_QUEUED)
        self.assertEqual(entry.attempts, 1)
        self.assertEqual(entry.last_error["kind"], "lease_expired")

    def test_fifo_oldest_first(self) -> None:
        self.park("limb-a")
        self.park("limb-b")
        self.vault.reject("limb-b")
        self.vault.reject("limb-a")
        first = self.vault.claim_next(worker_id="w")
        self.assertEqual(first.limb_id, "limb-a")  # angelegt zuerst, nicht Ablehn-Reihenfolge


class DaemonTest(VaultCase):
    def _queued(self, limb_id: str = "limb-a", **kwargs) -> None:
        self.park(limb_id, **kwargs)
        self.vault.reject(limb_id)

    def test_heal_patch_retest_ready_and_notify(self) -> None:
        self._queued()
        notified: list[str] = []
        healer = MarkerHealer()
        daemon = RefinementDaemon(self.vault, sandbox=FakeSandbox(), healer=healer, notify=lambda e: notified.append(e.state))
        report = daemon.run_once()
        self.assertEqual(report.outcome, READY_FOR_REVIEW)
        entry = self.vault.get("limb-a")
        self.assertEqual(entry.version, 2)
        self.assertEqual(entry.heal_steps, 1)
        self.assertIn("FIXED", self.vault.artifact_path(entry).read_text(encoding="utf-8"))
        self.assertTrue(self.vault.version_path(entry, 1).is_file())
        self.assertEqual(healer.seen_failures[0].kind, "test_failed")
        self.assertEqual(notified, [READY_FOR_REVIEW])

    def test_null_healer_never_invents_a_fix(self) -> None:
        self._queued()
        daemon = RefinementDaemon(self.vault, sandbox=FakeSandbox(), healer=NullHealer(), retry_base_s=0)
        report = daemon.run_once()
        self.assertEqual(report.outcome, REFINEMENT_QUEUED)
        entry = self.vault.get("limb-a")
        self.assertEqual(entry.version, 1)
        self.assertEqual(entry.last_error["kind"], "test_failed")

    def test_exploding_sandbox_is_isolated_to_the_entry(self) -> None:
        self._queued("limb-a")
        self._queued("limb-b")
        daemon = RefinementDaemon(self.vault, sandbox=FakeSandbox(explode=True), retry_base_s=0)
        report = daemon.run_once()
        self.assertEqual(report.limb_id, "limb-a")
        self.assertEqual(self.vault.get("limb-a").last_error["kind"], "step_error")
        self.assertEqual(self.vault.get("limb-b").state, REFINEMENT_QUEUED)  # nicht angefasst, nicht verloren

    def test_command_sandbox_uses_entry_test_command(self) -> None:
        sandbox = CommandSandbox(timeout_s=30)
        entry = self.park()
        import sys

        entry.test_command = (sys.executable, "-c", "import pathlib,sys; sys.exit(0 if 'fn main' in pathlib.Path(sys.argv[1]).read_text() else 1)", "{artifact}")
        result = sandbox.run_tests(entry, self.root)
        self.assertTrue(result.ok, result)

    def test_async_scheduler_loop_processes_queue(self) -> None:
        import asyncio

        self._queued()
        daemon = RefinementDaemon(self.vault, sandbox=FakeSandbox(), healer=MarkerHealer())
        reports = asyncio.run(daemon.run_forever(interval_s=1, max_cycles=1, max_items_per_cycle=1))
        self.assertEqual([report.outcome for report in reports], [READY_FOR_REVIEW])
        # Zweiter Daemon auf demselben Vault wird vom Instanz-Lock abgelehnt,
        # solange der erste laeuft -- hier: Lock ist nach dem Lauf wieder frei.
        reports = asyncio.run(daemon.run_forever(interval_s=1, max_cycles=1))
        self.assertEqual(reports[0].outcome, "empty")

    def test_active_window_over_midnight(self) -> None:
        from datetime import datetime

        night = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)
        noon = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        self.assertTrue(in_active_window(night, start=day_time(22, 0), end=day_time(5, 0)))
        self.assertFalse(in_active_window(noon, start=day_time(22, 0), end=day_time(5, 0)))
        self.assertTrue(in_active_window(noon, start=None, end=None))


class CliTest(VaultCase):
    def _cli(self, *argv: str) -> tuple[int, dict]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli_main(["--runtime-dir", str(self.root / "runtime"), "--json", *argv])
        return code, json.loads(buffer.getvalue() or "{}")

    def test_cli_park_reject_run_once_list(self) -> None:
        code, parked = self._cli("refinement", "park", str(self.source), "--limb-id", "cli-limb")
        self.assertEqual(code, 0)
        self.assertEqual(parked["state"], PARKED_PENDING_USER)
        code, rejected = self._cli("refinement", "reject", "cli-limb", "--feedback", "bitte heilen")
        self.assertEqual(rejected["state"], REFINEMENT_QUEUED)
        code, reports = self._cli("refinement", "run-once")
        self.assertEqual(code, 0)
        # Kein test_command hinterlegt -> isolierter Fehlschlag statt Schein-Heilung.
        self.assertEqual(reports[0]["outcome"], REFINEMENT_QUEUED)
        code, entries = self._cli("refinement", "list")
        self.assertEqual(entries[0]["last_error"]["kind"], "no_test_command")


if __name__ == "__main__":
    unittest.main()
