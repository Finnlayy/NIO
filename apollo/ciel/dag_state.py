"""DAG-Turn-Checkpoints für Apollo Ciel (NIO Phase 2).

Jeder abgeschlossene Agenten-Turn wird als unveränderlicher Knoten in einem
gerichteten Azyklischen Graphen (DAG) je Session abgelegt. Branches sind
benannte Zeiger auf einen Kopf-Knoten; ``/undo`` und ``/retry`` verschieben
nur diese Zeiger und löschen nie einen Knoten.

Speicher:

* :class:`InMemoryDAGStore` — Standard, prozesslokal, mit ``asyncio.Lock``.
* :class:`RedisDAGStore` — Schlüssel ``nio:dag:{sid}:nodes`` (Hash),
  ``nio:dag:{sid}:branches`` (Hash) und ``nio:dag:{sid}:active_branch``
  (String). Schreibvorgänge laufen als MULTI/EXEC bzw.
  ``pipeline(transaction=True)``. Unterstützt werden ein ``redis.asyncio``-
  kompatibler Client und ``orchestrator.kanban.redis_resp.RedisClient``.

Kopplung: keine Imports aus ``orchestrator``/``core``/``workspace``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, Protocol

from .models import BaseModel, ConfigDict, Field

#: Name des Start-Branches einer Session.
DEFAULT_BRANCH: Final[str] = "main"
#: Standard-Lebensdauer der Session-Schlüssel in Sekunden (24 h).
DEFAULT_TTL_SECONDS: Final[int] = 86400

NODES_KEY_FMT: Final[str] = "nio:dag:{sid}:nodes"
BRANCHES_KEY_FMT: Final[str] = "nio:dag:{sid}:branches"
ACTIVE_KEY_FMT: Final[str] = "nio:dag:{sid}:active_branch"


class TurnStatus(StrEnum):
    """Endstatus eines Turns."""

    COMPLETED = "COMPLETED"
    ABORTED_CLEAN = "ABORTED_CLEAN"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    FAILED = "FAILED"


class DAGTurnNode(BaseModel):
    """Ein unveränderlicher Checkpoint eines Turns.

    ``pending`` ist nur bei ``WAITING_APPROVAL`` gesetzt und enthält den
    ausstehenden Call (``call``), das Ticket (``ticket_id``) sowie den
    Snapshot des Laufs (``snapshot``), aus dem ``resume_after_approval`` weiterarbeitet.
    """

    model_config = ConfigDict(extra="ignore")

    turn_id: str
    session_id: str
    parent_turn_id: str | None = None
    branch_name: str = DEFAULT_BRANCH
    depth: int = 0
    created_at_ms: int = 0
    status: TurnStatus = TurnStatus.COMPLETED
    user_input: str = ""
    messages_delta: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls_summary: list[dict[str, Any]] = Field(default_factory=list)
    working_state_hash: str = ""
    working_state: dict[str, Any] = Field(default_factory=dict)
    pending: dict[str, Any] | None = None


@dataclass(frozen=True)
class DAGLineageView:
    """Lineage eines Branches: Wurzel bis Kopf, mit vollständigen Nachrichten."""

    session_id: str
    branch_name: str
    head_turn_id: str | None
    ordered_turn_ids: list[str]
    messages: list[dict[str, Any]]
    working_state: dict[str, Any]


@dataclass
class DAGSnapshot:
    """Gesamtzustand einer Session, wie ihn ein Store liefert."""

    nodes: dict[str, DAGTurnNode] = field(default_factory=dict)
    branches: dict[str, str | None] = field(default_factory=dict)
    active_branch: str | None = None


def working_state_hash(state: Mapping[str, Any]) -> str:
    """Stabiler Hash des Working States: sha256 über sortiertes JSON, gekürzt auf 16 Zeichen."""
    return hashlib.sha256(json.dumps(dict(state), sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _walk(nodes: Mapping[str, DAGTurnNode], head: str | None) -> list[DAGTurnNode]:
    """Läuft vom Kopf zur Wurzel und liefert die Kette Wurzel→Kopf. Zyklen werden abgewiesen."""
    chain: list[DAGTurnNode] = []
    visited: set[str] = set()
    current = head
    while current is not None:
        if current in visited:
            raise ValueError(f"Zyklus im DAG bei Turn {current!r}")
        visited.add(current)
        node = nodes.get(current)
        if node is None:
            raise ValueError(f"Turn {current!r} fehlt im Store")
        chain.append(node)
        current = node.parent_turn_id
    chain.reverse()
    return chain


def _view(snapshot: DAGSnapshot, session_id: str, branch: str) -> DAGLineageView:
    head = snapshot.branches.get(branch)
    chain = _walk(snapshot.nodes, head)
    messages = [dict(m) for node in chain for m in node.messages_delta]
    state = dict(chain[-1].working_state) if chain else {}
    return DAGLineageView(
        session_id=session_id,
        branch_name=branch,
        head_turn_id=head,
        ordered_turn_ids=[node.turn_id for node in chain],
        messages=messages,
        working_state=state,
    )


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------


class DAGStore(Protocol):
    """Persistenz eines Session-DAGs. Knoten werden als JSON-Text abgelegt."""

    async def load(self, session_id: str) -> DAGSnapshot: ...

    async def write(
        self,
        session_id: str,
        *,
        nodes: Sequence[DAGTurnNode],
        branches: Mapping[str, str | None],
        active_branch: str | None,
        ttl_seconds: int,
    ) -> None: ...


@dataclass
class _MemorySession:
    nodes: dict[str, str] = field(default_factory=dict)
    branches: dict[str, str] = field(default_factory=dict)
    active: str | None = None
    expires_at: float = 0.0


class InMemoryDAGStore:
    """Prozesslokaler Store mit identischer Semantik zum Redis-Store (JSON-Roundtrip)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, _MemorySession] = {}

    async def load(self, session_id: str) -> DAGSnapshot:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.expires_at < time.monotonic():
                self._sessions.pop(session_id, None)
                return DAGSnapshot()
            nodes = {tid: DAGTurnNode.model_validate(json.loads(raw)) for tid, raw in session.nodes.items()}
            branches: dict[str, str | None] = {name: (head or None) for name, head in session.branches.items()}
            return DAGSnapshot(nodes=nodes, branches=branches, active_branch=session.active)

    async def write(
        self,
        session_id: str,
        *,
        nodes: Sequence[DAGTurnNode],
        branches: Mapping[str, str | None],
        active_branch: str | None,
        ttl_seconds: int,
    ) -> None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.expires_at < time.monotonic():
                session = _MemorySession()
                self._sessions[session_id] = session
            for node in nodes:
                session.nodes[node.turn_id] = _dump_node(node)
            session.branches = {name: head or "" for name, head in branches.items()}
            session.active = active_branch
            session.expires_at = time.monotonic() + max(ttl_seconds, 0)


def _dump_node(node: DAGTurnNode) -> str:
    return json.dumps(node.model_dump(), ensure_ascii=False, sort_keys=True, default=str)


class _RedisCommands(Protocol):
    async def hgetall(self, key: str) -> dict[str, str]: ...

    async def get(self, key: str) -> str | None: ...

    async def transaction(self, ops: Sequence[tuple[str, tuple[Any, ...]]]) -> None: ...


def _text(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


class _AsyncioRedis:
    """Adapter für einen ``redis.asyncio``-kompatiblen Client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def hgetall(self, key: str) -> dict[str, str]:
        raw = await self._client.hgetall(key)
        return {_text(k): _text(v) for k, v in (raw or {}).items()}

    async def get(self, key: str) -> str | None:
        value = await self._client.get(key)
        return None if value is None else _text(value)

    async def transaction(self, ops: Sequence[tuple[str, tuple[Any, ...]]]) -> None:
        pipe = self._client.pipeline(transaction=True)
        for name, args in ops:
            getattr(pipe, name.lower())(*args)
        await pipe.execute()


class _RespRedis:
    """Adapter für ``orchestrator.kanban.redis_resp.RedisClient`` (``execute``)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def hgetall(self, key: str) -> dict[str, str]:
        flat = await self._client.execute("HGETALL", key) or []
        return {_text(flat[i]): _text(flat[i + 1]) for i in range(0, len(flat) - 1, 2)}

    async def get(self, key: str) -> str | None:
        value = await self._client.execute("GET", key)
        return None if value is None else _text(value)

    async def transaction(self, ops: Sequence[tuple[str, tuple[Any, ...]]]) -> None:
        await self._client.execute("MULTI")
        try:
            for name, args in ops:
                await self._client.execute(name, *args)
            await self._client.execute("EXEC")
        except Exception:
            await self._client.execute("DISCARD")
            raise


def _redis_adapter(client: Any) -> _RedisCommands:
    if hasattr(client, "pipeline"):
        return _AsyncioRedis(client)
    if hasattr(client, "execute"):
        return _RespRedis(client)
    raise TypeError("Redis-Client braucht pipeline() (redis.asyncio) oder execute() (RedisClient)")


class RedisDAGStore:
    """Redis-Store nach dem Schlüsselschema ``nio:dag:{sid}:…``."""

    def __init__(self, client: Any) -> None:
        self._redis = _redis_adapter(client)

    async def load(self, session_id: str) -> DAGSnapshot:
        raw_nodes = await self._redis.hgetall(NODES_KEY_FMT.format(sid=session_id))
        raw_branches = await self._redis.hgetall(BRANCHES_KEY_FMT.format(sid=session_id))
        active = await self._redis.get(ACTIVE_KEY_FMT.format(sid=session_id))
        nodes = {tid: DAGTurnNode.model_validate(json.loads(raw)) for tid, raw in raw_nodes.items()}
        branches: dict[str, str | None] = {name: (head or None) for name, head in raw_branches.items()}
        return DAGSnapshot(nodes=nodes, branches=branches, active_branch=active or None)

    async def write(
        self,
        session_id: str,
        *,
        nodes: Sequence[DAGTurnNode],
        branches: Mapping[str, str | None],
        active_branch: str | None,
        ttl_seconds: int,
    ) -> None:
        nodes_key = NODES_KEY_FMT.format(sid=session_id)
        branches_key = BRANCHES_KEY_FMT.format(sid=session_id)
        active_key = ACTIVE_KEY_FMT.format(sid=session_id)
        ops: list[tuple[str, tuple[Any, ...]]] = []
        for node in nodes:
            ops.append(("HSET", (nodes_key, node.turn_id, _dump_node(node))))
        for name, head in branches.items():
            ops.append(("HSET", (branches_key, name, head or "")))
        if active_branch is not None:
            ops.append(("SET", (active_key, active_branch)))
        if ttl_seconds > 0:
            for key in (nodes_key, branches_key, active_key):
                ops.append(("EXPIRE", (key, int(ttl_seconds))))
        await self._redis.transaction(ops)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class DAGStateManager:
    """Commit, Undo, Retry und Lineage-Abfragen über einem :class:`DAGStore`.

    Lese-Ändern-Schreiben-Zyklen laufen innerhalb dieses Prozesses unter einem
    ``asyncio.Lock``. Über mehrere Prozesse hinweg gibt es keine Sperre.
    """

    def __init__(self, store: DAGStore | None = None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._store: DAGStore = store or InMemoryDAGStore()
        self._ttl = int(ttl_seconds)
        self._mu = asyncio.Lock()

    @property
    def store(self) -> DAGStore:
        return self._store

    async def commit_turn(
        self,
        session_id: str,
        *,
        user_input: str = "",
        messages_delta: Sequence[Mapping[str, Any]] = (),
        tool_calls_summary: Sequence[Mapping[str, Any]] = (),
        working_state: Mapping[str, Any] | None = None,
        status: TurnStatus = TurnStatus.COMPLETED,
        pending: Mapping[str, Any] | None = None,
        branch_name: str | None = None,
    ) -> DAGTurnNode:
        """Hängt einen Turn an den Kopf des Branches (Standard: aktiver Branch) und macht ihn zum neuen Kopf."""
        state = dict(working_state or {})
        async with self._mu:
            snap = await self._store.load(session_id)
            branch = branch_name or snap.active_branch or DEFAULT_BRANCH
            head = snap.branches.get(branch)
            parent = snap.nodes.get(head) if head else None
            if head and parent is None:
                raise ValueError(f"Kopf {head!r} von Branch {branch!r} fehlt")
            node = DAGTurnNode(
                turn_id=uuid.uuid4().hex,
                session_id=session_id,
                parent_turn_id=head,
                branch_name=branch,
                depth=parent.depth + 1 if parent is not None else 0,
                created_at_ms=_now_ms(),
                status=status,
                user_input=user_input,
                messages_delta=[dict(m) for m in messages_delta],
                tool_calls_summary=[dict(s) for s in tool_calls_summary],
                working_state_hash=working_state_hash(state),
                working_state=state,
                pending=dict(pending) if pending is not None else None,
            )
            branches: dict[str, str | None] = dict(snap.branches)
            branches[branch] = node.turn_id
            await self._store.write(
                session_id,
                nodes=[node],
                branches=branches,
                active_branch=branch,
                ttl_seconds=self._ttl,
            )
            return node

    async def get_node(self, session_id: str, turn_id: str) -> DAGTurnNode | None:
        snap = await self._store.load(session_id)
        return snap.nodes.get(turn_id)

    async def lineage(self, session_id: str, branch_name: str | None = None) -> DAGLineageView:
        snap = await self._store.load(session_id)
        branch = branch_name or snap.active_branch or DEFAULT_BRANCH
        return _view(snap, session_id, branch)

    async def checkout_lineage(
        self,
        session_id: str,
        target_turn_id: str | None = None,
        branch_name: str | None = None,
    ) -> DAGLineageView:
        """Setzt den Kopf eines Branches auf ``target_turn_id`` und/oder wechselt den aktiven Branch.

        Ohne Argumente wird nur die aktuelle Lineage geliefert.
        """
        async with self._mu:
            snap = await self._store.load(session_id)
            if target_turn_id is None and branch_name is None:
                return _view(snap, session_id, snap.active_branch or DEFAULT_BRANCH)
            branches: dict[str, str | None] = dict(snap.branches)
            if target_turn_id is not None:
                target = snap.nodes.get(target_turn_id)
                if target is None:
                    raise ValueError(f"Turn {target_turn_id!r} gehört nicht zur Session {session_id!r}")
                branch = branch_name or target.branch_name
                branches[branch] = target_turn_id
            else:
                branch = branch_name or DEFAULT_BRANCH
                branches.setdefault(branch, None)
            await self._store.write(session_id, nodes=[], branches=branches, active_branch=branch, ttl_seconds=self._ttl)
            snap.branches = branches
            snap.active_branch = branch
            return _view(snap, session_id, branch)

    async def undo(self, session_id: str, steps: int = 1) -> DAGLineageView:
        """Verschiebt den Kopf des aktiven Branches um ``steps`` Schritte zurück. Löscht keine Knoten."""
        if steps < 1:
            raise ValueError("steps muss >= 1 sein")
        async with self._mu:
            snap = await self._store.load(session_id)
            branch = snap.active_branch or DEFAULT_BRANCH
            target = snap.branches.get(branch)
            if target is None:
                raise ValueError("Nichts zum Zurücknehmen: Branch ist leer")
            for _ in range(steps):
                if target is None:
                    raise ValueError("Undo über die Wurzel hinaus nicht möglich")
                target = snap.nodes[target].parent_turn_id
            branches: dict[str, str | None] = dict(snap.branches)
            branches[branch] = target
            await self._store.write(session_id, nodes=[], branches=branches, active_branch=branch, ttl_seconds=self._ttl)
            snap.branches = branches
            return _view(snap, session_id, branch)

    async def retry_from_parent(self, session_id: str, new_branch_name: str | None = None) -> DAGLineageView:
        """Legt einen neuen Branch am Elternknoten des Kopfes an und wechselt dorthin.

        Der alte Branch bleibt unverändert; der nächste Commit erzeugt einen Geschwisterknoten.
        """
        async with self._mu:
            snap = await self._store.load(session_id)
            current = snap.active_branch or DEFAULT_BRANCH
            head = snap.branches.get(current)
            if head is None:
                raise ValueError("Retry nicht möglich: Branch ist leer")
            name = new_branch_name or f"retry-{uuid.uuid4().hex[:8]}"
            if name in snap.branches:
                raise ValueError(f"Branch {name!r} existiert bereits")
            branches: dict[str, str | None] = dict(snap.branches)
            branches[name] = snap.nodes[head].parent_turn_id
            await self._store.write(session_id, nodes=[], branches=branches, active_branch=name, ttl_seconds=self._ttl)
            snap.branches = branches
            return _view(snap, session_id, name)

    async def list_branches(self, session_id: str) -> dict[str, str | None]:
        snap = await self._store.load(session_id)
        return dict(snap.branches)

    async def find_waiting(self, session_id: str, ticket_id: str) -> DAGTurnNode | None:
        """Liefert den WAITING_APPROVAL-Knoten zu einem Ticket, sofern noch kein Nachfolger existiert."""
        snap = await self._store.load(session_id)
        children = {node.parent_turn_id for node in snap.nodes.values() if node.parent_turn_id is not None}
        for node in snap.nodes.values():
            if node.status != TurnStatus.WAITING_APPROVAL or not node.pending:
                continue
            if str(node.pending.get("ticket_id", "")) != ticket_id:
                continue
            if node.turn_id in children:
                return None
            return node
        return None


__all__ = [
    "ACTIVE_KEY_FMT",
    "BRANCHES_KEY_FMT",
    "DEFAULT_BRANCH",
    "DEFAULT_TTL_SECONDS",
    "NODES_KEY_FMT",
    "DAGLineageView",
    "DAGSnapshot",
    "DAGStateManager",
    "DAGStore",
    "DAGTurnNode",
    "InMemoryDAGStore",
    "RedisDAGStore",
    "TurnStatus",
    "working_state_hash",
]
