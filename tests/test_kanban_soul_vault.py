import asyncio
import tempfile
import unittest
from pathlib import Path

from core.protocol import utc_now_iso
from orchestrator.kanban.models import Experience, KanbanBoard, KanbanTask, TaskStatus, Worker, WorkerStatus
from orchestrator.kanban.sandbox import SandboxResult
from orchestrator.kanban.soul import default_soul, merge_skills, parse_soul, render_soul
from orchestrator.kanban.store import SqliteKanbanStore
from orchestrator.kanban.sync import sync_back
from orchestrator.kanban.vault import ObsidianVault, WorkerHome


class TestSoul(unittest.TestCase):
    def test_roundtrip(self):
        original = default_soul("test-worker", "Worker-One", ("python", "bash"), "Mission")
        parsed = parse_soul(original)
        rendered = render_soul(parsed)
        self.assertEqual(rendered, original)

    def test_merge_skills(self):
        original = default_soul("test-worker", "Worker-One", ("python", "bash"))
        merged = merge_skills(original, ["bash", "rust"])
        parsed = parse_soul(merged)
        self.assertEqual(parsed.core_skills, ["python", "bash", "rust"])
        self.assertEqual(parsed.frontmatter["skills"], "python,bash,rust")

    def test_unknown_sections(self):
        text = "## Unknown\nSome content\n\n## Another\nMore content"
        parsed = parse_soul(text)
        rendered = render_soul(parsed)
        self.assertIn("## Unknown", rendered)
        self.assertIn("Some content", rendered)

if __name__ == "__main__":
    unittest.main()




class TestVault(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = ObsidianVault(self.root)
        self.home = WorkerHome(self.root / "workspace")
        self.task = KanbanTask(
            id="t-1234567890ab",
            board_id="b-1",
            title="Test Task",
            status=TaskStatus.COMPLETED,
            assigned_worker_uid="test-worker"
        )
        self.exp = Experience(
            id="e-1",
            worker_uid="test-worker",
            task_id="t-1234567890ab",
            summary="Did work",
            outcome="completed",
            lessons=["lesson 1"],
            skills_delta=["python"],
            created_at=utc_now_iso()
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_vault_operations(self):
        # SOUL mirror
        self.vault.mirror_soul("test-worker", "soul content")
        self.assertTrue((self.root / "workers" / "test-worker" / "SOUL.md").exists())
        self.assertTrue((self.root / "workers" / "test-worker" / "test-worker.md").exists())

        # History
        self.vault.append_history("test-worker", "- 2024-01-01 line 1")
        self.vault.append_history("test-worker", "- 2024-01-02 line 2")
        history_content = (self.root / "workers" / "test-worker" / "history.md").read_text("utf-8")
        self.assertEqual(history_content, "- 2024-01-01 line 1\n- 2024-01-02 line 2\n")

        # Write task
        self.vault.write_task(self.task)
        self.assertTrue((self.root / "tasks" / "task-t-1234567890ab.md").exists())

        # Write experience
        self.vault.write_experience(self.exp, self.task)
        date = self.exp.created_at[:10]
        self.assertTrue((self.root / "workers" / "test-worker" / "experiences" / f"{date}-t-1234567890ab.md").exists())

        # No tmp files
        tmps = list(self.root.rglob("*.tmp"))
        self.assertEqual(len(tmps), 0)

    def test_invalid_uid(self):
        with self.assertRaises(ValueError):
            self.vault.mirror_soul("../test", "content")
        with self.assertRaises(ValueError):
            self.home.write_soul("../test", "content")

    def test_invalid_task_id(self):
        task = KanbanTask(id="invalid-id", board_id="b-1", title="title")
        with self.assertRaises(ValueError):
            self.vault.write_task(task)



class TestSyncBack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault_dir = self.root / "vault"
        self.workspace_dir = self.root / "workspace"
        self.out_dir = self.root / "out"
        self.db_path = self.root / "kanban.db"

        self.vault_dir.mkdir()
        self.workspace_dir.mkdir()
        self.out_dir.mkdir()

        self.vault = ObsidianVault(self.vault_dir)
        self.store = SqliteKanbanStore(self.db_path)

        self.task = KanbanTask(
            id="t-1234567890ab",
            board_id="b-1",
            title="Test Task",
            status=TaskStatus.IN_PROGRESS,
            assigned_worker_uid="test-worker"
        )
        self.worker = Worker(
            uid="test-worker",
            name="Worker-One",
            skills=("python",),
            status=WorkerStatus.IDLE
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_sync_back_success(self):
        (self.out_dir / "result.json").write_text('{"status": "completed", "reason": "done", "result_payload": {"x": 1}}')
        (self.out_dir / "experience.json").write_text('{"summary": "great success", "outcome": "completed", "lessons": ["l1"], "skills_delta": ["s1"]}')
        (self.out_dir / "SOUL.md").write_text('updated soul')

        result = SandboxResult(
            exit_code=0,
            timed_out=False,
            cancelled=False,
            out_dir=self.out_dir,
            stderr_tail=""
        )

        async def run():
            await self.store.init()

            s = self.store
            if True:
                await s.upsert_worker(worker=self.worker)
                await s.create_board(board=KanbanBoard(id="b-1", name="B1"))
                await s.create_task(task=self.task)

                outcome = await sync_back(
                    store=s,
                    vault=self.vault,
                    workspace_dir=self.workspace_dir,
                    task=self.task,
                    worker=self.worker,
                    result=result
                )

                self.assertEqual(outcome.status, "completed")
                self.assertEqual(outcome.reason, "done")
                self.assertEqual(outcome.result_payload, {"x": 1})
                self.assertEqual(outcome.soul_md, "updated soul")
                self.assertEqual(outcome.experience.summary, "great success")

                # Check DB
                db_worker = await s.get_worker("test-worker")
                self.assertEqual(db_worker.soul_md, "updated soul")

                # Check Vault
                self.assertTrue((self.vault_dir / "workers" / "test-worker" / "SOUL.md").exists())
                self.assertTrue((self.vault_dir / "tasks" / "task-t-1234567890ab.md").exists())
                self.assertTrue((self.workspace_dir / "workers" / "test-worker" / "SOUL.md").exists())

                exps = await s._run(lambda conn: conn.execute("SELECT vault_synced FROM experiences WHERE id = ?", (outcome.experience.id,)).fetchall())
                self.assertTrue(exps[0]["vault_synced"])

        asyncio.run(run())

    def test_sync_back_no_result(self):
        result = SandboxResult(
            exit_code=1,
            timed_out=False,
            cancelled=False,
            out_dir=self.out_dir,
            stderr_tail=""
        )

        async def run():
            await self.store.init()

            s = self.store
            if True:
                await s.upsert_worker(worker=self.worker)
                await s.create_board(board=KanbanBoard(id="b-1", name="B1"))
                await s.create_task(task=self.task)

                outcome = await sync_back(
                    store=s,
                    vault=self.vault,
                    workspace_dir=self.workspace_dir,
                    task=self.task,
                    worker=self.worker,
                    result=result
                )

                self.assertEqual(outcome.status, "failed")
                self.assertTrue(outcome.reason.startswith("no result"))

        asyncio.run(run())

    def test_sync_back_readonly_vault(self):
        (self.out_dir / "result.json").write_text('{"status": "completed"}')
        self.vault_dir.chmod(0o555) # read-only

        result = SandboxResult(
            exit_code=0,
            timed_out=False,
            cancelled=False,
            out_dir=self.out_dir,
            stderr_tail=""
        )

        async def run():
            await self.store.init()

            s = self.store
            if True:
                await s.upsert_worker(worker=self.worker)
                await s.create_board(board=KanbanBoard(id="b-1", name="B1"))
                await s.create_task(task=self.task)

                outcome = await sync_back(
                    store=s,
                    vault=self.vault,
                    workspace_dir=self.workspace_dir,
                    task=self.task,
                    worker=self.worker,
                    result=result
                )

                exps = await s._run(lambda conn: conn.execute("SELECT vault_synced FROM experiences WHERE id = ?", (outcome.experience.id,)).fetchall())
                self.assertFalse(exps[0]["vault_synced"])

        asyncio.run(run())
        self.vault_dir.chmod(0o777) # cleanup
