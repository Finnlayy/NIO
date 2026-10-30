import asyncio
import tempfile
import unittest
from pathlib import Path

from orchestrator.telegram.models import (
    ApprovalRequest,
    ApprovalStatus,
    Direction,
    InvalidTransitionError,
    Signal,
    Suggestion,
    SuggestionStatus,
    TgMessage,
)
from orchestrator.telegram.store import SqliteTelegramStore


class TestTelegramStore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # use file db to prevent sqlite in-memory shared cache thread weirdness during CAS
        self.td = tempfile.TemporaryDirectory()
        db_path = Path(self.td.name) / "test.db"
        self.store = SqliteTelegramStore(db_path)
        await self.store.init()

    async def asyncTearDown(self):
        await self.store.close()
        self.td.cleanup()

    async def test_init_idempotent(self):
        await self.store.init()  # Second time should not fail

    async def test_add_messages_dedupe(self):
        msgs = [
            TgMessage(1, 1, "S", "T1", "2023-01-01T00:00:00Z", False, False),
            TgMessage(1, 2, "S", "T2", "2023-01-01T00:01:00Z", False, False),
        ]
        added = await self.store.add_messages(msgs)
        self.assertEqual(len(added), 2)

        # Add again with one new
        msgs2 = [
            TgMessage(1, 2, "S", "T2", "2023-01-01T00:01:00Z", False, False),
            TgMessage(1, 3, "S", "T3", "2023-01-01T00:02:00Z", False, False),
        ]
        added2 = await self.store.add_messages(msgs2)
        self.assertEqual(len(added2), 1)
        self.assertEqual(added2[0].msg_id, 3)

        recent = await self.store.recent_messages([1], 10)
        self.assertEqual(len(recent), 3)

    async def test_cursor_forward_only(self):
        self.assertEqual(await self.store.get_cursor(1), 0)
        await self.store.advance_cursor(1, 10)
        self.assertEqual(await self.store.get_cursor(1), 10)
        await self.store.advance_cursor(1, 5)  # Should not go backwards
        self.assertEqual(await self.store.get_cursor(1), 10)
        await self.store.advance_cursor(1, 15)
        self.assertEqual(await self.store.get_cursor(1), 15)

    async def test_monitored_pairings_allowlist(self):
        await self.store.add_monitored(1)
        await self.store.add_monitored(2)
        self.assertEqual(set(await self.store.list_monitored()), {1, 2})
        await self.store.remove_monitored(1)
        self.assertEqual(await self.store.list_monitored(), [2])

        await self.store.set_pairing(1, 10)
        await self.store.set_pairing(2, 20)
        self.assertEqual(await self.store.get_pairing(1), 10)
        self.assertEqual(await self.store.list_pairings(), {1: 10, 2: 20})
        await self.store.remove_pairing(1)
        self.assertEqual(await self.store.get_pairing(1), None)

        await self.store.allow(123)
        await self.store.allow("@user")
        self.assertTrue(await self.store.is_allowed(123))
        self.assertTrue(await self.store.is_allowed("@user"))
        self.assertFalse(await self.store.is_allowed(456))
        self.assertEqual(set(await self.store.list_allowed()), {123, "@user"})
        await self.store.disallow(123)
        self.assertFalse(await self.store.is_allowed(123))

    async def test_suggestion_cas_concurrent(self):
        s = Suggestion("1", 1, 2, "text", 10, "llm", SuggestionStatus.PENDING, "now", None, None)
        await self.store.add_suggestion(s)

        # Concurrent approve
        async def approve():
            return await self.store.cas_suggestion("1", SuggestionStatus.PENDING, {"status": SuggestionStatus.SENDING})

        results = await asyncio.gather(approve(), approve())
        winners = [r for r in results if r is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0].status, SuggestionStatus.SENDING)

        # Test transition rejection
        with self.assertRaises(InvalidTransitionError):
            await self.store.cas_suggestion("1", SuggestionStatus.SENDING, {"status": SuggestionStatus.PENDING})

    async def test_approval_cas(self):
        a = ApprovalRequest("1", None, "t", "d", ApprovalStatus.PENDING, "now", None, None)
        await self.store.add_approval(a)

        res = await self.store.cas_approval("1", ApprovalStatus.PENDING, {"status": ApprovalStatus.APPROVED})
        self.assertIsNotNone(res)
        self.assertEqual(res.status, ApprovalStatus.APPROVED)

        # Already approved, expected PENDING -> None
        res2 = await self.store.cas_approval("1", ApprovalStatus.PENDING, {"status": ApprovalStatus.REJECTED})
        self.assertIsNone(res2)

    async def test_signals(self):
        s1 = Signal("1", "BTC", Direction.BULLISH, 8, 1, 10, "ev", "2023-01-01", None)
        s2 = Signal("2", "BTC", Direction.BULLISH, 9, 1, 11, "ev", "2023-01-02", None)
        await self.store.add_signal(s1)
        await self.store.add_signal(s2)

        last = await self.store.last_signal("BTC", Direction.BULLISH)
        self.assertEqual(last.id, "2")

        await self.store.set_signal_task("1", "task-1")
        sigs = await self.store.list_signals(symbol="BTC")
        s1_updated = next(s for s in sigs if s.id == "1")
        self.assertEqual(s1_updated.kanban_task_id, "task-1")

    async def test_sends(self):
        await self.store.record_send(1, "2023-01-01T10:00:00Z")
        await self.store.record_send(1, "2023-01-01T10:10:00Z")
        await self.store.record_send(2, "2023-01-01T10:20:00Z")

        c = await self.store.count_sends_since(1, "2023-01-01T10:05:00Z")
        self.assertEqual(c, 1)

    async def test_file_db_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test2.db"
            store1 = SqliteTelegramStore(db_path)
            await store1.init()
            await store1.allow(123)
            await store1.close()

            store2 = SqliteTelegramStore(db_path)
            await store2.init()
            self.assertTrue(await store2.is_allowed(123))
            await store2.close()

    async def test_recent_messages_newest_last(self):
        await self.store.add_messages(
            [
                TgMessage(1, 2, "S", "B", "2026-01-01T00:02:00.000Z", False, False),
                TgMessage(1, 1, "S", "A", "2026-01-01T00:01:00.000Z", False, False),
                TgMessage(2, 9, "S", "X", "2026-01-01T00:03:00.000Z", False, True),
            ]
        )
        recent = await self.store.recent_messages([1], 10)
        self.assertEqual([m.text for m in recent], ["A", "B"])
        self.assertEqual([m.text for m in await self.store.recent_messages(None, 2)], ["B", "X"])
        self.assertTrue((await self.store.recent_messages([2], 1))[0].is_bot)
        self.assertEqual(await self.store.recent_messages([], 5), [])

    async def test_allowlist_normalised(self):
        await self.store.allow("@GlintBot")
        self.assertTrue(await self.store.is_allowed("@glintbot"))
        self.assertTrue(await self.store.is_allowed("GLINTBOT"))
        await self.store.allow("-100123")
        self.assertTrue(await self.store.is_allowed(-100123))
        self.assertEqual(set(await self.store.list_allowed()), {"@glintbot", -100123})

    async def test_cas_rejects_unknown_columns(self):
        s = Suggestion("s1", 1, 2, "text", None, "rules", SuggestionStatus.PENDING, "now", None, None)
        await self.store.add_suggestion(s)
        with self.assertRaises(ValueError):
            await self.store.cas_suggestion("s1", SuggestionStatus.PENDING, {"target_peer": 666})
        with self.assertRaises(ValueError):
            await self.store.cas_suggestion("s1", SuggestionStatus.PENDING, {"status=status, id": 1})
        got = await self.store.get_suggestion("s1")
        assert got is not None
        self.assertEqual(got.target_peer, 2)

    async def test_cas_full_cycle(self):
        s = Suggestion("s2", 1, 2, "t", None, "rules", SuggestionStatus.PENDING, "now", None, None)
        await self.store.add_suggestion(s)
        sending = await self.store.cas_suggestion("s2", SuggestionStatus.PENDING, {"status": SuggestionStatus.SENDING})
        assert sending is not None
        sent = await self.store.cas_suggestion("s2", SuggestionStatus.SENDING, {"status": SuggestionStatus.SENT, "decided_at": "later"})
        assert sent is not None
        self.assertEqual((sent.status, sent.decided_at), (SuggestionStatus.SENT, "later"))
        self.assertIsNone(await self.store.cas_suggestion("missing", SuggestionStatus.PENDING, {}))

    async def test_memory_store_and_parent_dir(self):
        mem = SqliteTelegramStore(":memory:")
        await mem.init()
        await mem.add_monitored(5)
        self.assertEqual(await mem.list_monitored(), [5])
        await mem.close()

        nested = Path(self.td.name) / "a" / "b" / "telegram.db"
        store = SqliteTelegramStore(nested)
        await store.init()
        await store.init()
        await store.close()
        self.assertTrue(nested.exists())


if __name__ == "__main__":
    unittest.main()
