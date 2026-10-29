import asyncio
import unittest

from orchestrator.kanban.models import KanbanEvent
from orchestrator.kanban.redis_resp import RedisBus, RedisClient, RedisError, RedisHeartbeatStore, RedisLockManager, RedisTokenStore


class FakeRedisServer:
    def __init__(self):
        self.data = {}
        self.expires = {}
        self.server = None
        self.subscribers = []
        self._tasks = []

    async def handle_client(self, reader, writer):
        # We need a proper RESP parser for the requests
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                if line.startswith(b"*"):
                    count = int(line[1:-2])
                    args = []
                    for _ in range(count):
                        lens = await reader.readline()
                        length = int(lens[1:-2])
                        arg = await reader.readexactly(length + 2)
                        args.append(arg[:-2])

                    await self.process_command(args, writer)
        except (TimeoutError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def process_command(self, args, writer):
        cmd = args[0].decode("utf-8").upper()

        if cmd == "PING":
            writer.write(b"+PONG\r\n")
        elif cmd == "AUTH":
            writer.write(b"+OK\r\n")
        elif cmd == "SELECT":
            writer.write(b"+OK\r\n")
        elif cmd == "SET":
            key = args[1].decode("utf-8")
            val = args[2]

            nx = False
            px = None
            i = 3
            while i < len(args):
                opt = args[i].decode("utf-8").upper()
                if opt == "NX":
                    nx = True
                    i += 1
                elif opt == "PX":
                    px = int(args[i+1])
                    i += 2
                else:
                    i += 1

            if nx and key in self.data:
                writer.write(b"$-1\r\n")
                await writer.drain()
                return

            self.data[key] = val
            if px is not None:
                loop = asyncio.get_running_loop()
                self.expires[key] = loop.time() + (px / 1000.0)
            writer.write(b"+OK\r\n")

        elif cmd == "GET":
            key = args[1].decode("utf-8")
            self._cleanup()
            if key in self.data:
                val = self.data[key]
                writer.write(f"${len(val)}\r\n".encode() + val + b"\r\n")
            else:
                writer.write(b"$-1\r\n")

        elif cmd == "DEL":
            key = args[1].decode("utf-8")
            if key in self.data:
                del self.data[key]
                writer.write(b":1\r\n")
            else:
                writer.write(b":0\r\n")

        elif cmd == "EXISTS":
            key = args[1].decode("utf-8")
            self._cleanup()
            if key in self.data:
                writer.write(b":1\r\n")
            else:
                writer.write(b":0\r\n")

        elif cmd == "PUBLISH":
            channel = args[1]
            message = args[2]

            for q in list(self.subscribers):
                try:
                    q.put_nowait((channel, message))
                except asyncio.QueueFull:
                    pass

            writer.write(b":1\r\n")

        elif cmd == "SUBSCRIBE":
            channel = args[1]
            writer.write(b"*3\r\n$9\r\nsubscribe\r\n$" + str(len(channel)).encode("utf-8") + b"\r\n" + channel + b"\r\n:1\r\n")
            await writer.drain()

            q = asyncio.Queue(maxsize=1000)
            self.subscribers.append(q)

            # Start a background task for subscriber
            async def sub_loop():
                try:
                    while True:
                        if writer.is_closing():
                            break
                        ch, msg = await q.get()
                        if ch == channel:
                            resp = b"*3\r\n$7\r\nmessage\r\n$" + str(len(ch)).encode("utf-8") + b"\r\n" + ch + b"\r\n$" + str(len(msg)).encode("utf-8") + b"\r\n" + msg + b"\r\n"
                            writer.write(resp)
                            await writer.drain()
                except Exception:
                    pass
                finally:
                    if q in self.subscribers:
                        self.subscribers.remove(q)

            task = asyncio.create_task(sub_loop())
            self._tasks.append(task)

        elif cmd == "EVAL":
            script = args[1].decode("utf-8")
            if "del" in script.lower(): # release script
                key = args[3].decode("utf-8")
                owner = args[4]
                self._cleanup()
                if key in self.data and self.data[key] == owner:
                    del self.data[key]
                    writer.write(b":1\r\n")
                else:
                    writer.write(b":0\r\n")
            elif "pexpire" in script.lower(): # refresh script
                key = args[3].decode("utf-8")
                owner = args[4]
                ttl = int(args[5])
                self._cleanup()
                if key in self.data and self.data[key] == owner:
                    loop = asyncio.get_running_loop()
                    self.expires[key] = loop.time() + (ttl / 1000.0)
                    writer.write(b":1\r\n")
                else:
                    writer.write(b":0\r\n")
            else:
                writer.write(b"-ERR unknown script\r\n")
        else:
            writer.write(b"-ERR unknown command\r\n")

        if not writer.is_closing():
            try:
                await writer.drain()
            except Exception:
                pass

    def _cleanup(self):
        loop = asyncio.get_running_loop()
        now = loop.time()
        expired = [k for k, v in self.expires.items() if v < now]
        for k in expired:
            if k in self.data:
                del self.data[k]
            del self.expires[k]

    async def start(self):
        self.server = await asyncio.start_server(self.handle_client, '127.0.0.1', 0)
        return self.server.sockets[0].getsockname()[1]

    async def stop(self):
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self.server:
            self.server.close()
            await self.server.wait_closed()


class TestKanbanRedisResp(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake_redis = FakeRedisServer()
        self.port = await self.fake_redis.start()
        self.client = RedisClient('127.0.0.1', self.port)

    async def asyncTearDown(self):
        await self.client.close()
        await self.fake_redis.stop()

    async def test_redis_client_parser(self):
        # Test simple string
        self.assertEqual(await self.client.execute("PING"), "PONG")

        # Test error
        with self.assertRaises(RedisError):
            await self.client.execute("UNKNOWN")

        # Test int
        await self.client.execute("SET", "k1", "v1")
        self.assertEqual(await self.client.execute("EXISTS", "k1"), 1)

        # Test bulk string
        self.assertEqual(await self.client.execute("GET", "k1"), b"v1")

        # Test null bulk string
        self.assertIsNone(await self.client.execute("GET", "missing"))

    async def test_redis_bus(self):
        bus = RedisBus(self.client)
        sub = bus.subscribe()

        # We need a small task to process subscription logic
        sub_task = asyncio.create_task(sub.__anext__())

        # Give it a moment to connect and send SUBSCRIBE
        await asyncio.sleep(0.1)

        event = KanbanEvent(kind="test", payload={"a": 1})
        await bus.publish(event)

        e1 = await sub_task
        self.assertEqual(e1.kind, "test")
        self.assertEqual(e1.payload, {"a": 1})

        await bus.close()

        # also cleanly close the subclient that subscribe spawns
        if hasattr(sub, "ag_frame"):
            pass

    async def test_redis_lock_manager(self):
        lm = RedisLockManager(self.client)

        ok = await lm.acquire("l1", "w1", 0.1)
        self.assertTrue(ok)

        ok = await lm.acquire("l1", "w2", 0.1)
        self.assertFalse(ok)

        ok = await lm.release("l1", "w2")
        self.assertFalse(ok)

        ok = await lm.release("l1", "w1")
        self.assertTrue(ok)

        # test refresh
        await lm.acquire("l2", "w1", 0.5)
        ok = await lm.refresh("l2", "w1", 0.5)
        self.assertTrue(ok)
        ok = await lm.refresh("l2", "w2", 0.5)
        self.assertFalse(ok)

    async def test_redis_heartbeat_store(self):
        hb = RedisHeartbeatStore(self.client)

        await hb.beat("t1", 0.1, worker_uid="w1")
        self.assertTrue(await hb.alive("t1"))

        await hb.clear("t1")
        self.assertFalse(await hb.alive("t1"))

        await hb.beat("t2", 0.05)
        await asyncio.sleep(0.1)
        self.assertFalse(await hb.alive("t2"))

    async def test_redis_token_store(self):
        ts = RedisTokenStore(self.client)

        await ts.put("secret", {"id": "t1"}, 0.1)
        claims = await ts.get("secret")
        self.assertEqual(claims, {"id": "t1"})

        await ts.revoke("secret")
        self.assertIsNone(await ts.get("secret"))

if __name__ == '__main__':
    unittest.main()
