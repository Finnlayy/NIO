"""Redis-Client via RESP2 fuer asyncio ohne externe Abhaengigkeiten (WP-02).

Implementiert die Bus/Lock/Heartbeat/Token-Protocols ueber Redis.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import urllib.parse
from collections.abc import AsyncIterator
from typing import Any

from orchestrator.kanban.bus import HeartbeatStore, KanbanBus, LockManager, TokenStore
from orchestrator.kanban.models import KanbanEvent

__all__ = [
    "RedisError",
    "RedisClient",
    "RedisBus",
    "RedisLockManager",
    "RedisHeartbeatStore",
    "RedisTokenStore",
]


class RedisError(Exception):
    """Fehlerantwort vom Redis-Server."""
    pass


class RedisClient:
    """Minimaler asynchroner Redis-Client ueber RESP2."""

    def __init__(self, host: str, port: int, password: str | None = None, db: int = 0, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._mu = asyncio.Lock()

    @classmethod
    def from_url(cls, url: str, timeout: float = 5.0) -> RedisClient:
        """Erzeugt Client aus redis://[:pw@]host:port/db"""
        p = urllib.parse.urlparse(url)
        host = p.hostname or "localhost"
        port = p.port or 6379
        password = p.password
        db = 0
        if p.path and p.path != "/":
            with contextlib.suppress(ValueError):
                db = int(p.path.lstrip("/"))
        return cls(host, port, password, db, timeout)

    async def connect(self) -> None:
        """Verbindet (und authentifiziert/waehlt DB) bei Bedarf."""
        if self._writer is not None:
            return

        # open_connection needs to be awaited with a timeout theoretically, but connect is internal
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=self.timeout
        )
        if self.password:
            await self.execute("AUTH", self.password)
        if self.db != 0:
            await self.execute("SELECT", str(self.db))

    async def close(self) -> None:
        async with self._mu:
            if self._writer is not None:
                self._writer.close()
                with contextlib.suppress(Exception):
                    await self._writer.wait_closed()
                self._writer = None
                self._reader = None

    def _encode(self, *args: Any) -> bytes:
        cmds = []
        cmds.append(f"*{len(args)}\r\n".encode("utf-8"))
        for arg in args:
            if isinstance(arg, bytes):
                cmds.append(f"${len(arg)}\r\n".encode("utf-8"))
                cmds.append(arg)
                cmds.append(b"\r\n")
            else:
                s = str(arg).encode("utf-8")
                cmds.append(f"${len(s)}\r\n".encode("utf-8"))
                cmds.append(s)
                cmds.append(b"\r\n")
        return b"".join(cmds)

    async def _read_response(self) -> Any:
        if self._reader is None:
            raise ConnectionError("Not connected")

        line = await self._reader.readline()
        if not line:
            raise ConnectionError("Verbindung abgebrochen")

        prefix = chr(line[0])
        data = line[1:-2]  # strip \r\n

        if prefix == "+":
            return data.decode("utf-8")
        elif prefix == "-":
            raise RedisError(data.decode("utf-8"))
        elif prefix == ":":
            return int(data)
        elif prefix == "$":
            length = int(data)
            if length == -1:
                return None
            res = await self._reader.readexactly(length + 2)
            return res[:-2]
        elif prefix == "*":
            count = int(data)
            if count == -1:
                return None
            return [await self._read_response() for _ in range(count)]
        else:
            raise ProtocolError(f"Unbekanntes RESP2 Prefix: {prefix}")

    async def _execute_once(self, *args: Any) -> Any:
        await self.connect()
        assert self._writer is not None
        req = self._encode(*args)
        self._writer.write(req)
        await self._writer.drain()
        return await self._read_response()

    async def execute(self, *args: Any) -> Any:
        async with self._mu:
            try:
                return await asyncio.wait_for(self._execute_once(*args), timeout=self.timeout)
            except (ConnectionError, asyncio.TimeoutError, OSError):
                # Wenn es pub/eval ist, nicht nochmal versuchen? Speziell eval/publish.
                cmd = str(args[0]).upper()
                if cmd in ("PUBLISH", "EVAL"):
                    raise
                # Verbindung abräumen und neu versuchen
                if self._writer:
                    self._writer.close()
                    self._writer = None
                    self._reader = None
                return await asyncio.wait_for(self._execute_once(*args), timeout=self.timeout)

    async def subscribe(self, channel: str) -> AsyncIterator[bytes]:
        """Abonniert einen Kanal und liefert die Payloads. Oeffnet eigene Verbindung."""
        sub_client = RedisClient(self.host, self.port, self.password, self.db, timeout=5.0)
        await sub_client.connect()
        assert sub_client._writer is not None
        assert sub_client._reader is not None

        sub_client._writer.write(sub_client._encode("SUBSCRIBE", channel))
        await sub_client._writer.drain()

        try:
            while True:
                resp = await sub_client._read_response()
                if isinstance(resp, list) and len(resp) == 3 and resp[0] == b"message" and resp[1] == channel.encode("utf-8"):
                    yield resp[2]
        finally:
            await sub_client.close()


class RedisBus(KanbanBus):
    """Event-Bus ueber Redis Pub/Sub."""

    def __init__(self, client: RedisClient, channel: str = "kanban:events"):
        self.client = client
        self.channel = channel
        self._closed = False

    async def publish(self, event: KanbanEvent) -> None:
        if self._closed:
            return
        payload = json.dumps(event.to_dict())
        with contextlib.suppress(Exception):
            await self.client.execute("PUBLISH", self.channel, payload)

    async def _subscriber(self) -> AsyncIterator[KanbanEvent]:
        try:
            async for payload in self.client.subscribe(self.channel):
                if self._closed:
                    break
                try:
                    data = json.loads(payload.decode("utf-8"))
                    yield KanbanEvent.from_dict(data)
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass

    def subscribe(self) -> AsyncIterator[KanbanEvent]:
        return self._subscriber()

    async def close(self) -> None:
        self._closed = True


class RedisLockManager(LockManager):
    """Verteiltes Lock ueber Redis (SET NX PX)."""

    def __init__(self, client: RedisClient):
        self.client = client
        self._release_script = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"
        self._refresh_script = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('pexpire',KEYS[1],ARGV[2]) else return 0 end"

    def _key(self, key: str) -> str:
        return f"kanban:lock:{key}"

    async def acquire(self, key: str, owner: str, ttl_s: float) -> bool:
        r = await self.client.execute("SET", self._key(key), owner, "NX", "PX", int(ttl_s * 1000))
        return bool(r == b"OK" or r == "OK")

    async def release(self, key: str, owner: str) -> bool:
        r = await self.client.execute("EVAL", self._release_script, "1", self._key(key), owner)
        return bool(r == 1)

    async def refresh(self, key: str, owner: str, ttl_s: float) -> bool:
        r = await self.client.execute("EVAL", self._refresh_script, "1", self._key(key), owner, str(int(ttl_s * 1000)))
        return bool(r == 1)


class RedisHeartbeatStore(HeartbeatStore):
    """Heartbeats ueber Redis SET PX."""

    def __init__(self, client: RedisClient):
        self.client = client

    def _key(self, task_id: str) -> str:
        return f"kanban:hb:{task_id}"

    async def beat(self, task_id: str, ttl_s: float, *, worker_uid: str = "") -> None:
        payload = json.dumps({"ts": 0, "worker_uid": worker_uid})
        await self.client.execute("SET", self._key(task_id), payload, "PX", int(ttl_s * 1000))

    async def alive(self, task_id: str) -> bool:
        r = await self.client.execute("EXISTS", self._key(task_id))
        return bool(r == 1)

    async def clear(self, task_id: str) -> None:
        await self.client.execute("DEL", self._key(task_id))


class RedisTokenStore(TokenStore):
    """Token-Store ueber Redis SET PX."""

    def __init__(self, client: RedisClient):
        self.client = client

    def _hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _key(self, token: str) -> str:
        return f"kanban:token:{self._hash(token)}"

    async def put(self, token: str, claims: dict[str, str], ttl_s: float) -> None:
        payload = json.dumps(claims)
        await self.client.execute("SET", self._key(token), payload, "PX", int(ttl_s * 1000))

    async def get(self, token: str) -> dict[str, str] | None:
        r = await self.client.execute("GET", self._key(token))
        if r is None:
            return None
        try:
            val = json.loads(r.decode("utf-8"))
            if isinstance(val, dict):
                return val
            return None
        except Exception:
            return None

    async def revoke(self, token: str) -> None:
        await self.client.execute("DEL", self._key(token))

class ProtocolError(Exception):
    pass
