"""Injizierte Geheimnisse duerfen aus Worker-Ausgaben nirgends ankommen.

Der Worker gibt jedes Geheimnis aus (stdout, stderr, result.json, experience.json,
SOUL.md). Geprueft wird, dass weder Store, Audit, Platte noch Fehlertexte den
Klartext enthalten, und dass das Task-Token nur Kanban-Tool-Worker erreicht.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.breaker import CircuitBreaker
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.decomposer import ChecklistDecomposer
from orchestrator.kanban.dispatcher import Dispatcher
from orchestrator.kanban.models import KanbanBoard, KanbanTask, TaskStatus, Worker, WorkerStatus
from orchestrator.kanban.notify import NullNotifier
from orchestrator.kanban.redact import REDACTED, redact
from orchestrator.kanban.sandbox import SandboxResult, SandboxSpec, _ProcessSandbox
from orchestrator.kanban.soul import uses_kanban_tools
from orchestrator.kanban.store import SqliteKanbanStore
from tests.test_kanban_dispatcher import FakeBus, FakeHeartbeats, FakeLocks, FakeService, FakeTokens, FakeVault

SECRET_A = "sk-test-AAAA-0123456789abcdef"
SECRET_B = "ghp_testBBBB9876543210"
WORKER_ENTRY = Path(__file__).resolve().parents[1] / "orchestrator" / "kanban" / "worker_entry.py"


def _soul(runtime: str, extra: str = "") -> str:
    return f"---\nruntime: {runtime}\n{extra}---\n## Identity\nTest\n"


class TestRedactHelper(unittest.TestCase):
    def test_nested_and_overlapping(self) -> None:
        data = {"a": f"x{SECRET_A}y", "l": [SECRET_B, {"k": SECRET_A[:-2]}], SECRET_B: 1}
        out = redact(data, [SECRET_A, SECRET_A[:-2], SECRET_B])
        self.assertNotIn(SECRET_A[:-2], json.dumps(out))
        self.assertNotIn(SECRET_B, json.dumps(out))
        self.assertEqual(out["a"], f"x{REDACTED}y")

    def test_empty_secret_is_ignored(self) -> None:
        self.assertEqual(redact("abc", [""]), "abc")


class TestTokenScope(unittest.TestCase):
    def test_only_kanban_tool_workers_need_token(self) -> None:
        self.assertFalse(uses_kanban_tools(_soul("noop")))
        self.assertFalse(uses_kanban_tools(_soul("command")))
        self.assertFalse(uses_kanban_tools(_soul("limb")))
        self.assertTrue(uses_kanban_tools(_soul("opencode")))
        self.assertTrue(uses_kanban_tools(_soul("command", "kanban_tools: true\n")))


class TestWorkerEntryRedacts(unittest.TestCase):
    """worker_entry.py schwaerzt schon in der Sandbox, bevor out/ beschrieben wird."""

    def _run(self, code: str) -> tuple[dict, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for d in ("in", "out", "work"):
                (root / d).mkdir()
            cmd = json.dumps([sys.executable, "-c", code])
            (root / "in" / "SOUL.md").write_text(_soul("command", f"command: {cmd}\n"))
            (root / "in" / "task.json").write_text(json.dumps({"title": "t"}))
            env = {
                "PATH": os.environ.get("PATH", ""),
                "NIO_KANBAN_IN": str(root / "in"),
                "NIO_KANBAN_OUT": str(root / "out"),
                "NIO_KANBAN_WORKDIR": str(root / "work"),
                "NIO_KANBAN_HEARTBEAT_S": "5",
                "NIO_KANBAN_TASK_TOKEN": SECRET_A,
                "OTHER_KEY": SECRET_B,
                "NIO_KANBAN_SECRET_NAMES": "NIO_KANBAN_TASK_TOKEN,OTHER_KEY",
            }
            subprocess.run([sys.executable, "-I", str(WORKER_ENTRY)], env=env, cwd=root / "work", timeout=60)
            raw = (root / "out" / "result.json").read_text() + (root / "out" / "experience.json").read_text()
            self.assertNotIn(SECRET_A, raw)
            self.assertNotIn(SECRET_B, raw)
            return (
                json.loads((root / "out" / "result.json").read_text()),
                json.loads((root / "out" / "experience.json").read_text()),
            )

    def test_stdout_on_success(self) -> None:
        res, _ = self._run("import os; print(os.environ['NIO_KANBAN_TASK_TOKEN'], os.environ['OTHER_KEY'])")
        self.assertEqual(res["status"], "completed")
        self.assertIn(REDACTED, res["result_payload"]["stdout"])

    def test_stderr_on_failure(self) -> None:
        res, exp = self._run(
            "import os, sys; sys.stderr.write(os.environ['NIO_KANBAN_TASK_TOKEN'] + os.environ['OTHER_KEY']); sys.exit(3)"
        )
        self.assertEqual(res["status"], "failed")
        self.assertIn(REDACTED, res["result_payload"]["stderr"])
        self.assertTrue(any(REDACTED in lesson for lesson in exp["lessons"]))


class _EchoSandbox(_ProcessSandbox):
    """Prozess-Sandbox, deren Prozess alle Geheimnisse auf stderr schreibt."""

    def _prepare(self, spec: SandboxSpec):
        code = "import os, sys; sys.stderr.write(' '.join(os.environ[k] for k in sorted(os.environ) if k.startswith('S_')))"
        return [sys.executable, "-c", code], {"PATH": os.environ.get("PATH", ""), **spec.secrets}, None

    def _stop_proc(self, proc) -> None:
        proc.kill()


class TestSandboxStderrRedacted(unittest.IsolatedAsyncioTestCase):
    async def test_stderr_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "out").mkdir()
            task = KanbanTask(id="t-000000000001", board_id="b1", title="t")
            worker = Worker(uid="w1-1111-1111-1111", name="W1", skills=[])
            spec = SandboxSpec(
                run_id="r1", task=task, worker=worker, run_dir=run_dir, env={},
                secrets={"S_A": SECRET_A, "S_B": SECRET_B}, image="x", deadline_s=30,
            )
            cfg = KanbanConfig(workspace_dir=run_dir / "ws", vault_dir=run_dir / "vault")

            async def hb() -> None:
                return None

            result = await _EchoSandbox(cfg).run(spec, on_heartbeat=hb)
            self.assertNotIn(SECRET_A, result.stderr_tail)
            self.assertNotIn(SECRET_B, result.stderr_tail)
            self.assertIn(REDACTED, result.stderr_tail)


class LeakySandbox:
    """Simuliert einen Worker, der out/ direkt mit allen Geheimnissen beschreibt."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.specs: list[SandboxSpec] = []

    async def run(self, spec, *, on_heartbeat):
        self.specs.append(spec)
        await on_heartbeat()
        out = spec.run_dir / "out"
        out.mkdir(parents=True, exist_ok=True)
        leak = " ".join(spec.secrets.values())
        (out / "result.json").write_text(json.dumps({
            "status": "failed" if self.fail else "completed",
            "result_payload": {"stdout": f"env: {leak}", "nested": [leak, {leak: leak}]},
            "reason": f"boom {leak}" if self.fail else "",
        }))
        (out / "experience.json").write_text(json.dumps({
            "summary": f"sum {leak}", "lessons": [f"lesson {leak}"], "skills_delta": [], "outcome": "success",
        }))
        (out / "SOUL.md").write_text(f"---\nruntime: noop\n---\n## Identity\n{leak}\n")
        return SandboxResult(
            exit_code=1 if self.fail else 0, timed_out=False, cancelled=False, out_dir=out, stderr_tail="",
        )

    async def cancel(self, run_id):
        pass


class TestDispatcherRedacts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"NIO_TEST_SECRET_A": SECRET_A, "NIO_TEST_SECRET_B": SECRET_B})
        self.env.start()
        self.store = SqliteKanbanStore(":memory:")
        await self.store.init()
        await self.store.create_board(KanbanBoard(id="b1", name="B1"))
        self.ledger = AuditLedger(self.store)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = KanbanConfig(
            workspace_dir=self.root / "ws",
            vault_dir=self.root / "vault",
            secret_allowlist=("NIO_TEST_SECRET_A", "NIO_TEST_SECRET_B"),
        )

    async def asyncTearDown(self) -> None:
        await self.store.close()
        self.tmp.cleanup()
        self.env.stop()

    def _dispatcher(self, sandbox) -> Dispatcher:
        bus = FakeBus()
        return Dispatcher(
            store=self.store,
            service=FakeService(self.store, bus, self.ledger),
            locks=FakeLocks(),
            heartbeats=FakeHeartbeats(),
            tokens=FakeTokens(),
            sandbox=sandbox,
            breaker=CircuitBreaker(
                store=self.store, ledger=self.ledger, notifier=NullNotifier(), bus_service=bus, threshold=3, cooldown_s=60,
            ),
            vault=FakeVault(),
            decomposer=ChecklistDecomposer(),
            config=self.config,
            owner_id="test_owner",
        )

    async def _run(self, runtime: str, *, fail: bool = False) -> tuple[LeakySandbox, str]:
        task = KanbanTask(id="t-000000000001", board_id="b1", title="T", status=TaskStatus.READY, required_skills=["py"])
        await self.store.create_task(task)
        await self.store.upsert_worker(Worker(
            uid="w1-1111-1111-1111", name="W1", skills=["py"], status=WorkerStatus.IDLE, soul_md=_soul(runtime),
        ))
        sandbox = LeakySandbox(fail=fail)
        await self._dispatcher(sandbox).tick(wait=True)
        self.assertEqual(len(sandbox.specs), 1)

        stored = await self.store.get_task(task.id)
        dump = json.dumps(stored.to_dict())
        dump += json.dumps([e.to_dict() if hasattr(e, "to_dict") else repr(e) for e in await self.store.list_experiences()])
        dump += json.dumps([repr(a) for a in await self.store.list_audit()])
        for path in (self.root / "ws").rglob("*"):
            if path.is_file():
                dump += path.read_text(errors="replace")
        return sandbox, dump

    def _assert_clean(self, sandbox: LeakySandbox, dump: str) -> None:
        for value in sandbox.specs[0].secrets.values():
            self.assertNotIn(value, dump)
        self.assertIn(REDACTED, dump)

    async def test_completed_run_redacts_everything(self) -> None:
        sandbox, dump = await self._run("opencode")
        spec = sandbox.specs[0]
        self.assertIn("NIO_KANBAN_TASK_TOKEN", spec.secrets)
        self.assertEqual(spec.secrets["NIO_TEST_SECRET_A"], SECRET_A)
        self._assert_clean(sandbox, dump)
        self.assertEqual((await self.store.get_task("t-000000000001")).status, TaskStatus.COMPLETED)

    async def test_failed_run_redacts_reason(self) -> None:
        sandbox, dump = await self._run("opencode", fail=True)
        self._assert_clean(sandbox, dump)

    async def test_command_worker_gets_no_task_token(self) -> None:
        sandbox, dump = await self._run("command")
        self.assertNotIn("NIO_KANBAN_TASK_TOKEN", sandbox.specs[0].secrets)
        self._assert_clean(sandbox, dump)


if __name__ == "__main__":
    unittest.main()
