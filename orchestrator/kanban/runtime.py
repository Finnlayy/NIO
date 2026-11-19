"""Zusammenbau und Lebenszyklus der Kanban-Komponenten (Dependency Injection).

``build_runtime(config)`` waehlt die Adapter anhand der Config (SQLite/Postgres,
In-Process/Redis, Subprocess/Docker) und verdrahtet sie einmal -- CLI und API
teilen sich so genau eine Konstruktionsstelle.
"""

from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.breaker import CircuitBreaker
from orchestrator.kanban.bus import HeartbeatStore, KanbanBus, LockManager, TokenStore
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.decomposer import ChecklistDecomposer
from orchestrator.kanban.dispatcher import Dispatcher
from orchestrator.kanban.models import KanbanEvent, new_id
from orchestrator.kanban.notify import Notifier, build_notifier
from orchestrator.kanban.reaper import Reaper
from orchestrator.kanban.sandbox import SandboxRunner, build_sandbox
from orchestrator.kanban.service import KanbanService
from orchestrator.kanban.store import KanbanStore
from orchestrator.kanban.tools import KanbanToolbox
from orchestrator.kanban.vault import ObsidianVault

__all__ = ["KanbanRuntime", "SandboxAgentRegistry", "build_runtime"]


class SandboxAgentRegistry:
    """Hält die laufenden SandboxAgents der Runtime, damit ``/abort`` sie erreicht.

    Die Registry kennt nur das Abbruch-Protokoll ``abort(session_id, reason, detail)``
    und importiert keine Ciel-Klassen; Agenten melden sich über ``register`` an.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}

    def register(self, name: str, agent: Any) -> None:
        if not name:
            raise ValueError("Agent-Name darf nicht leer sein")
        self._agents[name] = agent

    def unregister(self, name: str) -> None:
        self._agents.pop(name, None)

    def names(self) -> list[str]:
        return sorted(self._agents)

    def abort_session(self, session_id: str, reason: str, detail: str = "") -> int:
        """Sendet das Abbruchsignal an alle Agenten. Gibt die Zahl der ausgelösten Signale zurück."""
        return sum(int(agent.abort(session_id, reason, detail)) for agent in self._agents.values())


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
    #: Control-Plane-Singletons (Phase 4), in ``build_runtime`` verdrahtet.
    dag: Any = None
    policy: Any = None
    agents: SandboxAgentRegistry = field(default_factory=SandboxAgentRegistry)

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

    runtime = KanbanRuntime(
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

    # 5. Control Plane: DAG-Gedächtnis und Pre-Execution-Policy (Redis, sonst In-Memory)
    from apollo.ciel.dag_state import DAGStateManager, InMemoryDAGStore, RedisDAGStore

    dag_store: Any = RedisDAGStore(client) if client is not None else InMemoryDAGStore()
    runtime.dag = DAGStateManager(dag_store)
    runtime.policy = build_pre_execution_policy(runtime)
    return runtime


def build_pre_execution_policy(
    runtime: Any,
    *,
    tool_tiers: Mapping[str, Any] | None = None,
    **engine_kwargs: Any,
) -> Any:
    """Baut die Ciel-Pre-Execution-Policy über die Kanban-Infrastruktur.

    Bewusst nur gebaut, nicht global eingeschaltet: der Aufrufer reicht das
    Ergebnis an ``SandboxAgent(policy_engine=...)`` weiter.

    * Store: Redis (Lua-Gate über ``runtime.redis``), sonst In-Memory.
    * ``on_audit`` schreibt ins Hash-Kettenprotokoll (``AuditLedger``). Die
      Kategorie ist ``system`` mit Aktion ``approval.<aktion>``, weil das
      SQL-``CHECK`` auf ``audit_ledger.category`` nur die fünf bestehenden
      Kategorien erlaubt (Schemaänderung nicht Teil dieser Änderung).
    * ``on_ticket`` benachrichtigt über ``runtime.notifier``; ein Fehler dort
      blockiert die Policy nicht.
    """
    from apollo.ciel.policy_gate import (
        InMemoryPolicyStore,
        PreExecutionPolicyEngine,
        RedisPolicyStore,
        resp_eval_shim,
    )

    if getattr(runtime, "redis", None) is not None:
        store: Any = RedisPolicyStore(resp_eval_shim(runtime.redis))
    else:
        store = InMemoryPolicyStore()
    ledger = runtime.ledger
    notifier = runtime.notifier

    async def on_audit(action: str, payload: dict[str, Any]) -> None:
        await ledger.append(
            actor="policy",
            action=f"approval.{action}",
            category="system",
            subject=str(payload.get("ticket_id", "")),
            payload=payload,
        )

    async def on_ticket(ticket: Any) -> None:
        await notifier.alert(f"Freigabe nötig: Tool {ticket.tool} (Ticket {ticket.id})")
        # Zusätzlich auf den Bus, damit das Frontend per SSE sofort sieht. Nur Ticket-Metadaten, keine Argumente.
        bus = getattr(runtime, "bus", None)
        if bus is not None:
            await bus.publish(
                KanbanEvent(
                    kind="approval.pending",
                    payload={
                        "ticket_id": ticket.id,
                        "session_id": ticket.session_id,
                        "tool": ticket.tool,
                        "status": str(ticket.status),
                        "expires_ms": ticket.expires_ms,
                    },
                )
            )

    return PreExecutionPolicyEngine(
        store,
        tool_tiers=dict(tool_tiers or {}),
        on_audit=on_audit,
        on_ticket=on_ticket,
        **engine_kwargs,
    )
