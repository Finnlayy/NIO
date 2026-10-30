import unittest
from datetime import UTC, datetime, timedelta

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.breaker import CircuitBreaker
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import KanbanTask, TaskStatus
from orchestrator.kanban.notify import NullNotifier
from orchestrator.kanban.reaper import Reaper
from orchestrator.kanban.store import SqliteKanbanStore


class FakeBus:
    async def publish(self, event): pass

class FakeHeartbeats:
    def __init__(self): self.alive_ids = set()
    async def alive(self, t_id): return t_id in self.alive_ids

class FakeVault:
    def write_experience(self, exp, task): pass
    def append_history(self, worker_uid: str, text: str): pass

class TestReaper(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = SqliteKanbanStore(":memory:")
        await self.store.init()
        from orchestrator.kanban.models import KanbanBoard
        await self.store.create_board(KanbanBoard(id="b1", name="B1"))

        self.ledger = AuditLedger(self.store)
        self.bus = FakeBus()
        self.breaker = CircuitBreaker(store=self.store, ledger=self.ledger, notifier=NullNotifier(), bus_service=self.bus, threshold=3, cooldown_s=60)
        self.heartbeats = FakeHeartbeats()
        self.config = KanbanConfig(reaper_grace_s=5)

        self.reaper = Reaper(
            store=self.store,
            heartbeats=self.heartbeats,
            breaker=self.breaker,
            vault=FakeVault(),
            config=self.config
        )

    async def asyncTearDown(self):
        await self.store.close()

    async def test_reap_orphaned(self):
        old_time = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
        t = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.IN_PROGRESS, started_at=old_time)
        await self.store.create_task(t)

        reaped = await self.reaper.tick()
        self.assertEqual(len(reaped), 1)
        self.assertEqual(reaped[0], t.id)

        t2 = await self.store.get_task(t.id)
        self.assertEqual(t2.status, TaskStatus.READY) # Since threshold=3, first fail retries
        self.assertEqual(t2.attempts, 1)

    async def test_no_reap_alive(self):
        old_time = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
        t = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.IN_PROGRESS, started_at=old_time)
        await self.store.create_task(t)

        self.heartbeats.alive_ids.add(t.id)
        reaped = await self.reaper.tick()
        self.assertEqual(len(reaped), 0)

    async def test_no_reap_grace_period(self):
        recent_time = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
        t = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.IN_PROGRESS, started_at=recent_time)
        await self.store.create_task(t)

        reaped = await self.reaper.tick()
        self.assertEqual(len(reaped), 0)

    async def test_local_hang_is_cancelled_not_double_counted(self):
        class FakeDispatcher:
            def __init__(self):
                self._active = {"1": object()}
                self.cancelled = []

            async def cancel(self, task_id):
                self.cancelled.append(task_id)

        old_time = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
        await self.store.create_task(KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.IN_PROGRESS, started_at=old_time))
        self.reaper.dispatcher = FakeDispatcher()

        reaped = await self.reaper.tick()

        self.assertEqual(reaped, ["1"])
        self.assertEqual(self.reaper.dispatcher.cancelled, ["1"])
        t2 = await self.store.get_task("1")
        self.assertEqual(t2.status, TaskStatus.IN_PROGRESS)
        self.assertEqual(t2.attempts, 0)
