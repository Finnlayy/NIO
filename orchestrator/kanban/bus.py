"""In-Memory Bus, LockManager, HeartbeatStore und TokenStore (WP-02).

Diese Implementierungen sind rein lokal und eignen sich für Einzelprozesse
oder Tests. Für verteilte Umgebungen existieren die Redis-Pendants.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import time
from collections.abc import AsyncIterator
from typing import Protocol

from orchestrator.events import EventBus as UdsEventBus
from orchestrator.kanban.models import KanbanEvent

__all__ = [
    "KanbanBus",
    "LockManager",
    "HeartbeatStore",
    "TokenStore",
    "InProcessBus",
    "NeuEventBridge",
    "InMemoryLockManager",
    "InMemoryHeartbeatStore",
    "InMemoryTokenStore",
]


class KanbanBus(Protocol):
    async def publish(self, event: KanbanEvent) -> None: ...
    def subscribe(self) -> AsyncIterator[KanbanEvent]: ...
    async def close(self) -> None: ...


class LockManager(Protocol):
    async def acquire(self, key: str, owner: str, ttl_s: float) -> bool: ...
    async def release(self, key: str, owner: str) -> bool: ...
    async def refresh(self, key: str, owner: str, ttl_s: float) -> bool: ...


class HeartbeatStore(Protocol):
    async def beat(self, task_id: str, ttl_s: float, *, worker_uid: str = "") -> None: ...
    async def alive(self, task_id: str) -> bool: ...
    async def clear(self, task_id: str) -> None: ...


class TokenStore(Protocol):
    async def put(self, token: str, claims: dict[str, str], ttl_s: float) -> None: ...
    async def get(self, token: str) -> dict[str, str] | None: ...
    async def revoke(self, token: str) -> None: ...


class InProcessBus:
    """Lokaler Event-Bus mit Fan-Out ueber asyncio.Queue."""

    def __init__(self) -> None:
        self.queues: list[asyncio.Queue[KanbanEvent | None]] = []
        self.dropped: int = 0
        self._closed = False

    async def publish(self, event: KanbanEvent) -> None:
        if self._closed:
            return
        for q in self.queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                self.dropped += 1

    async def _subscriber(self, q: asyncio.Queue[KanbanEvent | None]) -> AsyncIterator[KanbanEvent]:
        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield item
        finally:
            if q in self.queues:
                self.queues.remove(q)

    def subscribe(self) -> AsyncIterator[KanbanEvent]:
        q: asyncio.Queue[KanbanEvent | None] = asyncio.Queue(maxsize=1000)
        self.queues.append(q)
        return self._subscriber(q)

    async def close(self) -> None:
        self._closed = True
        for q in self.queues:
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(None)


class NeuEventBridge:
    """Leitet Kanban-Events an die System-Telemetrie weiter."""

    def __init__(self, bus: UdsEventBus, kanban_bus: KanbanBus) -> None:
        self.bus = bus
        self.kanban_bus = kanban_bus
        self._task: asyncio.Task[None] | None = None
        self._iterator: AsyncIterator[KanbanEvent] | None = None

    def start(self) -> None:
        self._iterator = self.kanban_bus.subscribe()
        self._task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        if self._iterator is None:
            return
        try:
            async for event in self._iterator:
                self.bus.emit(f"kanban.{event.kind}", event.to_dict())
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


class InMemoryLockManager:
    """Lokaler Lock-Manager ueber ein Dict mit Ablaufzeiten."""

    def __init__(self) -> None:
        self._locks: dict[str, tuple[str, float]] = {}
        self._mu = asyncio.Lock()

    def _cleanup(self, now: float) -> None:
        expired = [k for k, v in self._locks.items() if v[1] < now]
        for k in expired:
            del self._locks[k]

    async def acquire(self, key: str, owner: str, ttl_s: float) -> bool:
        async with self._mu:
            now = time.monotonic()
            self._cleanup(now)
            if key in self._locks:
                return False
            self._locks[key] = (owner, now + ttl_s)
            return True

    async def release(self, key: str, owner: str) -> bool:
        async with self._mu:
            now = time.monotonic()
            self._cleanup(now)
            if key not in self._locks:
                return False
            current_owner, _ = self._locks[key]
            if current_owner == owner:
                del self._locks[key]
                return True
            return False

    async def refresh(self, key: str, owner: str, ttl_s: float) -> bool:
        async with self._mu:
            now = time.monotonic()
            self._cleanup(now)
            if key not in self._locks:
                return False
            current_owner, _ = self._locks[key]
            if current_owner == owner:
                self._locks[key] = (owner, now + ttl_s)
                return True
            return False


class InMemoryHeartbeatStore:
    """Lokaler Heartbeat-Store."""

    def __init__(self) -> None:
        self._beats: dict[str, tuple[float, str]] = {}
        self._mu = asyncio.Lock()

    async def beat(self, task_id: str, ttl_s: float, *, worker_uid: str = "") -> None:
        async with self._mu:
            self._beats[task_id] = (time.monotonic() + ttl_s, worker_uid)

    async def alive(self, task_id: str) -> bool:
        async with self._mu:
            if task_id not in self._beats:
                return False
            expiry, _ = self._beats[task_id]
            if expiry < time.monotonic():
                del self._beats[task_id]
                return False
            return True

    async def clear(self, task_id: str) -> None:
        async with self._mu:
            self._beats.pop(task_id, None)


class InMemoryTokenStore:
    """Lokaler Token-Store (speichert sha256)."""

    def __init__(self) -> None:
        self._tokens: dict[str, tuple[dict[str, str], float]] = {}
        self._mu = asyncio.Lock()

    def _hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def put(self, token: str, claims: dict[str, str], ttl_s: float) -> None:
        h = self._hash(token)
        async with self._mu:
            self._tokens[h] = (claims, time.monotonic() + ttl_s)

    async def get(self, token: str) -> dict[str, str] | None:
        h = self._hash(token)
        async with self._mu:
            if h not in self._tokens:
                return None
            claims, expiry = self._tokens[h]
            if expiry < time.monotonic():
                del self._tokens[h]
                return None
            return claims

    async def revoke(self, token: str) -> None:
        h = self._hash(token)
        async with self._mu:
            self._tokens.pop(h, None)
