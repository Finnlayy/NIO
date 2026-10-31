"""Zusammenbau und Lebenszyklus der Kanban-Komponenten (Dependency Injection).

``build_runtime(config)`` waehlt die Adapter anhand der Config (SQLite/Postgres,
In-Process/Redis, Subprocess/Docker) und verdrahtet sie einmal -- CLI und API
teilen sich so genau eine Konstruktionsstelle.
"""

from __future__ import annotations

import asyncio
import os
import socket
from dataclasses import dataclass
from typing import Any, cast

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.breaker import CircuitBreaker
from orchestrator.kanban.bus import HeartbeatStore, KanbanBus, LockManager, TokenStore
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.decomposer import ChecklistDecomposer
from orchestrator.kanban.dispatcher import Dispatcher
from orchestrator.kanban.models import new_id
from orchestrator.kanban.notify import Notifier, build_notifier
from orchestrator.kanban.reaper import Reaper
from orchestrator.kanban.sandbox import SandboxRunner, build_sandbox
from orchestrator.kanban.service import KanbanService
from orchestrator.kanban.store import KanbanStore
from orchestrator.kanban.tools import KanbanToolbox
from orchestrator.kanban.vault import ObsidianVault

__all__ = ["KanbanRuntime", "build_runtime"]


@dataclass
class KanbanRuntime:
    config: KanbanConfig
    store: KanbanStore
    bus: KanbanBus
    locks: LockManager
    heartbeats: HeartbeatStore
    tokens: TokenStore
    ledger: AuditLedger
    service: KanbanService
    toolbox: KanbanToolbox
    dispatcher: Dispatcher
    reaper: Reaper
    vault: ObsidianVault
    notifier: Notifier
    sandbox: SandboxRunner
    redis: Any = None
    telegram: Any = None

    async def close(self) -> None:
        if self.telegram is not None:
            await self.telegram.close()
        sandbox_close = getattr(self.sandbox, "close", None)
        if callable(sandbox_close):
            await sandbox_close()
        store_close = getattr(self.store, "close", None)
        if callable(store_close):
            await store_close()
        await self.bus.close()
        if self.redis is not None:
            await self.redis.close()

    async def serve(self, stop: asyncio.Event) -> None:
        tasks = [
            asyncio.create_task(self.dispatcher.run(stop)),
            asyncio.create_task(self.reaper.run(stop)),
        ]
        if self.telegram is not None:
            tasks.append(asyncio.create_task(self.telegram.serve(stop)))
        await asyncio.gather(*tasks)


async def build_runtime(config: KanbanConfig, *, neu_events: Any = None) -> KanbanRuntime:
    # 1. Store
    if config.store == "postgres":
        import importlib

        store_pg = importlib.import_module("orchestrator.kanban.store_pg")
        store: KanbanStore = store_pg.PostgresKanbanStore(config.pg_dsn)
    else:
        from orchestrator.kanban.store import SqliteKanbanStore

        store = SqliteKanbanStore(config.sqlite_path)
    await store.init()

    # 2. Bus, Locks, Heartbeats, Tokens
    raw_bus: KanbanBus
    client: Any = None
    if config.bus == "redis":
        from orchestrator.kanban.redis_resp import (
            RedisBus,
            RedisClient,
            RedisHeartbeatStore,
            RedisLockManager,
            RedisTokenStore,
        )

        client = RedisClient.from_url(config.redis_url)
        raw_bus = RedisBus(client)
        locks: LockManager = RedisLockManager(client)
        heartbeats: HeartbeatStore = RedisHeartbeatStore(client)
        tokens: TokenStore = RedisTokenStore(client)
    else:
        from orchestrator.kanban.bus import InMemoryHeartbeatStore, InMemoryLockManager, InMemoryTokenStore, InProcessBus

        raw_bus = InProcessBus()
        locks = InMemoryLockManager()
        heartbeats = InMemoryHeartbeatStore()
        tokens = InMemoryTokenStore()

    bus: KanbanBus = raw_bus
    if neu_events is not None:
        from orchestrator.kanban.bus import NeuEventBridge

        bus = cast(KanbanBus, NeuEventBridge(bus=neu_events, kanban_bus=raw_bus))

    # 3. Ledger, Vault, Notifier, Sandbox, Decomposer
    ledger = AuditLedger(store)
    vault = ObsidianVault(config.vault_dir)
    notifier = build_notifier(config)
    sandbox = build_sandbox(config)
    decomposer = ChecklistDecomposer()

    # 4. Service, Breaker, Dispatcher, Reaper
    service = KanbanService(
        store=store,
        bus=bus,
        ledger=ledger,
        heartbeats=heartbeats,
        tokens=tokens,
        config=config,
    )
    toolbox = KanbanToolbox(service, tokens)
    breaker = CircuitBreaker(
        store,
        ledger,
        notifier,
        bus_service=bus,
        threshold=config.breaker_threshold,
        cooldown_s=config.breaker_cooldown_s,
    )
    dispatcher = Dispatcher(
        store=store,
        service=service,
        locks=locks,
        heartbeats=heartbeats,
        tokens=tokens,
        sandbox=sandbox,
        breaker=breaker,
        vault=vault,
        decomposer=decomposer,
        config=config,
        # Pro Prozess eindeutig: Lock-Freigabe prueft den Owner, ein fester Name
        # liesse zwei Dispatcher gegenseitig ihre Locks loesen.
        owner_id=f"{socket.gethostname()}-{os.getpid()}-{new_id('d')}",
    )
    reaper = Reaper(
        store=store,
        heartbeats=heartbeats,
        breaker=breaker,
        vault=vault,
        config=config,
        dispatcher=dispatcher,
    )

    return KanbanRuntime(
        config=config,
        store=store,
        bus=bus,
        locks=locks,
        heartbeats=heartbeats,
        tokens=tokens,
        ledger=ledger,
        service=service,
        toolbox=toolbox,
        dispatcher=dispatcher,
        reaper=reaper,
        vault=vault,
        notifier=notifier,
        sandbox=sandbox,
        redis=client,
    )
