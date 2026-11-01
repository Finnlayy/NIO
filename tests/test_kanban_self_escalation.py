import json
import asyncio
import tempfile
from pathlib import Path
import unittest
import hashlib

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import KanbanTask, Worker, TaskStatus, WorkerStatus, KanbanBoard
from orchestrator.kanban.sandbox import SandboxSpec, build_sandbox
from orchestrator.kanban.store import SqliteKanbanStore
from orchestrator.kanban.sync import sync_back
from orchestrator.kanban.vault import ObsidianVault
from orchestrator.kanban.sandbox import SandboxResult, SubprocessSandbox

class TestSelfEscalation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = KanbanConfig(repo_root=self.root)
        self.vault_dir = self.root / "vault"
        self.workspace_dir = self.root / "workspace"
        self.out_dir = self.root / "out"
        self.db_path = self.root / "kanban.db"

        self.vault_dir.mkdir(parents=True)
        self.workspace_dir.mkdir(parents=True)
        self.out_dir.mkdir(parents=True)

        self.store = SqliteKanbanStore(self.db_path)
        await self.store.init()
        self.vault = ObsidianVault(self.vault_dir)

        self.worker = Worker(uid="test-worker", name="Worker-One", soul_md="---\nruntime: noop\n---\n## Core", status=WorkerStatus.IDLE)
        await self.store.upsert_worker(self.worker)

        self.task = KanbanTask(id="t-1234567890ab", board_id="b-1", title="Test Task", status=TaskStatus.IN_PROGRESS, assigned_worker_uid="test-worker")

    async def asyncTearDown(self):
        await self.store.close()
        self.tmp.cleanup()

    async def test_worker_cannot_change_soul_and_defaults_to_docker(self):
        await self.store.create_board(board=KanbanBoard(id="b-1", name="B1"))
        def _do(conn):
            self.store._insert_task(conn, self.task)
        await self.store._run(_do)

        # Test 1: Worker proposes new SOUL.md with arbitrary command
        new_soul = "---\nruntime: command\ncommand: [\"ls\"]\n---\n## Core"
        (self.out_dir / "SOUL.md").write_text(new_soul)
        (self.out_dir / "result.json").write_text('{"status": "completed", "result_payload": {}}')

        res = SandboxResult(exit_code=0, timed_out=False, cancelled=False, out_dir=self.out_dir, stderr_tail="")

        outcome = await sync_back(
            store=self.store,
            vault=self.vault,
            workspace_dir=self.workspace_dir,
            task=self.task,
            worker=self.worker,
            result=res
        )

        updated_worker = await self.store.get_worker("test-worker")

        # Gap 1: Worker shouldn't be able to apply its own new soul directly
        self.assertEqual(updated_worker.soul_md, "---\nruntime: noop\n---\n## Core")

        updated_task = await self.store.get_task(self.task.id)
        payload = updated_task.result_payload or {}

        # It should become a proposal instead
        self.assertIn("proposed_soul", payload)
        self.assertEqual(payload["proposed_soul"]["status"], "pending")
        self.assertEqual(payload["proposed_soul"]["content"], new_soul)
        self.assertEqual(payload["proposed_soul"]["sha256"], hashlib.sha256(new_soul.encode("utf-8")).hexdigest())

        # Gap 2: Sandbox should default to docker
        self.assertEqual(self.config.sandbox, "docker")

        # Gap 3: SubprocessSandbox strictly requires runtime: noop, fails for command
        spec = SandboxSpec(
            run_id="run1",
            task=self.task,
            worker=Worker(uid="w1", name="w1", soul_md="---\nruntime: command\n---\n"),
            run_dir=self.out_dir,
            env={}, secrets={}, image="", deadline_s=10
        )

        sb = SubprocessSandbox(self.config)
        with self.assertRaises(ValueError):
            sb._prepare(spec)
