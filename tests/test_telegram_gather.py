import asyncio
import tempfile
import unittest
from pathlib import Path

from orchestrator.telegram.client import FakeTelegramClient, TelegramFloodWait, TelegramNotAuthorized
from orchestrator.telegram.config import TelegramConfig
from orchestrator.telegram.gather import GatherLoop
from orchestrator.telegram.models import TgMessage
from orchestrator.telegram.router import IntelRouter, SuggestionSink
from orchestrator.telegram.store import SqliteTelegramStore
from orchestrator.telegram.symbols import SymbolIndex

FEED, OTHER, BOT = 10, 11, 20
T0 = "2026-01-01T00:00:00.000Z"


def msg(msg_id, text="BTC rally", peer=FEED):
    return TgMessage(peer, msg_id, "feed", text, T0, False, False)


class FlakySink:
    def __init__(self):
        self.fail_on = set()
        self.seen = []

    async def handle(self, message, signal):
        if message.msg_id in self.fail_on:
            raise RuntimeError("sink down")
        self.seen.append(message.msg_id)


class Base(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = SqliteTelegramStore(Path(self.td.name) / "t.db")
        await self.store.init()
        await self.store.add_monitored(FEED)
        await self.store.set_pairing(FEED, BOT)
        await self.store.allow(BOT)
        self.config = TelegramConfig.from_env({}, repo_root=Path(self.td.name))
        self.client = FakeTelegramClient()
        index = SymbolIndex(Path("/nonexistent/none.json"))
        index.bases = {"BTC"}
        self.flaky = FlakySink()
        sinks = [SuggestionSink(self.store, self.config), self.flaky]
        self.loop = GatherLoop(self.client, self.store, IntelRouter(self.store, index, sinks), self.config)

    async def asyncTearDown(self):
        await self.store.close()
        self.td.cleanup()


class TestTick(Base):
    async def test_routes_and_advances_cursor(self):
        self.client.fake_messages = [msg(1), msg(2)]
        report = await self.loop.tick()
        self.assertEqual((report.peers, report.fetched, report.routed, report.errors), (1, 2, 2, []))
        self.assertEqual(await self.store.get_cursor(FEED), 2)
        self.assertEqual(await self.store.unrouted_messages(FEED), [])

    async def test_no_new_messages_keeps_cursor(self):
        await self.loop.tick()
        self.assertEqual(await self.store.get_cursor(FEED), 0)

    async def test_at_least_once_after_router_failure(self):
        self.client.fake_messages = [msg(1), msg(2), msg(3)]
        self.flaky.fail_on = {2}
        report = await self.loop.tick()
        self.assertEqual(report.routed, 1)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(await self.store.get_cursor(FEED), 0)
        self.assertEqual([m.msg_id for m in await self.store.unrouted_messages(FEED)], [2, 3])

        self.flaky.fail_on = set()
        report = await self.loop.tick()
        self.assertEqual((report.routed, report.errors), (2, []))
        self.assertEqual(await self.store.get_cursor(FEED), 3)
        self.assertEqual(self.flaky.seen, [1, 2, 3])
        # Msg 2 lief vor dem Fehler schon durch die SuggestionSink: trotzdem nur ein Vorschlag.
        ids = sorted(s.id for s in await self.store.list_suggestions())
        self.assertEqual(ids, [f"sug-{FEED}-1-0", f"sug-{FEED}-2-0", f"sug-{FEED}-3-0"])

    async def test_failing_peer_does_not_block_others(self):
        await self.store.add_monitored(OTHER)
        self.client.fake_messages = [msg(1), msg(5, peer=OTHER)]
        self.flaky.fail_on = {1}
        report = await self.loop.tick()
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(await self.store.get_cursor(OTHER), 5)

    async def test_flood_wait_stops_tick(self):
        await self.store.add_monitored(OTHER)
        calls = []

        async def flood(peer, min_id, limit):
            calls.append(peer)
            raise TelegramFloodWait(42)

        self.client.messages_since = flood
        report = await self.loop.tick()
        self.assertEqual(report.flood_wait_s, 42)
        self.assertEqual(len(calls), 1)
        self.assertEqual(await self.store.get_cursor(FEED), 0)

    async def test_not_authorized_stops_tick(self):
        async def denied(peer, min_id, limit):
            raise TelegramNotAuthorized("nein")

        self.client.messages_since = denied
        report = await self.loop.tick()
        self.assertEqual(len(report.errors), 1)
        self.assertIn("TelegramNotAuthorized", report.errors[0])

    async def test_status(self):
        self.assertIsNone(self.loop.status()["last_tick"])
        await self.loop.tick()
        status = self.loop.status()
        self.assertFalse(status["running"])
        self.assertEqual(status["interval_s"], 300.0)
        self.assertEqual(status["last_tick"]["peers"], 1)


class TestLive(Base):
    async def test_monitored_only(self):
        self.loop.attach_live()
        await self.client.push(msg(1))
        await self.client.push(msg(9, peer=OTHER))
        self.assertEqual(self.flaky.seen, [1])
        self.assertEqual(await self.store.recent_messages([OTHER], 10), [])
        self.assertEqual(await self.store.get_cursor(FEED), 0)

    async def test_attach_twice_registers_once(self):
        self.loop.attach_live()
        self.loop.attach_live()
        self.assertEqual(len(self.client.callbacks), 1)

    async def test_live_failure_retried_by_tick(self):
        self.loop.attach_live()
        self.flaky.fail_on = {1}
        await self.client.push(msg(1))
        self.flaky.fail_on = set()
        await self.loop.tick()
        self.assertEqual(self.flaky.seen, [1])

    async def test_tick_does_not_route_live_message_again(self):
        self.loop.attach_live()
        await self.client.push(msg(1))
        await self.loop.tick()
        self.assertEqual(self.flaky.seen, [1])
        self.assertEqual(await self.store.get_cursor(FEED), 1)

    async def test_concurrent_tick_and_live_route_once(self):
        self.client.fake_messages = [msg(1)]
        await asyncio.gather(self.loop.tick(), self.loop._on_live(msg(1)))
        self.assertEqual(self.flaky.seen, [1])


class TestRun(Base):
    async def test_stops_on_event_and_survives_tick_errors(self):
        calls = 0
        real_tick = self.loop.tick
        stop = asyncio.Event()

        async def tick():
            nonlocal calls
            calls += 1
            stop.set()
            await real_tick()
            raise RuntimeError("kaputt")

        self.loop.tick = tick
        with self.assertLogs("orchestrator.telegram.gather", "ERROR"):
            await asyncio.wait_for(self.loop.run(stop), 2)
        self.assertEqual(calls, 1)
        self.assertFalse(self.loop.status()["running"])
