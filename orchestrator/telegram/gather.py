"""Gather-Loop und Live-Listener: holen Feed-Nachrichten und routen sie at-least-once.

Der Cursor rueckt erst vor, wenn alles zugestellt ist; ``routed_at`` haelt fest, was
schon durch ist. Pro Peer routet immer nur einer (Tick oder Listener).
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.protocol import utc_now_iso

from .client import TelegramFloodWait, TelegramNotAuthorized, TelegramPort
from .config import TelegramConfig
from .models import TgMessage
from .router import Emit, IntelRouter, safe_emit
from .store import TelegramStore

__all__ = ["GatherLoop", "TickReport"]

logger = logging.getLogger(__name__)

_FETCH_LIMIT = 200


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


@dataclass
class TickReport:
    at: str
    peers: int = 0
    fetched: int = 0
    routed: int = 0
    errors: list[str] = field(default_factory=list)
    flood_wait_s: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class GatherLoop:
    def __init__(
        self,
        client: TelegramPort,
        store: TelegramStore,
        router: IntelRouter,
        config: TelegramConfig,
        *,
        clock: Callable[[], str] = utc_now_iso,
        emit: Emit | None = None,
    ) -> None:
        self._client = client
        self._store = store
        self._router = router
        self._config = config
        self._clock = clock
        self._emit = emit
        self._peer_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._attached = False
        self._running = False
        self._last_tick: TickReport | None = None

    async def _route_peer(self, peer: int) -> tuple[int, str | None]:
        """Routet alles Offene in ``msg_id``-Reihenfolge; stoppt beim ersten Fehler."""
        routed = 0
        async with self._peer_locks[peer]:
            while messages := await self._store.unrouted_messages(peer):
                for msg in messages:
                    try:
                        await self._router.route(msg)
                    except Exception as exc:
                        logger.warning("Routing %s/%s fehlgeschlagen: %s", peer, msg.msg_id, type(exc).__name__)
                        return routed, f"{peer}: {_describe(exc)}"
                    await self._store.mark_routed(peer, [msg.msg_id])
                    routed += 1
        return routed, None

    async def _store_new(self, messages: list[TgMessage]) -> None:
        for msg in await self._store.add_messages(messages):
            await safe_emit(self._emit, "message", msg.to_dict())

    async def tick(self) -> TickReport:
        report = TickReport(at=self._clock())
        for peer in await self._store.list_monitored():
            report.peers += 1
            try:
                messages = await self._client.messages_since(peer, await self._store.get_cursor(peer), _FETCH_LIMIT)
                await self._store_new(messages)
            except TelegramFloodWait as exc:
                report.flood_wait_s = exc.seconds
                break
            except TelegramNotAuthorized as exc:
                report.errors.append(_describe(exc))
                break
            except Exception as exc:
                report.errors.append(f"{peer}: {_describe(exc)}")
                continue
            report.fetched += len(messages)
            routed, error = await self._route_peer(peer)
            report.routed += routed
            if error is not None:
                report.errors.append(error)
            elif messages:
                await self._store.advance_cursor(peer, max(m.msg_id for m in messages))
        self._last_tick = report
        return report

    async def _on_live(self, msg: TgMessage) -> None:
        try:
            if msg.peer not in await self._store.list_monitored():
                return
            await self._store_new([msg])
            await self._route_peer(msg.peer)
        except Exception as exc:
            # Der naechste Tick holt die Nachricht nach; der Listener muss weiterleben.
            logger.warning("Live-Nachricht nicht verarbeitet: %s", type(exc).__name__)

    def attach_live(self) -> None:
        if not self._attached:
            self._attached = True
            self._client.on_new_message(self._on_live)

    async def run(self, stop: asyncio.Event) -> None:
        self._running = True
        try:
            while not stop.is_set():
                wait_s = self._config.gather_interval_s
                try:
                    report = await self.tick()
                    wait_s = max(wait_s, report.flood_wait_s or 0)
                except Exception as exc:
                    logger.exception("Gather-Tick fehlgeschlagen: %s", type(exc).__name__)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), wait_s)
        finally:
            self._running = False

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "last_tick": self._last_tick.to_dict() if self._last_tick else None,
            "interval_s": self._config.gather_interval_s,
        }
