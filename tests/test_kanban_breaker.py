import unittest

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.breaker import CircuitBreaker
from orchestrator.kanban.models import KanbanTask, TaskStatus, Worker
from orchestrator.kanban.notify import NullNotifier
from orchestrator.kanban.store import SqliteKanbanStore


class FakeBus:
    async def publish(self, event): pass

class TestCircuitBreaker(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = SqliteKanbanStore(":memory:")
        await self.store.init()
        from orchestrator.kanban.models import KanbanBoard
        await self.store.create_board(KanbanBoard(id="b1", name="B1"))

        self.ledger = AuditLedger(self.store)
        self.bus = FakeBus()
        self.breaker = CircuitBreaker(
            store=self.store,
            ledger=self.ledger,
            notifier=NullNotifier(),
            bus_service=self.bus,
            threshold=3,
            cooldown_s=60
        )

    async def asyncTearDown(self):
        await self.store.close()

    async def test_record_failure_retry(self):
        worker = Worker(uid="w1-1111-1111-1111", name="W1")
        await self.store.upsert_worker(worker)
        task = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.IN_PROGRESS, assigned_worker_uid="w1-1111-1111-1111")
        await self.store.create_task(task)

        triggered = await self.breaker.record_failure(task.id, "w1-1111-1111-1111", "reason1")
        self.assertFalse(triggered)

        t2 = await self.store.get_task(task.id)
        self.assertEqual(t2.status, TaskStatus.READY)
        self.assertEqual(t2.attempts, 1)
        self.assertIsNone(t2.assigned_worker_uid)

        w2 = await self.store.get_worker("w1-1111-1111-1111")
        self.assertEqual(w2.fail_count, 1)

    async def test_record_failure_trigger(self):
        worker = Worker(uid="w1-1111-1111-1111", name="W1", fail_count=2)
        await self.store.upsert_worker(worker)
        task = KanbanTask(id="1", board_id="b1", title="T", status=TaskStatus.IN_PROGRESS, assigned_worker_uid="w1-1111-1111-1111", attempts=2)
        await self.store.create_task(task)

        triggered = await self.breaker.record_failure(task.id, "w1-1111-1111-1111", "reason1")
        self.assertTrue(triggered)

        t2 = await self.store.get_task(task.id)
        self.assertEqual(t2.status, TaskStatus.BLOCKED)
        self.assertEqual(t2.attempts, 3)
        self.assertTrue(t2.block_reason.startswith("circuit breaker:"))

        w2 = await self.store.get_worker("w1-1111-1111-1111")
        self.assertEqual(w2.fail_count, 0)
        self.assertIsNotNone(w2.breaker_open_until)
        self.assertTrue(self.breaker.is_open(w2))

    async def test_record_success(self):
        worker = Worker(uid="w1-1111-1111-1111", name="W1", fail_count=2)
        await self.store.upsert_worker(worker)
        await self.breaker.record_success("w1-1111-1111-1111")
        w2 = await self.store.get_worker("w1-1111-1111-1111")
        self.assertEqual(w2.fail_count, 0)
