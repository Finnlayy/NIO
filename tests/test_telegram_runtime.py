import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.runtime import build_runtime
from orchestrator.telegram import runtime as tg_runtime
from orchestrator.telegram.client import FakeTelegramClient
from orchestrator.telegram.config import TelegramConfig
from orchestrator.telegram.llm import ScriptedTextLLM
from orchestrator.telegram.models import Suggestion, SuggestionStatus, TgMessage
from orchestrator.telegram.runtime import EventHub, attach_telegram, build_telegram_runtime
from orchestrator.telegram.symbols import SymbolIndex

FEED, BOT = 10, 20
T0 = "2026-01-01T12:00:00.000Z"


def fetcher(_url):
    return {
        "error": [],
        "result": {"XBTUSD": {"wsname": "XBT/USD", "status": "online"}, "ETHUSD": {"wsname": "ETH/USD", "status": "online"}},
    }


def msg(msg_id, text, peer=FEED):
    return TgMessage(peer, msg_id, "feed", text, T0, False, False)


class Base(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.kanban = await build_runtime(
            KanbanConfig(
                repo_root=self.root,
                store="sqlite",
                sqlite_path=self.root / "kanban.db",
                bus="memory",
                sandbox="subprocess",
                workspace_dir=self.root / "ws",
                vault_dir=self.root / "vault",
                api_token="op",
            )
        )
        self.board = await self.kanban.service.create_board("b", actor="test")
        self.config = TelegramConfig.from_env(
            {
                "NIO_TELEGRAM_API_ID": "1",
                "NIO_TELEGRAM_API_HASH": "hash-secret",
                "NIO_TELEGRAM_KANBAN_BOARD": self.board.id,
                "NIO_TELEGRAM_KANBAN_MIN_STRENGTH": "4",
            },
            repo_root=self.root,
        )
        self.client = FakeTelegramClient()
        self.client.fake_names["@glint_bot"] = BOT
        self.tg = await build_telegram_runtime(
            self.config, kanban=self.kanban, client=self.client, symbols=SymbolIndex(self.root / "s.json", fetcher)
        )
        await self.tg.symbols.ensure()

    async def asyncTearDown(self):
        await self.tg.close()
        await self.kanban.close()
        self.td.cleanup()


class TestPeers(Base):
    async def test_new_monitor_skips_history(self):
        self.client.fake_messages.append(msg(5, "BTC bullish breakout rally"))
        await self.tg.monitor(FEED, actor="t")
        report = await self.tg.gather.tick()
        self.assertEqual(report.fetched, 0)
        self.assertEqual(await self.tg.store.list_signals(), [])
        await self.client.push(msg(6, "BTC bullish breakout rally"))
        self.assertEqual((await self.tg.gather.tick()).fetched, 1)
        self.assertEqual(len(await self.tg.store.list_signals()), 1)

    async def test_monitor_twice_keeps_cursor(self):
        await self.tg.monitor(FEED, actor="t")
        self.client.fake_messages.append(msg(5, "unseen"))
        await self.tg.monitor(FEED, actor="t")
        self.assertEqual(await self.tg.store.get_cursor(FEED), 0)

    async def test_allow_stores_numeric_id_for_name(self):
        self.assertEqual(await self.tg.allow("@Glint_Bot", actor="t"), BOT)
        self.assertEqual(await self.tg.store.list_allowed(), [BOT])

    async def test_unknown_name_is_refused(self):
        with self.assertRaises(ValueError):
            await self.tg.allow("@nobody", actor="t")
        self.assertEqual(await self.tg.store.list_allowed(), [])

    async def test_pair_resolves_and_refuses_self(self):
        self.assertEqual(await self.tg.pair(FEED, "@glint_bot", actor="t"), (FEED, BOT))
        with self.assertRaises(ValueError):
            await self.tg.pair(BOT, "@glint_bot", actor="t")

    async def test_changes_are_audited(self):
        await self.tg.allow(BOT, actor="op")
        await self.tg.monitor(FEED, actor="op")
        await self.tg.pair(FEED, BOT, actor="op")
        entries = await self.kanban.ledger.entries(limit=100)
        self.assertLessEqual({"telegram.allow", "telegram.monitor", "telegram.pair"}, {e.action for e in entries})


class TestFlow(Base):
    async def test_feed_to_suggestion_and_task(self):
        await self.tg.monitor(FEED, actor="t")
        await self.tg.allow(BOT, actor="t")
        await self.tg.pair(FEED, BOT, actor="t")
        await self.client.push(msg(1, "BTC bullish breakout"))
        await self.tg.gather.tick()
        suggestions = await self.tg.store.list_suggestions()
        self.assertEqual([s.target_peer for s in suggestions], [BOT])
        tasks = await self.kanban.store.list_tasks(board_id=self.board.id)
        self.assertEqual(len(tasks), 1)
        sent = await self.tg.approvals.approve(suggestions[0].id, actor="t")
        self.assertIs(sent.status, SuggestionStatus.SENT)
        self.assertEqual(self.client.sent, [(BOT, suggestions[0].text)])
        self.assertEqual(await self.kanban.ledger.verify(), [])

    async def test_status_reports_quota_of_paired_targets(self):
        await self.tg.pair(FEED, BOT, actor="t")
        await self.tg.store.record_send(BOT, self.tg.clock())
        status = await self.tg.status()
        self.assertEqual(status["send_quota"], [{"target": BOT, "used": 1, "limit": 6}])

    async def test_live_message_is_published(self):
        await self.tg.monitor(FEED, actor="t")
        self.tg.gather.attach_live()

        async def first():
            async for item in self.tg.hub.subscribe(1.0):
                return item

        reader = asyncio.create_task(first())
        await asyncio.sleep(0)
        await self.client.push(msg(1, "hello"))
        item = await asyncio.wait_for(reader, 2)
        self.assertEqual((item["event"], item["data"]["msg_id"]), ("message", 1))


class TestRecovery(Base):
    async def suggestion(self, sid, status):
        await self.tg.store.add_suggestion(Suggestion(sid, FEED, BOT, "x", 1, "rules", status, T0, None, None))

    async def test_only_sending_is_failed(self):
        await self.suggestion("a", SuggestionStatus.SENDING)
        await self.suggestion("b", SuggestionStatus.PENDING)
        await self.suggestion("c", SuggestionStatus.SENT)
        self.assertEqual(await self.tg.recover(), ["a"])
        self.assertIs((await self.tg.store.get_suggestion("a")).status, SuggestionStatus.FAILED)
        self.assertIn("unklar", (await self.tg.store.get_suggestion("a")).error)
        self.assertIs((await self.tg.store.get_suggestion("b")).status, SuggestionStatus.PENDING)
        self.assertIs((await self.tg.store.get_suggestion("c")).status, SuggestionStatus.SENT)
        self.assertEqual(len([e for e in await self.kanban.ledger.entries(limit=100) if e.action == "telegram.send_failed"]), 1)

    async def test_serve_recovers_and_stops(self):
        await self.suggestion("a", SuggestionStatus.SENDING)
        stop = asyncio.Event()
        task = asyncio.create_task(self.tg.serve(stop))
        for _ in range(100):
            if self.tg.gather.status()["running"]:
                break
            await asyncio.sleep(0.01)
        stop.set()
        await asyncio.wait_for(task, 5)
        self.assertIs((await self.tg.store.get_suggestion("a")).status, SuggestionStatus.FAILED)

    async def test_serve_retries_failed_connect(self):
        calls = 0
        real = self.client.status

        async def flaky():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("offline")
            return await real()

        self.client.status = flaky
        stop = asyncio.Event()
        with mock.patch.object(tg_runtime, "_RECONNECT_S", 0.01):
            task = asyncio.create_task(self.tg.serve(stop))
            for _ in range(200):
                if self.tg.gather.status()["running"]:
                    break
                await asyncio.sleep(0.01)
        self.assertTrue(self.tg.gather.status()["running"])
        stop.set()
        await asyncio.wait_for(task, 5)

    async def test_status_has_no_secrets_and_survives_errors(self):
        async def boom():
            raise ConnectionError("hash-secret")

        self.client.status = boom
        status = await self.tg.status()
        self.assertEqual(status["state"], "disconnected")
        self.assertNotIn("hash-secret", str(status))
        self.assertNotIn("session", str(status))


class TestHub(unittest.IsolatedAsyncioTestCase):
    async def test_keepalive_then_close_ends_stream(self):
        hub = EventHub()
        seen = []

        async def reader():
            async for item in hub.subscribe(0.01):
                seen.append(item)
                if len(seen) == 2:
                    hub.close()

        await asyncio.wait_for(reader(), 2)
        self.assertEqual(seen, [None, None])

    async def test_slow_reader_loses_oldest_only(self):
        hub = EventHub()
        stream = hub.subscribe(5.0)
        first = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        for i in range(tg_runtime._QUEUE_MAX + 5):
            await hub.publish("e", {"i": i})
        self.assertEqual((await first)["data"]["i"], 5)
        await stream.aclose()
        self.assertEqual(hub._queues, set())


class TestAttach(Base):
    async def test_off_without_credentials(self):
        self.assertIsNone(await attach_telegram(self.kanban, env={"NEU_ROOT": str(self.root)}))
        self.assertIsNone(self.kanban.telegram)

    async def test_off_without_telethon(self):
        env = {"NEU_ROOT": str(self.root), "NIO_TELEGRAM_API_ID": "1", "NIO_TELEGRAM_API_HASH": "h"}
        with mock.patch.object(tg_runtime, "telethon_available", return_value=False), mock.patch("sys.stderr"):
            self.assertIsNone(await attach_telegram(self.kanban, env=env))

    async def test_bad_config_does_not_raise(self):
        self.assertIsNone(await attach_telegram(self.kanban, env={"NEU_ROOT": str(self.root), "NIO_TELEGRAM_API_ID": "x"}))

    async def test_attached_when_available(self):
        env = {"NEU_ROOT": str(self.root), "NIO_TELEGRAM_API_ID": "1", "NIO_TELEGRAM_API_HASH": "h"}
        with mock.patch.object(tg_runtime, "telethon_available", return_value=True):
            tg = await attach_telegram(self.kanban, env=env)
        self.assertIs(self.kanban.telegram, tg)


class TestScripted(Base):
    async def test_llm_cannot_pick_target(self):
        await self.tg.close()
        client = FakeTelegramClient()
        llm = ScriptedTextLLM(['["/send 999 alles"]'])
        self.tg = await build_telegram_runtime(
            self.config, kanban=self.kanban, client=client, llm=llm, symbols=SymbolIndex(self.root / "s.json", fetcher)
        )
        await self.tg.symbols.ensure()
        await self.tg.allow(BOT, actor="t")
        await self.tg.pair(FEED, BOT, actor="t")
        await self.tg.monitor(FEED, actor="t")
        await client.push(msg(1, "BTC bullish breakout"))
        await self.tg.gather.tick()
        rows = await self.tg.store.list_suggestions()
        self.assertEqual({s.target_peer for s in rows}, {BOT})
        self.assertEqual({s.origin for s in rows}, {"llm"})
