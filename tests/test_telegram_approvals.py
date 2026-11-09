import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from orchestrator.kanban.audit import AuditLedger
from orchestrator.telegram.approvals import Approvals, Conflict, NotAllowed, RateLimited, SuggestionNotFound
from orchestrator.telegram.client import FakeTelegramClient, TelegramFloodWait
from orchestrator.telegram.config import TelegramConfig
from orchestrator.telegram.models import ApprovalStatus, Suggestion, SuggestionStatus
from orchestrator.telegram.store import SqliteTelegramStore
from tests.test_kanban_service_tools import FakeKanbanStore

FEED, BOT = 10, 20
T0 = "2026-01-01T12:00:00.000Z"


class Base(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = SqliteTelegramStore(Path(self.td.name) / "t.db")
        await self.store.init()
        await self.store.allow(BOT)
        self.config = TelegramConfig.from_env(
            {
                "NIO_TELEGRAM_API_HASH": "hash-secret",
                "NIO_TELEGRAM_LLM_API_KEY": "llm-secret",
                "NIO_TELEGRAM_SEND_RATE": "2",
                "NIO_TELEGRAM_CALLBACK_ALLOWLIST": "Orch.Local",
            },
            repo_root=Path(self.td.name),
        )
        self.client = FakeTelegramClient()
        self.audit_store = FakeKanbanStore()
        self.now = T0
        self.posted = []
        self.approvals = self.build()

    def build(self, **kw):
        kw.setdefault("poster", self.post)
        return Approvals(self.store, self.client, self.config, ledger=AuditLedger(self.audit_store), clock=lambda: self.now, **kw)

    async def post(self, url, payload):
        self.posted.append((url, payload))

    async def asyncTearDown(self):
        await self.store.close()
        self.td.cleanup()

    async def suggestion(self, sid="s1", target=BOT, text="/glint BTC BULLISH 10.0"):
        await self.store.add_suggestion(Suggestion(sid, FEED, target, text, 1, "rules", SuggestionStatus.PENDING, T0, None, None))
        return sid

    def actions(self):
        return [e.action for e in self.audit_store.audit]


class TestApprove(Base):
    async def test_sends_once_and_audits(self):
        sid = await self.suggestion()
        result = await self.approvals.approve(sid, actor="op")
        self.assertEqual(result.status, SuggestionStatus.SENT)
        self.assertEqual(result.decided_at, T0)
        self.assertEqual(self.client.sent, [(BOT, "/glint BTC BULLISH 10.0")])
        self.assertEqual(self.actions(), ["telegram.sent"])
        self.assertEqual(self.audit_store.audit[0].category, "trading")

    async def test_concurrent_double_approve_sends_once(self):
        sid = await self.suggestion()
        results = await asyncio.gather(*(self.approvals.approve(sid, actor="op") for _ in range(5)), return_exceptions=True)
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(sum(isinstance(r, Suggestion) for r in results), 1)
        self.assertTrue(all(isinstance(r, (Suggestion, Conflict)) for r in results))

    async def test_second_approve_conflicts(self):
        sid = await self.suggestion()
        await self.approvals.approve(sid, actor="op")
        with self.assertRaises(Conflict):
            await self.approvals.approve(sid, actor="op")

    async def test_unknown(self):
        with self.assertRaises(SuggestionNotFound):
            await self.approvals.approve("nope", actor="op")

    async def test_not_allowlisted(self):
        sid = await self.suggestion(target=666)
        with self.assertRaises(NotAllowed):
            await self.approvals.approve(sid, actor="op")
        self.assertEqual((await self.store.get_suggestion(sid)).status, SuggestionStatus.PENDING)
        self.assertEqual(self.client.sent, [])
        self.assertEqual(self.actions(), ["telegram.send_refused"])

    async def test_allowlist_removed_after_creation(self):
        sid = await self.suggestion()
        await self.store.disallow(BOT)
        with self.assertRaises(NotAllowed):
            await self.approvals.approve(sid, actor="op")

    async def test_rate_limit(self):
        for i in range(2):
            await self.approvals.approve(await self.suggestion(f"s{i}"), actor="op")
        self.now = "2026-01-01T12:10:00.000Z"
        sid = await self.suggestion("s9")
        with self.assertRaises(RateLimited) as ctx:
            await self.approvals.approve(sid, actor="op")
        self.assertEqual(ctx.exception.retry_after_s, 50 * 60)
        self.assertEqual((await self.store.get_suggestion(sid)).status, SuggestionStatus.PENDING)
        self.assertEqual(len(self.client.sent), 2)

        self.now = "2026-01-01T13:00:01.000Z"
        await self.approvals.approve(sid, actor="op")
        self.assertEqual(len(self.client.sent), 3)

    async def test_concurrent_approvals_cannot_overrun_rate_limit(self):
        real_send = self.client.send

        async def slow_send(peer, text):
            await asyncio.sleep(0.01)
            return await real_send(peer, text)

        self.client.send = slow_send
        sids = [await self.suggestion(f"s{i}") for i in range(5)]
        results = await asyncio.gather(*(self.approvals.approve(sid, actor="op") for sid in sids), return_exceptions=True)
        self.assertEqual(len(self.client.sent), 2)
        self.assertEqual(sum(isinstance(r, RateLimited) for r in results), 3)

    async def test_rate_limit_is_per_target(self):
        await self.store.allow(21)
        for i in range(2):
            await self.approvals.approve(await self.suggestion(f"s{i}"), actor="op")
        await self.approvals.approve(await self.suggestion("other", target=21), actor="op")
        self.assertEqual(len(self.client.sent), 3)

    async def test_send_failure_then_retry(self):
        async def broken(peer, text):
            raise RuntimeError("netz weg")

        sid = await self.suggestion()
        real_send, self.client.send = self.client.send, broken
        failed = await self.approvals.approve(sid, actor="op")
        self.assertEqual(failed.status, SuggestionStatus.FAILED)
        self.assertEqual(failed.error, "RuntimeError: netz weg")
        self.assertEqual(self.actions(), ["telegram.send_failed"])
        self.assertEqual(await self.store.count_sends_since(BOT, "2000"), 0)

        pending = await self.approvals.retry(sid)
        self.assertEqual((pending.status, pending.error), (SuggestionStatus.PENDING, None))
        self.client.send = real_send
        self.assertEqual((await self.approvals.approve(sid, actor="op")).status, SuggestionStatus.SENT)

    async def test_flood_wait_marks_failed_and_reraises(self):
        self.client.flood_wait_after = 0
        sid = await self.suggestion()
        with self.assertRaises(TelegramFloodWait):
            await self.approvals.approve(sid, actor="op")
        self.assertEqual((await self.store.get_suggestion(sid)).status, SuggestionStatus.FAILED)

    async def test_retry_needs_failed(self):
        sid = await self.suggestion()
        with self.assertRaises(Conflict):
            await self.approvals.retry(sid)

    async def test_dismiss(self):
        sid = await self.suggestion()
        self.assertEqual((await self.approvals.dismiss(sid)).status, SuggestionStatus.DISMISSED)
        with self.assertRaises(Conflict):
            await self.approvals.dismiss(sid)
        with self.assertRaises(Conflict):
            await self.approvals.approve(sid, actor="op")


class TestOrchestratorApprovals(Base):
    async def test_request_validates_callback(self):
        for url in (
            "http://evil.local/x",
            "ftp://orch.local/x",
            "file:///etc/passwd",
            "http://orch.local@evil.local/x",
            "http://evil.local\\@orch.local/x",
            "http://[bad/x",
            "orch.local/x",
        ):
            with self.assertRaises(ValueError, msg=url):
                await self.approvals.request("t", "d", callback_url=url)
        ok = await self.approvals.request("t", "d", callback_url="https://ORCH.local:8080/cb")
        self.assertEqual(ok.status, ApprovalStatus.PENDING)
        self.assertEqual(self.actions(), ["telegram.approval_requested"])

    async def test_request_limits(self):
        for title, detail in (("  ", "d"), ("x" * 201, "d"), ("t", "x" * 2001)):
            with self.assertRaises(ValueError):
                await self.approvals.request(title, detail)

    async def test_decide_posts_callback_once(self):
        a = await self.approvals.request("t", "d", request_id="r1", callback_url="http://orch.local/cb")
        decided = await self.approvals.decide(a.id, True, actor="op")
        self.assertEqual(decided.status, ApprovalStatus.APPROVED)
        self.assertEqual(
            self.posted,
            [("http://orch.local/cb", {"request_id": "r1", "approval_id": a.id, "approved": True, "decided_at": T0})],
        )
        with self.assertRaises(Conflict):
            await self.approvals.decide(a.id, False, actor="op")
        self.assertEqual(len(self.posted), 1)

    async def test_rejected_without_request_id(self):
        a = await self.approvals.request("t", "d", callback_url="http://orch.local/cb")
        await self.approvals.decide(a.id, False, actor="op")
        self.assertEqual(self.posted[0][1]["request_id"], a.id)
        self.assertFalse(self.posted[0][1]["approved"])

    async def test_callback_failure_ignored(self):
        async def broken(url, payload):
            raise OSError("weg")

        a = await self.approvals.request("t", "d", callback_url="http://orch.local/cb")
        decided = await self.build(poster=broken).decide(a.id, True, actor="op")
        self.assertEqual(decided.status, ApprovalStatus.APPROVED)

    async def test_callback_revalidated_at_decide(self):
        a = await self.approvals.request("t", "d", callback_url="http://orch.local/cb")
        self.config = replace(self.config, callback_allowlist=())
        await self.build().decide(a.id, True, actor="op")
        self.assertEqual(self.posted, [])

    async def test_get_and_pending(self):
        a = await self.approvals.request("t", "d")
        self.assertEqual((await self.approvals.get(a.id)).id, a.id)
        self.assertEqual([p.id for p in await self.approvals.pending()], [a.id])
        await self.approvals.decide(a.id, False, actor="op")
        self.assertEqual(await self.approvals.pending(), [])

    async def test_audit_has_no_secrets(self):
        sid = await self.suggestion()
        await self.approvals.approve(sid, actor="op")
        a = await self.approvals.request("t", "d", callback_url="http://orch.local/cb?token=abc")
        await self.approvals.decide(a.id, True, actor="op")
        dump = json.dumps([e.payload for e in self.audit_store.audit])
        for secret in ("hash-secret", "llm-secret", "token=abc"):
            self.assertNotIn(secret, dump)
