import asyncio
import os
import unittest
import uuid
from datetime import UTC, datetime

from orchestrator.kanban.audit import AuditDraft
from orchestrator.kanban.models import (
    KanbanBoard,
    KanbanTask,
    TaskStatus,
)
from orchestrator.kanban.store_pg import PostgresKanbanStore

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

PG_DSN = os.environ.get("NIO_KANBAN_TEST_PG_DSN")


@unittest.skipUnless(HAS_ASYNCPG and PG_DSN, "Requires asyncpg and NIO_KANBAN_TEST_PG_DSN")
class TestPostgresKanbanStore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.schema_name = f"t_{uuid.uuid4().hex}"

        # Connect to create schema
        conn = await asyncpg.connect(PG_DSN)
        await conn.execute(f"CREATE SCHEMA {self.schema_name}")
        await conn.close()

        self.store = PostgresKanbanStore(
            dsn=PG_DSN,
            server_settings={"search_path": self.schema_name}
        )
        await self.store.init()

    async def asyncTearDown(self) -> None:
        await self.store.close()
        conn = await asyncpg.connect(PG_DSN)
        await conn.execute(f"DROP SCHEMA {self.schema_name} CASCADE")
        await conn.close()

    async def test_migration_is_idempotent(self) -> None:
        # Should not throw any exception when running a second time
        await self.store.init()

        # Check that schema_version table exists and has rows
        async with self.store._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM schema_version")
            self.assertTrue(len(rows) > 0)

    async def test_cas_task_concurrent(self) -> None:
        board = KanbanBoard(id="b1", name="Board 1", created_at=datetime.now(UTC).isoformat())
        await self.store.create_board(board)

        task = KanbanTask(
            id="t1",
            board_id="b1",
            title="Task 1",
            status=TaskStatus.READY,
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )
        await self.store.create_task(task)

        async def try_acquire() -> KanbanTask | None:
            return await self.store.cas_task(
                task_id="t1",
                expected=TaskStatus.READY,
                changes={"status": TaskStatus.IN_PROGRESS}
            )

        results = await asyncio.gather(*(try_acquire() for _ in range(5)))
        successes = [r for r in results if r is not None]

        self.assertEqual(len(successes), 1)
        self.assertEqual(successes[0].status, TaskStatus.IN_PROGRESS)

    async def test_decomposition_promotion_rollup(self) -> None:
        board = KanbanBoard(id="b1", name="Board 1", created_at=datetime.now(UTC).isoformat())
        await self.store.create_board(board)

        parent = KanbanTask(
            id="p1",
            board_id="b1",
            title="Parent",
            status=TaskStatus.TRIAGE,
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )
        await self.store.create_task(parent)

        child1 = KanbanTask(
            id="c1",
            board_id="b1",
            title="Child 1",
            parent_id="p1",
            status=TaskStatus.BACKLOG,
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )
        child2 = KanbanTask(
            id="c2",
            board_id="b1",
            title="Child 2",
            parent_id="p1",
            status=TaskStatus.BACKLOG,
            dependencies=["c1"],
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )

        await self.store.apply_decomposition("p1", [child1, child2])

        p = await self.store.get_task("p1")
        self.assertEqual(p.status, TaskStatus.BACKLOG)
        self.assertTrue(p.is_rollup)

        promotable = await self.store.promotable_tasks()
        self.assertEqual(len(promotable), 1)
        self.assertEqual(promotable[0].id, "c1")

        await self.store.cas_task("c1", None, {"status": TaskStatus.COMPLETED})

        promotable = await self.store.promotable_tasks()
        self.assertEqual(len(promotable), 1)
        self.assertEqual(promotable[0].id, "c2")

        rollup_candidates = await self.store.rollup_candidates()
        self.assertEqual(len(rollup_candidates), 0)

        await self.store.cas_task("c2", None, {"status": TaskStatus.COMPLETED})

        rollup_candidates = await self.store.rollup_candidates()
        self.assertEqual(len(rollup_candidates), 1)
        self.assertEqual(rollup_candidates[0].id, "p1")

    async def test_audit_ledger_immutable(self) -> None:
        import asyncpg
        draft = AuditDraft(
            actor="test",
            action="do",
            category="system",
            subject="sys",
            payload={"key": "val"}
        )
        await self.store.append_audit(draft)

        entries = await self.store.list_audit()
        self.assertEqual(len(entries), 1)

        with self.assertRaises(asyncpg.exceptions.RaiseException):
            async with self.store._pool.acquire() as conn:
                await conn.execute("UPDATE audit_ledger SET actor = 'hacked'")

        with self.assertRaises(asyncpg.exceptions.RaiseException):
            async with self.store._pool.acquire() as conn:
                await conn.execute("DELETE FROM audit_ledger")

    async def test_concurrent_audit(self) -> None:
        async def append(i: int) -> None:
            draft = AuditDraft(
                actor=f"test{i}",
                action="do",
                category="system",
                subject="sys",
                payload={"i": i}
            )
            await self.store.append_audit(draft)

        await asyncio.gather(*(append(i) for i in range(10)))

        entries = await self.store.list_audit()
        self.assertEqual(len(entries), 10)

        # Verify hash chain
        # verify_chain expects an iterable of entry dicts? Let's check how it works
        # Actually in WP-01 instructions: AuditLedger(store).verify() == [] nach 10 parallelen appends
        from orchestrator.kanban.audit import AuditLedger

        ledger = AuditLedger(self.store)
        errors = await ledger.verify()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
