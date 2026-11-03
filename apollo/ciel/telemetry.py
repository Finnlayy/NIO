"""Modul E: Real-Time Graph-UI Telemetry & WebSocket Events.

Damit das visuelle Graph-Dashboard die Ciel-Aktivitaet in Echtzeit rendern
kann, wird jede Routing-Entscheidung sofort als Event publiziert. Transport:

* **Event-Bus** (``orchestrator/events.py``): ``ciel.graph.event`` — fliesst
  ueber einen subscribed ``UDSBroadcastSink`` (``orchestrator/uds.py``) und
  die SSE-Route ``GET /api/telemetry/stream`` ins Dashboard. Abwaerts-
  kompatibel: neue Kinds, keine Aenderung bestehender Payloads.
* **UDS direkt** (optional): ``UDSDatagramSubscriber`` sendet als
  ``AF_UNIX``/``SOCK_DGRAM``-Datagramm an ``runtime/telemetry.sock``.

Non-Blocking (Pflichtregel 2): :meth:`CielTelemetryPublisher.publish` ist
synchron, nutzt ``put_nowait`` auf eine begrenzte ``asyncio.Queue`` und kehrt
sofort zurueck (bei voller Queue wird gezaehlt gedroppt, nie gewartet). Eine
Worker-Task verteilt an Sync-Subscriber direkt und an Async-Subscriber per
``asyncio.create_task`` — die Execution-Pipeline wird niemals verlangsamt.
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .bus import emit
from .models import BaseModel, ConfigDict, Field

#: Event-Bus-Kind aller Graph-Telemetry-Events (Payload traegt den Typ).
GRAPH_EVENT_KIND: str = "ciel.graph.event"


class CielGraphEventType(StrEnum):
    """Die vier Graph-Event-Typen (Wire-Format: der String-Wert)."""

    COLD_STATE_SYNC = "CIEL_COLD_STATE_SYNC"
    NCM_ROUTING = "CIEL_NCM_ROUTING"
    JIT_RELOAD = "CIEL_JIT_RELOAD"
    MACRO_EVOLUTION = "CIEL_MACRO_EVOLUTION"


class RoutingMode(StrEnum):
    """Gate-Modi (UI: gruener Blitz-Pfad vs. gelber LLM-Pfad)."""

    SYSTEM_1_BYPASS = "SYSTEM_1_BYPASS"
    SYSTEM_2_JIT = "SYSTEM_2_JIT"


#: Knoten-Zustaende im UI-Graphen (COLD = ausgegraut, WARM/HOT = aktiv).
NODE_COLD: str = "COLD"
NODE_WARM: str = "WARM"
NODE_HOT: str = "HOT"


class CielGraphNode(BaseModel):
    """Ein Tool-Knoten im UI-Graphen."""

    model_config = ConfigDict(extra="ignore")

    node_id: str
    tool: str
    confidence_score: float = 0.0
    status: str = NODE_COLD
    cluster: str = "fastmcp"


class CielGraphEvent(BaseModel):
    """Typsicheres Graph-Telemetry-Event (pydantic v2, mit Stdlib-Fallback)."""

    model_config = ConfigDict(extra="ignore")

    event: str
    ts: str = ""
    trace_id: str = ""
    intent: str = ""
    mode: str | None = None
    active_nodes: list[CielGraphNode] = Field(default_factory=list)
    saved_tokens_estimate: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def estimate_tokens(payload: Any) -> int:
    """Heuristische Token-Schaetzung (JSON-Laenge / 4, mind. 1).

    Deterministisch und cheap — genutzt fuer ``saved_tokens_estimate`` und
    die Pro-Tool-Kosten in der Registry.
    """
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(payload)
    return max(1, len(text) // 4)


def coerce_node(node: CielGraphNode | Mapping[str, Any]) -> CielGraphNode:
    if isinstance(node, CielGraphNode):
        return node
    return CielGraphNode.model_validate(dict(node))


def cold_state_sync_event(
    nodes: Sequence[CielGraphNode | Mapping[str, Any]],
    *,
    trace_id: str = "",
    intent: str = "",
    detail: Mapping[str, Any] | None = None,
) -> CielGraphEvent:
    """Baut ``CIEL_COLD_STATE_SYNC`` (alle Tool-Nodes als COLD an den Graphen)."""
    return CielGraphEvent(
        event=CielGraphEventType.COLD_STATE_SYNC.value,
        trace_id=trace_id,
        intent=intent,
        active_nodes=[coerce_node(n) for n in nodes],
        detail=dict(detail or {}),
    )


def routing_event(
    nodes: Sequence[CielGraphNode | Mapping[str, Any]],
    *,
    mode: str,
    intent: str = "",
    trace_id: str = "",
    saved_tokens_estimate: int = 0,
    detail: Mapping[str, Any] | None = None,
) -> CielGraphEvent:
    """Baut ``CIEL_NCM_ROUTING`` (Top-3 + Modus + Token-Saver-Counter)."""
    return CielGraphEvent(
        event=CielGraphEventType.NCM_ROUTING.value,
        trace_id=trace_id,
        intent=intent[:500],
        mode=mode,
        active_nodes=[coerce_node(n) for n in nodes],
        saved_tokens_estimate=max(0, int(saved_tokens_estimate)),
        detail=dict(detail or {}),
    )


def jit_reload_event(
    node: CielGraphNode | Mapping[str, Any],
    *,
    query: str = "",
    intent: str = "",
    trace_id: str = "",
    detail: Mapping[str, Any] | None = None,
) -> CielGraphEvent:
    """Baut ``CIEL_JIT_RELOAD`` (Nachlade-Kante im Graphen)."""
    merged = dict(detail or {})
    merged.setdefault("query", query)
    return CielGraphEvent(
        event=CielGraphEventType.JIT_RELOAD.value,
        trace_id=trace_id,
        intent=intent[:500],
        active_nodes=[coerce_node(node)],
        detail=merged,
    )


def macro_evolution_event(
    macro_node: CielGraphNode | Mapping[str, Any],
    parents: Sequence[CielGraphNode | Mapping[str, Any]] = (),
    *,
    intent: str = "",
    trace_id: str = "",
    detail: Mapping[str, Any] | None = None,
) -> CielGraphEvent:
    """Baut ``CIEL_MACRO_EVOLUTION`` (neuer Super-Node aus verschmolzenen Nodes)."""
    merged = dict(detail or {})
    nodes = [coerce_node(macro_node), *(coerce_node(p) for p in parents)]
    merged.setdefault("chain", [n.tool for n in nodes[1:]])
    return CielGraphEvent(
        event=CielGraphEventType.MACRO_EVOLUTION.value,
        trace_id=trace_id,
        intent=intent[:500],
        active_nodes=nodes,
        detail=merged,
    )


SyncSubscriber = Callable[[CielGraphEvent], None]
AsyncSubscriber = Callable[[CielGraphEvent], Awaitable[None]]


class CielTelemetryPublisher:
    """Non-blocking Graph-Telemetry-Publisher (Queue + Worker-Task).

    * :meth:`publish` ist synchron und kehrt sofort zurueck; bei voller
      Queue wird das Event gezaehlt verworfen (``dropped``), nie gewartet.
    * Die Worker-Task startet automatisch beim ersten :meth:`publish` aus
      einem laufenden Event-Loop (sonst explizit via :meth:`start`).
    * Sync-Subscriber laufen in der Worker-Task, Async-Subscriber je als
      eigene ``create_task`` (ein haengender Subscriber blockiert nie).
    * Subscriber-Fehler werden gezaehlt (``errors``), nie propagiert.
    """

    def __init__(self, *, queue_size: int = 1024) -> None:
        self._maxsize = max(1, queue_size)
        self._queue: asyncio.Queue[CielGraphEvent] = asyncio.Queue(maxsize=self._maxsize)
        self._sync_subscribers: list[SyncSubscriber] = []
        self._async_subscribers: list[AsyncSubscriber] = []
        self._worker: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.published = 0
        self.dropped = 0
        self.dispatched = 0
        self.errors = 0

    @property
    def queue_size(self) -> int:
        return self._maxsize

    @property
    def queued(self) -> int:
        return self._queue.qsize()

    def _ensure_loop(self) -> None:
        """Migriert die Queue bei Loop-Wechsel (z. B. mehrere ``asyncio.run``).

        ``asyncio.Queue`` bindet sich lazy an ihren ersten Loop; ohne diese
        Migration wuerfe jede Wiederverwendung des Publishers ueber Loop-
        Grenzen hinweg ``RuntimeError``. Wartende Events ziehen um, nichts
        geht verloren.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._loop is loop:
            return
        pending: list[CielGraphEvent] = []
        while True:
            try:
                pending.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        self._queue = asyncio.Queue(maxsize=self._maxsize)
        for event in pending:
            self._queue.put_nowait(event)
        self._worker = None
        self._loop = loop

    def add_subscriber(self, subscriber: SyncSubscriber | AsyncSubscriber) -> None:
        """Registriert einen Subscriber (async-Funktionen werden erkannt)."""
        if asyncio.iscoroutinefunction(subscriber):
            self._async_subscribers.append(subscriber)  # type: ignore[arg-type]
        else:
            self._sync_subscribers.append(subscriber)  # type: ignore[arg-type]

    def add_sync_subscriber(self, subscriber: SyncSubscriber) -> None:
        self._sync_subscribers.append(subscriber)

    def add_async_subscriber(self, subscriber: AsyncSubscriber) -> None:
        self._async_subscribers.append(subscriber)

    def publish(self, event: CielGraphEvent) -> bool:
        """Publiziert ein Event — kehrt sofort zurueck (nie blockierend).

        Gibt ``False`` zurueck, wenn die Queue voll war (Event gedroppt).
        """
        stamped = event if event.ts else event.model_copy(update={"ts": utc_now_iso()})
        if not isinstance(stamped, CielGraphEvent):
            stamped = CielGraphEvent.model_validate(stamped)
        self._ensure_loop()
        try:
            self._queue.put_nowait(stamped)
        except asyncio.QueueFull:
            self.dropped += 1
            return False
        self.published += 1
        self._ensure_worker()
        return True

    async def start(self) -> None:
        """Startet die Worker-Task explizit (sonst Auto-Start bei publish)."""
        self._ensure_loop()
        self._ensure_worker()

    async def drain(self, *, timeout: float = 5.0) -> None:
        """Wartet, bis alle queued Events verteilt sind (Tests/Shutdown)."""
        self._ensure_loop()
        self._ensure_worker()
        await asyncio.wait_for(self._queue.join(), timeout=timeout)

    async def close(self) -> None:
        """Verteilt Rest-Queue und stoppt die Worker-Task sauber."""
        try:
            await self.drain()
        finally:
            worker, self._worker = self._worker, None
            if worker is not None and not worker.done():
                worker.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await worker

    def _ensure_worker(self) -> None:
        if self._worker is not None and not self._worker.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # kein Loop (Sync-Kontext) — Events warten bis start()
        self._worker = loop.create_task(self._run(), name="ciel-telemetry")

    async def _run(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                self._dispatch(event)
                self.dispatched += 1
            except Exception:
                self.errors += 1
            finally:
                self._queue.task_done()

    def _dispatch(self, event: CielGraphEvent) -> None:
        for subscriber in self._sync_subscribers:
            try:
                subscriber(event)
            except Exception:
                self.errors += 1
        for subscriber in self._async_subscribers:
            try:
                task = asyncio.get_running_loop().create_task(subscriber(event))
            except RuntimeError:
                self.errors += 1
                continue
            task.add_done_callback(self._on_async_done)

    def _on_async_done(self, task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except Exception:
            self.errors += 1


class EventBusGraphSubscriber:
    """Sync-Subscriber: spiegelt Graph-Events auf den NEU-Event-Bus.

    Kind ist immer ``ciel.graph.event`` (siehe :data:`GRAPH_EVENT_KIND`), der
    Payload ist der volle ``CielGraphEvent``-Dump inkl. ``event``-Typ.
    """

    def __init__(self, bus: Any, *, kind: str = GRAPH_EVENT_KIND) -> None:
        self._bus = bus
        self._kind = kind
        self.forwarded = 0

    def __call__(self, event: CielGraphEvent) -> None:
        emit(self._bus, self._kind, event.model_dump())
        self.forwarded += 1


class UDSDatagramSubscriber:
    """Sync-Subscriber: sendet Graph-Events direkt als UDS-Datagramm.

    Ziel ist derselbe Socket, den ``telemetryBridge`` konsumiert
    (Default: ``runtime/telemetry.sock``). Non-blocking, fail-silent:
    Fehlt der Consumer, wird gezaehlt verworfen (``dropped``).
    """

    def __init__(self, socket_path: str | Path) -> None:
        self._path = str(socket_path)
        self.sent = 0
        self.dropped = 0

    @property
    def socket_path(self) -> str:
        return self._path

    def __call__(self, event: CielGraphEvent) -> None:
        try:
            line = (
                json.dumps(
                    {"kind": GRAPH_EVENT_KIND, "payload": event.model_dump()},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.setblocking(False)
                sock.sendto(line, self._path)
            self.sent += 1
        except OSError:
            self.dropped += 1


__all__ = [
    "GRAPH_EVENT_KIND",
    "NODE_COLD",
    "NODE_HOT",
    "NODE_WARM",
    "AsyncSubscriber",
    "CielGraphEvent",
    "CielGraphEventType",
    "CielGraphNode",
    "CielTelemetryPublisher",
    "EventBusGraphSubscriber",
    "RoutingMode",
    "SyncSubscriber",
    "UDSDatagramSubscriber",
    "coerce_node",
    "cold_state_sync_event",
    "estimate_tokens",
    "jit_reload_event",
    "macro_evolution_event",
    "routing_event",
    "utc_now_iso",
]
