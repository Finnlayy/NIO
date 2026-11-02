import asyncio
import unittest

from orchestrator.events import EventBus, EventSink
from orchestrator.kanban.bus import (
    InMemoryHeartbeatStore,
    InMemoryLockManager,
    InMemoryTokenStore,
    InProcessBus,
    NeuEventBridge,
)
from orchestrator.kanban.models import KanbanEvent


class DummySink(EventSink):
    def __init__(self, target):
        self.target = target
    def wants_prepared_line(self) -> bool:
        return False
    def write(self, record):
        self.target(record)
    def write_prepared(self, record, line):
        self.target(record)

class TestKanbanBus(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        # Cancel any remaining tasks
        for task in asyncio.all_tasks(self.loop):
            task.cancel()

        # Run event loop to give cancelled tasks a chance to finish
        async def cancel_tasks():
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if not tasks:
                return
            await asyncio.gather(*tasks, return_exceptions=True)

        self.loop.run_until_complete(cancel_tasks())
        self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        self.loop.close()

    def test_in_process_bus_fanout(self):
        async def run():
            bus = InProcessBus()
            sub1 = bus.subscribe()
            sub2 = bus.subscribe()

            event = KanbanEvent(kind="test", payload={"a": 1})
            await bus.publish(event)

            e1 = await sub1.__anext__()
            e2 = await sub2.__anext__()

            self.assertEqual(e1.kind, "test")
            self.assertEqual(e2.kind, "test")

            await bus.close()
            with self.assertRaises(StopAsyncIteration):
                await sub1.__anext__()
        self.loop.run_until_complete(run())

    def test_in_process_bus_full_queue(self):
        async def run():
            bus = InProcessBus()
            bus.subscribe()

            for _ in range(1010):
                await bus.publish(KanbanEvent(kind="test", payload={}))

            self.assertGreater(bus.dropped, 0)
            await bus.close()
        self.loop.run_until_complete(run())

    def test_in_memory_lock_manager(self):
        async def run():
            lm = InMemoryLockManager()

            # acquire
            ok = await lm.acquire("l1", "w1", 0.1)
            self.assertTrue(ok)

            # double acquire fails
            ok = await lm.acquire("l1", "w2", 0.1)
            self.assertFalse(ok)

            # wrong owner release fails
            ok = await lm.release("l1", "w2")
            self.assertFalse(ok)

            # right owner release succeeds
            ok = await lm.release("l1", "w1")
            self.assertTrue(ok)

            # expire
            await lm.acquire("l2", "w1", 0.01)
            await asyncio.sleep(0.02)
            ok = await lm.acquire("l2", "w2", 0.1)
            self.assertTrue(ok)
        self.loop.run_until_complete(run())

    def test_in_memory_heartbeat_store(self):
        async def run():
            hb = InMemoryHeartbeatStore()

            await hb.beat("t1", 0.05, worker_uid="w1")
            self.assertTrue(await hb.alive("t1"))

            await asyncio.sleep(0.06)
            self.assertFalse(await hb.alive("t1"))

            await hb.beat("t1", 0.1)
            await hb.clear("t1")
            self.assertFalse(await hb.alive("t1"))
        self.loop.run_until_complete(run())

    def test_in_memory_token_store(self):
        async def run():
            ts = InMemoryTokenStore()

            await ts.put("secret", {"id": "t1"}, 0.1)
            claims = await ts.get("secret")
            self.assertEqual(claims, {"id": "t1"})

            await ts.revoke("secret")
            self.assertIsNone(await ts.get("secret"))

            await ts.put("secret2", {"id": "t2"}, 0.01)
            await asyncio.sleep(0.02)
            self.assertIsNone(await ts.get("secret2"))
        self.loop.run_until_complete(run())

    def test_neu_event_bridge(self):
        async def run():
            kanban_bus = InProcessBus()
            emitted = []
            def capture(record):
                kind = record.get("kind")
                if kind and kind.startswith("kanban."):
                    emitted.append((kind, record))
            sys_bus = EventBus([DummySink(capture)])

            bridge = NeuEventBridge(sys_bus, kanban_bus)
            bridge.start()

            await kanban_bus.publish(KanbanEvent(kind="test_kind", payload={"p": 1}))
            await asyncio.sleep(0.05)

            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0][0], "kanban.test_kind")

            # record is event.to_dict()
            # It should have a payload field in the dict with the inner dict
            payload = emitted[0][1].get("payload", {})
            self.assertEqual(payload.get("payload", {}), {"p": 1})

            await bridge.stop()
            await kanban_bus.close()
        self.loop.run_until_complete(run())

if __name__ == '__main__':
    unittest.main()
