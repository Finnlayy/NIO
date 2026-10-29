import asyncio
import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.breaker import CircuitBreaker
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.decomposer import ChecklistDecomposer
from orchestrator.kanban.dispatcher import Dispatcher
from orchestrator.kanban.models import KanbanTask, TaskStatus, Worker, WorkerStatus
from orchestrator.kanban.notify import NullNotifier
from orchestrator.kanban.sandbox import SandboxResult
from orchestrator.kanban.store import SqliteKanbanStore


class FakeLocks:
    def __init__(self): self.locks = {}
    async def acquire(self, key, owner, ttl):
        if key in self.locks:
            return False
        self.locks[key] = owner
        return True
    async def release(self, key, owner):
        if self.locks.get(key) == owner:
            del self.locks[key]
            return True
        return False

class FakeHeartbeats:
    def __init__(self): self.beats = {}
    async def beat(self, t_id, ttl, *, worker_uid=""): self.beats[t_id] = worker_uid
    async def alive(self, t_id): return t_id in self.beats
    async def clear(self, t_id): self.beats.pop(t_id, None)

class FakeTokens:
    async def put(self, t, c, ttl): pass
    async def get(self, t): return None
    async def revoke(self, t): pass

class FakeSandbox:
    def __init__(self): self.fail = False
    async def run(self, spec, *, on_heartbeat):
        # Spielt den Dateivertrag nach: der Worker hinterlaesst out/result.json.
        await on_heartbeat()
        out = spec.run_dir / "out"
        out.mkdir(parents=True, exist_ok=True)
        status = "failed" if self.fail else "completed"
        (out / "result.json").write_text(json.dumps({"status": status, "result_payload": {"ok": not self.fail}, "reason": ""}))
        return SandboxResult(exit_code=1 if self.fail else 0, timed_out=False, cancelled=False, out_dir=out, stderr_tail="")
    async def cancel(self, run_id): pass

class FakeBus:
    async def publish(self, event): pass

@dataclass
class FakeService:
    store: any
    bus: any
    ledger: any
    async def complete(self, task_id, payload, *, actor):
        await self.store.cas_task(task_id, TaskStatus.IN_PROGRESS, {"status": TaskStatus.COMPLETED, "result_payload": payload})
    async def block(self, task_id, reason, *, actor):
        await self.store.cas_task(task_id, TaskStatus.IN_PROGRESS, {"status": TaskStatus.BLOCKED, "block_reason": reason})

class FakeVault:
    def write_experience(self, exp, task): pass
    def append_history(self, worker_uid: str, text: str): pass
    def write_task(self, task): pass

class TestDispatcher(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = SqliteKanbanStore(":memory:")
        await self.store.init()
        from orchestrator.kanban.models import KanbanBoard
        await self.store.create_board(KanbanBoard(id="b1", name="B1"))

        self.ledger = AuditLedger(self.store)
        self.bus = FakeBus()
        self.service = FakeService(self.store, self.bus, self.ledger)
        self.locks = FakeLocks()
        self.breaker = CircuitBreaker(store=self.store, ledger=self.ledger, notifier=NullNotifier(), bus_service=self.bus, threshold=3, cooldown_s=60)
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.config = KanbanConfig(workspace_dir=root / "ws", vault_dir=root / "vault")

        self.dispatcher = Dispatcher(
            store=self.store,
            service=self.service,
            locks=self.locks,
            heartbeats=FakeHeartbeats(),
            tokens=FakeTokens(),
            sandbox=FakeSandbox(),
            breaker=self.breaker,
            vault=FakeVault(),
            decomposer=ChecklistDecomposer(),
            config=self.config,
            owner_id="test_owner"
        )

    async def asyncTearDown(self):
        await self.store.close()
        self.tmp.cleanup()

    async def test_triage_and_promote(self):
        t1 = KanbanTask(id="1", board_id="b1", title="t1", status=TaskStatus.TRIAGE, description="- [ ] child")
        await self.store.create_task(t1)

        # Ein Tick zerlegt und befoerdert das Kind sofort (kein Worker -> bleibt ready).
        report = await self.dispatcher.tick()
        self.assertEqual(report.decomposed, 1)
        self.assertEqual(report.promoted, 1)

        tasks = await self.store.list_tasks(board_id=t1.board_id)
        self.assertEqual(len(tasks), 2)
        child = next(c for c in tasks if c.parent_id == t1.id)
        # Kind-IDs muessen dem normalen Task-ID-Format folgen (der Vault lehnt alles andere ab).
        self.assertRegex(child.id, r"^t-[0-9a-f]{12}$")
        self.assertEqual((await self.store.get_task(child.id)).status, TaskStatus.READY)
        parent = await self.store.get_task(t1.id)
        self.assertEqual(parent.status, TaskStatus.BACKLOG)
        self.assertTrue(parent.is_rollup)

    async def test_assign_and_run(self):
        task = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.READY, required_skills=["python"])
        await self.store.create_task(task)
        worker = Worker(uid="w1-1111-1111-1111", name="W1", skills=["python"], status=WorkerStatus.IDLE)
        await self.store.upsert_worker(worker)

        report = await self.dispatcher.tick(wait=True)
        self.assertEqual(report.assigned, 1)

        t2 = await self.store.get_task(task.id)
        # Sandbox returns complete
        self.assertEqual(t2.status, TaskStatus.COMPLETED)
        w2 = await self.store.get_worker("w1-1111-1111-1111")
        self.assertEqual(w2.status, WorkerStatus.IDLE)

    async def test_concurrent_dispatchers(self):
        task = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.READY)
        await self.store.create_task(task)
        worker = Worker(uid="w1-1111-1111-1111", name="W1", status=WorkerStatus.IDLE)
        await self.store.upsert_worker(worker)

        d2 = Dispatcher(
            store=self.store, service=self.service, locks=self.locks, heartbeats=self.dispatcher.heartbeats,
            tokens=self.dispatcher.tokens, sandbox=self.dispatcher.sandbox, breaker=self.breaker,
            vault=self.dispatcher.vault, decomposer=self.dispatcher.decomposer, config=self.config, owner_id="owner2"
        )

        r1, r2 = await asyncio.gather(self.dispatcher.tick(wait=True), d2.tick(wait=True))

        # Only one should have assigned
        self.assertEqual(r1.assigned + r2.assigned, 1)

    async def test_sandbox_exception_releases_locks(self):
        class CrashingSandbox:
            async def run(self, *a, **k): raise ValueError("Crash")
            async def cancel(self, run_id): pass

        self.dispatcher.sandbox = CrashingSandbox()

        task = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.READY)
        await self.store.create_task(task)
        worker = Worker(uid="w1-1111-1111-1111", name="W1", status=WorkerStatus.IDLE)
        await self.store.upsert_worker(worker)

        await self.dispatcher.tick(wait=True)

        t2 = await self.store.get_task(task.id)
        # Error -> breaker triggered (retry) -> READY
        self.assertEqual(t2.status, TaskStatus.READY)
        w2 = await self.store.get_worker("w1-1111-1111-1111")
        self.assertEqual(w2.status, WorkerStatus.IDLE)

        # Locks must be released
        self.assertNotIn(f"task:{task.id}", self.locks.locks)
        self.assertNotIn(f"worker:{worker.uid}", self.locks.locks)


    async def test_worktree_failure_cleans_up(self):
        worker = Worker(uid="w1-1111-1111-1111", name="W1", status=WorkerStatus.IDLE)
        await self.store.upsert_worker(worker)
        task = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.READY,
                          workspace_repo=str(Path(self.tmp.name) / "kein-repo"))
        await self.store.create_task(task)

        await self.dispatcher.tick(wait=True)

        t2 = await self.store.get_task(task.id)
        self.assertEqual(t2.status, TaskStatus.READY)
        self.assertEqual(t2.attempts, 1)
        self.assertEqual((await self.store.get_worker(worker.uid)).status, WorkerStatus.IDLE)
        self.assertEqual(self.locks.locks, {})
