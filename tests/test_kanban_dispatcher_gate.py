"""Sandbox-Gate im Dispatcher: fail-closed, Merge nur bei gruenem Gate, Aufraeumen danach.

Echte Git-Repos und echte Subprozesse in einem eigenen Temp-Verzeichnis (kein ``workspace/``).
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.breaker import CircuitBreaker
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.decomposer import ChecklistDecomposer
from orchestrator.kanban.dispatcher import Dispatcher
from orchestrator.kanban.models import KanbanBoard, KanbanTask, TaskStatus, Worker, WorkerStatus
from orchestrator.kanban.notify import NullNotifier
from orchestrator.kanban.store import SqliteKanbanStore
from tests.test_kanban_dispatcher import FakeBus, FakeHeartbeats, FakeLocks, FakeSandbox, FakeService, FakeTokens, FakeVault

WORKER_UID = "w1-1111-1111-1111"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


class CommittingSandbox(FakeSandbox):
    """Worker, der im Worktree eine Datei schreibt und committet."""

    def __init__(self, content="aus dem worker\n", commit=True):
        super().__init__()
        self.content = content
        self.commit = commit

    async def run(self, spec, *, on_heartbeat):
        work = spec.run_dir / "work"
        (work / "feature.txt").write_text(self.content)
        if self.commit:
            git(work, "add", "feature.txt")
            git(work, "commit", "-q", "-m", "worker change")
        return await super().run(spec, on_heartbeat=on_heartbeat)


GATE_GREEN = "import sys; sys.exit(0)\n"
GATE_RED = "import sys, json; print(json.dumps({'passed': False})); sys.exit(1)\n"
GATE_SLOW = "import time; time.sleep(30)\n"


class TestDispatcherGate(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Test")
        (self.repo / "README").write_text("base\n")
        git(self.repo, "add", "README")
        git(self.repo, "commit", "-q", "-m", "init")

        self.gate = root / "gate.py"
        self.gate.write_text(GATE_GREEN)

        self.store = SqliteKanbanStore(":memory:")
        await self.store.init()
        await self.store.create_board(KanbanBoard(id="b1", name="B1"))
        ledger = AuditLedger(self.store)
        bus = FakeBus()
        self.locks = FakeLocks()
        self.config = KanbanConfig(
            workspace_dir=root / "ws", vault_dir=root / "vault", gate_script=self.gate, gate_timeout_s=1.0
        )
        self.dispatcher = Dispatcher(
            store=self.store, service=FakeService(self.store, bus, ledger), locks=self.locks,
            heartbeats=FakeHeartbeats(), tokens=FakeTokens(), sandbox=CommittingSandbox(),
            breaker=CircuitBreaker(store=self.store, ledger=ledger, notifier=NullNotifier(), bus_service=bus,
                                   threshold=3, cooldown_s=60),
            vault=FakeVault(), decomposer=ChecklistDecomposer(), config=self.config, owner_id="test_owner",
        )

    async def asyncTearDown(self):
        await self.store.close()
        self.tmp.cleanup()

    async def _run_task(self):
        await self.store.upsert_worker(Worker(uid=WORKER_UID, name="W1", status=WorkerStatus.IDLE))
        await self.store.create_task(KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.READY,
                                                workspace_repo=str(self.repo)))
        await self.dispatcher.tick(wait=True)
        return await self.store.get_task("1")

    def assert_cleaned_up(self):
        self.assertEqual(git(self.repo, "branch", "--list", "kanban/*").strip(), "")
        self.assertEqual(len(git(self.repo, "worktree", "list", "--porcelain").split("worktree ")), 2)
        self.assertEqual(self.locks.locks, {})

    def assert_not_merged(self):
        self.assertFalse((self.repo / "feature.txt").exists())
        self.assertEqual(git(self.repo, "rev-list", "--count", "HEAD").strip(), "1")

    async def test_green_gate_merges_no_ff_and_cleans_up(self):
        task = await self._run_task()
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result_payload["merge"]["merged"], True)
        self.assertEqual(task.result_payload["merge"]["target"], "main")
        self.assertEqual((self.repo / "feature.txt").read_text(), "aus dem worker\n")
        # --no-ff: Merge-Commit mit zwei Eltern
        self.assertEqual(len(git(self.repo, "rev-list", "--parents", "-n1", "HEAD").split()), 3)
        self.assertIn("Auto-merge Kanban Run 1-a0", git(self.repo, "log", "-1", "--format=%s"))
        self.assert_cleaned_up()

    async def test_red_gate_discards(self):
        self.gate.write_text(GATE_RED)
        task = await self._run_task()
        self.assertEqual(task.status, TaskStatus.READY)  # Breaker -> Retry
        self.assertEqual(task.attempts, 1)
        self.assert_not_merged()
        self.assert_cleaned_up()

    async def test_missing_gate_fails_closed(self):
        self.gate.unlink()
        task = await self._run_task()
        self.assertEqual(task.status, TaskStatus.READY)
        self.assert_not_merged()
        self.assert_cleaned_up()

    async def test_gate_timeout_fails_closed(self):
        self.gate.write_text(GATE_SLOW)
        task = await self._run_task()
        self.assertEqual(task.status, TaskStatus.READY)
        self.assert_not_merged()
        self.assert_cleaned_up()

    async def test_dirty_target_checkout_blocks_merge(self):
        (self.repo / "README").write_text("lokale aenderung\n")
        task = await self._run_task()
        self.assertEqual(task.status, TaskStatus.READY)
        self.assertFalse((self.repo / "feature.txt").exists())
        self.assertEqual((self.repo / "README").read_text(), "lokale aenderung\n")
        self.assert_cleaned_up()

    async def test_merge_conflict_is_aborted(self):
        (self.repo / "feature.txt").write_text("schon im main\n")
        git(self.repo, "add", "feature.txt")
        git(self.repo, "commit", "-q", "-m", "konkurrierende aenderung")
        # Worktree wird vom aktuellen HEAD erzeugt; den Konflikt nach dem Abzweig erzwingen:
        self.dispatcher.sandbox = ConflictingSandbox(self.repo)
        task = await self._run_task()
        self.assertEqual(task.status, TaskStatus.READY)
        self.assertEqual(git(self.repo, "status", "--porcelain").strip(), "")
        self.assertFalse((self.repo / ".git" / "MERGE_HEAD").exists())
        self.assert_cleaned_up()

    async def test_uncommitted_worktree_changes_are_rejected(self):
        self.dispatcher.sandbox = ModifyTrackedSandbox()
        task = await self._run_task()
        self.assertEqual(task.status, TaskStatus.READY)
        self.assertEqual((self.repo / "README").read_text(), "base\n")
        self.assert_cleaned_up()

    async def test_gate_receives_contract_arguments(self):
        seen = Path(self.tmp.name) / "argv.txt"
        self.gate.write_text(f"import sys; open({str(seen)!r}, 'w').write(' '.join(sys.argv[1:]))\n")
        await self._run_task()
        argv = seen.read_text().split()
        self.assertEqual(argv[0], "--worktree")
        self.assertTrue(argv[1].endswith("runs/1-a0/work"))
        self.assertEqual(argv[2:], ["--run-id", "1-a0"])


class ConflictingSandbox(CommittingSandbox):
    """Committet im Worktree, waehrend main parallel dieselbe Datei anders aendert."""

    def __init__(self, repo):
        super().__init__(content="vom worker\n")
        self.repo = repo

    async def run(self, spec, *, on_heartbeat):
        result = await super().run(spec, on_heartbeat=on_heartbeat)
        (self.repo / "feature.txt").write_text("main hat parallel geaendert\n")
        git(self.repo, "commit", "-q", "-am", "parallel")
        return result


class ModifyTrackedSandbox(FakeSandbox):
    async def run(self, spec, *, on_heartbeat):
        (spec.run_dir / "work" / "README").write_text("nicht committet\n")
        return await super().run(spec, on_heartbeat=on_heartbeat)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(unittest.main())
