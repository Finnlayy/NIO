"""Event-Bus des Orchestrators (Phase 1).

Jeder Zustandsubergang (Intent angenommen, Policy entschieden, Limb gestartet,
Result erfasst, Verdict gefaellt, archiviert) wird als strukturiertes Event
emittiert. Sinks entscheiden, wohin die Ereignisse fliessen.

Phase 1 liefert bewusst **nur** die Konsole als Sink. Die persistente
``runtime/system.log`` wird in Phase 3 rekursiv vom Bootstrap-Limb selbst
ergaenzt (Ouroboros-Test) -- deshalb ist hier eine klar markierte Andockstelle:

    NEU-PHASE-3-ANCHOR -> build_event_bus()
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Protocol, TextIO


class EventSink(Protocol):
    """Ein Sink nimmt fertig serialisierte Event-Datensaetze entgegen."""

    name: str

    def write(self, record: Mapping[str, Any]) -> None:  # pragma: no cover - Protokoll
        ...


@dataclass(frozen=True)
class Event:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    timestamp: str = ""
    job_id: str = ""
    trace_id: str = ""
    intent_id: str = ""
    limb: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "job_id": self.job_id,
            "trace_id": self.trace_id,
            "intent_id": self.intent_id,
            "limb": self.limb,
            "payload": dict(self.payload),
        }


class ConsoleSink:
    """Schreibt Events als JSON-Zeilen auf einen Textstrom (Default: stderr).

    stderr statt stdout, damit stdout fuer das jeweilige Ergebnis reserviert
    bleibt (Pipe-Sicherheit: ``... | jq``).
    """

    name = "console"

    def __init__(self, stream: TextIO | None = None, quiet: bool = False) -> None:
        self.stream = stream or sys.stderr
        self.quiet = quiet

    def write(self, record: Mapping[str, Any]) -> None:
        if self.quiet:
            return
        try:
            self.stream.write(json.dumps(dict(record), ensure_ascii=False) + "\n")
            self.stream.flush()
        except (ValueError, OSError):  # Ein Log-Sink darf die Pipeline nie toeten
            pass


class CollectingSink:
    """Sammelt Events im Speicher -- fuer Tests und fuer die CLI-Zusammenfassung."""

    name = "collector"

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def write(self, record: Mapping[str, Any]) -> None:
        self.records.append(dict(record))

    def kinds(self) -> list[str]:
        return [str(r.get("kind")) for r in self.records]


class EventBus:
    """Nummeriert, zeitstempelt und verteilt Ereignisse an alle Sinks."""

    def __init__(self, sinks: Iterable[EventSink] | None = None) -> None:
        self._sinks: list[EventSink] = list(sinks or [])
        self._seq = 0

    def subscribe(self, sink: EventSink) -> None:
        self._sinks.append(sink)

    @property
    def sinks(self) -> tuple[EventSink, ...]:
        return tuple(self._sinks)

    def emit(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        job_id: str = "",
        trace_id: str = "",
        intent_id: str = "",
        limb: str = "",
    ) -> Event:
        self._seq += 1
        event = Event(
            kind=kind,
            payload=dict(payload or {}),
            seq=self._seq,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            job_id=job_id or trace_id,
            trace_id=trace_id,
            intent_id=intent_id,
            limb=limb,
        )
        record = event.to_dict()
        for sink in self._sinks:
            try:
                sink.write(record)
            except Exception as exc:  # noqa: BLE001 - Logging ist niemals fatal
                sys.stderr.write(f"[events] Sink '{getattr(sink, 'name', '?')} scheiterte: {exc}\n")
        return event


def build_event_bus(*, quiet: bool = False, collector: CollectingSink | None = None, stream: TextIO | None = None) -> EventBus:
    """Standard-Bus des Orchestrators.

    NEU-PHASE-3-ANCHOR: Hier wird der persistente File-Sink (``runtime/system.log``)
    registriert, sobald der Bootstrap-Limb ihn implementiert hat. Reihenfolge
    bleibt: erst persistent, dann Konsole -- damit kein Event verloren geht.
    """
    sinks: list[EventSink] = []
    if collector is not None:
        sinks.append(collector)
    sinks.append(ConsoleSink(stream=stream, quiet=quiet))
    return EventBus(sinks)
