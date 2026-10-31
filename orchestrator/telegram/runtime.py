"""Zusammenbau und Lebenszyklus der Telegram-Komponenten.

``build_telegram_runtime`` verdrahtet alles genau einmal -- CLI, API und E2E teilen
sich diese Stelle. Der Aufbau verbindet noch nicht mit Telegram: ``connect`` tut das,
damit reine Listen-Kommandos ohne Session laufen.

``neu kanban serve`` startet Telegram nur, wenn ``NIO_TELEGRAM_API_ID`` und
``NIO_TELEGRAM_API_HASH`` gesetzt sind und Telethon installiert ist.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import logging
import sys
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.protocol import utc_now_iso

from .approvals import Approvals
from .client import TelegramError, TelegramPort, TelethonClient
from .config import TelegramConfig
from .gather import GatherLoop
from .llm import TextLLM, llm_from_config
from .models import LoginState, normalize_peer
from .router import IntelRouter, KanbanSink, Sink, SuggestionSink
from .store import SqliteTelegramStore, TelegramStore
from .symbols import SymbolIndex
from .tools import TelegramToolbox

if TYPE_CHECKING:
    from orchestrator.kanban.audit import AuditLedger
    from orchestrator.kanban.runtime import KanbanRuntime

__all__ = ["EventHub", "TelegramRuntime", "attach_telegram", "build_telegram_runtime"]

logger = logging.getLogger(__name__)

_RECONNECT_S = 30.0
_QUEUE_MAX = 256
_STALE_ERROR = "Prozess endete waehrend des Sendens, Zustellung unklar"


class EventHub:
    """Verteilt Live-Events an SSE-Abonnenten; ein langsamer Client verliert nur eigene Events."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any] | None]] = set()
        self._closed = False

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        for queue in self._queues:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait({"event": event, "data": data})

    async def subscribe(self, keepalive_s: float) -> AsyncIterator[dict[str, Any] | None]:
        """Liefert Events; ``None`` ist ein Keepalive. Endet mit ``close``."""
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(_QUEUE_MAX)
        self._queues.add(queue)
        try:
            while not self._closed:
                try:
                    item = await asyncio.wait_for(queue.get(), keepalive_s)
                except TimeoutError:
                    yield None
                    continue
                if item is None:
                    return
                yield item
        finally:
            self._queues.discard(queue)

    def close(self) -> None:
        # Offene SSE-Streams wuerden sonst das Herunterfahren von uvicorn blockieren.
        self._closed = True
        for queue in self._queues:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(None)


@dataclass
class TelegramRuntime:
    config: TelegramConfig
    store: TelegramStore
    client: TelegramPort
    symbols: SymbolIndex
    llm: TextLLM | None
    gather: GatherLoop
    approvals: Approvals
    hub: EventHub
    toolbox: TelegramToolbox
    ledger: AuditLedger | None = None
    kanban_enabled: bool = False
    clock: Callable[[], str] = utc_now_iso

    async def connect(self) -> LoginState:
        return await self.client.status()

    async def recover(self) -> list[str]:
        """Eine beim Absturz in ``sending`` haengende Suggestion waere sonst fuer immer gesperrt."""
        stale = await self.store.fail_stale_sending(_STALE_ERROR, self.clock())
        for sid in stale:
            await self._audit("telegram", "telegram.send_failed", "trading", sid, {"suggestion_id": sid, "error": _STALE_ERROR})
        return stale

    async def serve(self, stop: asyncio.Event) -> None:
        try:
            await self.recover()
            await self.symbols.ensure()
            while not stop.is_set():
                try:
                    state = await self.connect()
                except Exception as exc:
                    logger.warning("Telegram nicht erreichbar: %s", type(exc).__name__)
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(stop.wait(), _RECONNECT_S)
                    continue
                if state is not LoginState.AUTHORIZED:
                    logger.warning("Telegram nicht eingeloggt: neu telegram login")
                break
            if not stop.is_set():
                self.gather.attach_live()
                await self.gather.run(stop)
        finally:
            self.hub.close()

    async def close(self) -> None:
        self.hub.close()
        await self.client.close()
        await self.store.close()

    async def _audit(self, actor: str, action: str, category: str, subject: str, payload: Mapping[str, Any]) -> None:
        if self.ledger is not None:
            await self.ledger.append(actor=actor, action=action, category=category, subject=subject, payload=payload)

    async def status(self) -> dict[str, Any]:
        """Kein Secret, kein Session-Pfad: das geht an API und UI."""
        me: dict[str, Any] | None = None
        try:
            state = await self.connect()
            if state is LoginState.AUTHORIZED:
                me = await self.client.me()
        except Exception as exc:
            logger.warning("Telegram-Status nicht ermittelbar: %s", type(exc).__name__)
            state = LoginState.DISCONNECTED
        return {
            "state": state.value,
            "me": me,
            "flood_wait_until": getattr(self.client, "flood_wait_until", None),
            "gather": self.gather.status(),
            "symbols": self.symbols.status(),
            "llm_configured": self.llm is not None,
            "kanban_enabled": self.kanban_enabled,
            "send_rate_per_hour": self.config.send_rate_per_hour,
        }

    # -- Konfiguration zur Laufzeit --------------------------------------- #
    async def monitor(self, peer: int | str, *, actor: str) -> int:
        """Startet beim neuesten Stand: ein neuer Chat darf keine Altlasten als Signale liefern."""
        resolved = await self.client.resolve_peer(peer)
        if resolved not in await self.store.list_monitored():
            await self.store.advance_cursor(resolved, await self.client.latest_msg_id(resolved))
            await self.store.add_monitored(resolved)
            await self._audit(actor, "telegram.monitor", "system", str(resolved), {"peer": resolved})
        return resolved

    async def unmonitor(self, peer: int | str, *, actor: str) -> int:
        resolved = await self._known_peer(peer)
        await self.store.remove_monitored(resolved)
        await self._audit(actor, "telegram.unmonitor", "system", str(resolved), {"peer": resolved})
        return resolved

    async def pair(self, source: int | str, target: int | str, *, actor: str) -> tuple[int, int]:
        src, dst = await self.client.resolve_peer(source), await self.client.resolve_peer(target)
        if src == dst:
            raise ValueError("Feed und Ziel muessen verschieden sein")
        await self.store.set_pairing(src, dst)
        await self._audit(actor, "telegram.pair", "system", str(src), {"source": src, "target": dst})
        return src, dst

    async def unpair(self, source: int | str, *, actor: str) -> int:
        src = await self._known_peer(source)
        await self.store.remove_pairing(src)
        await self._audit(actor, "telegram.unpair", "system", str(src), {"source": src})
        return src

    async def allow(self, peer: int | str, *, actor: str) -> int:
        """Speichert immer die numerische ID, denn Sendeziele sind numerisch."""
        resolved = await self.client.resolve_peer(peer)
        await self.store.allow(resolved)
        await self._audit(actor, "telegram.allow", "system", str(resolved), {"peer": resolved})
        return resolved

    async def disallow(self, peer: int | str, *, actor: str) -> int | str:
        norm = normalize_peer(peer)
        await self.store.disallow(norm)
        await self._audit(actor, "telegram.disallow", "system", str(norm), {"peer": norm})
        return norm

    async def _known_peer(self, peer: int | str) -> int:
        norm = normalize_peer(peer)
        return norm if isinstance(norm, int) else await self.client.resolve_peer(norm)


async def build_telegram_runtime(
    config: TelegramConfig,
    *,
    kanban: KanbanRuntime | None = None,
    client: TelegramPort | None = None,
    llm: TextLLM | None = None,
    symbols: SymbolIndex | None = None,
    store: TelegramStore | None = None,
    clock: Callable[[], str] = utc_now_iso,
) -> TelegramRuntime:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.data_dir.chmod(0o700)
    if store is None:
        store = SqliteTelegramStore(config.db_path)
    await store.init()

    client = client or TelethonClient(config)
    symbols = symbols or SymbolIndex(config.symbols_cache)
    llm = llm or llm_from_config(config)
    ledger = kanban.ledger if kanban is not None else None
    hub = EventHub()

    sinks: list[Sink] = [SuggestionSink(store, config, llm, clock=clock, emit=hub.publish)]
    kanban_enabled = kanban is not None and bool(config.kanban_board)
    if kanban is not None and kanban_enabled:
        sinks.append(KanbanSink(kanban.service, store, config, clock=clock, emit=hub.publish))
    router = IntelRouter(store, symbols, sinks, clock=clock, emit=hub.publish)

    return TelegramRuntime(
        config=config,
        store=store,
        client=client,
        symbols=symbols,
        llm=llm,
        gather=GatherLoop(client, store, router, config, clock=clock, emit=hub.publish),
        approvals=Approvals(store, client, config, ledger=ledger, clock=clock, emit=hub.publish),
        hub=hub,
        toolbox=TelegramToolbox(store, symbols, llm),
        ledger=ledger,
        kanban_enabled=kanban_enabled,
        clock=clock,
    )


def telethon_available() -> bool:
    return importlib.util.find_spec("telethon") is not None


async def attach_telegram(kanban: KanbanRuntime, *, env: Mapping[str, str] | None = None) -> TelegramRuntime | None:
    """Haengt Telegram an die Kanban-Runtime; ein Fehler hier darf ``serve`` nie stoppen."""
    try:
        config = TelegramConfig.from_env(env)
        if not config.configured:
            return None
        if not telethon_available():
            print("telegram: nicht gestartet -- Extra 'telegram' (telethon) fehlt", file=sys.stderr)
            return None
        telegram = await build_telegram_runtime(config, kanban=kanban)
    except (ValueError, OSError, TelegramError) as exc:
        logger.warning("Telegram nicht gestartet: %s", type(exc).__name__)
        return None
    kanban.telegram = telegram
    return telegram
