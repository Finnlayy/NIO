"""Anbindung an den NEU-Event-Bus (``orchestrator/events.py``).

Ciel emittiert eigene Event-Kinds (``ciel.*``). Der Bus validiert Kinds
bewusst nicht — neue Kinds sind daher abwärtskompatibel und brauchen keine
Änderung in ``orchestrator/events.py``. Jede Emission ist fail-silent: Ein
Beobachtungsfehler darf die Tool-Orchestrierung niemals stoppen.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def emit(bus: Any | None, kind: str, payload: Mapping[str, Any] | None = None, **fields: Any) -> None:
    """Emittiert ein Event, wenn ein Bus verdrahtet ist (sonst No-Op).

    Duck-typed (``bus.emit(kind, payload, ...)``), damit auch fremde
    Bus-Implementierungen funktionieren.
    """
    if bus is None:
        return
    try:
        emit_fn = getattr(bus, "emit", None)
        if callable(emit_fn):
            emit_fn(kind, dict(payload or {}), **fields)
    except Exception:
        pass


#: Dokumentation der von Ciel emittierten Event-Kinds (informativ, wie
#: ``VALID_EVENT_KINDS`` in ``orchestrator/events.py`` — der Bus prüft nicht).
CIEL_EVENT_KINDS: tuple[str, ...] = (
    "ciel.registry.snapshot",  # Tools beim Start ins Cold-Storage übernommen
    "ciel.registry.cache_loaded",  # Schemas aus SQLite/JSON-Cache geladen
    "ciel.gate.decision",  # Routing-Entscheidung (system1_bypass | system2_jit)
    "ciel.gate.bypass_executed",  # Pfad 1: deterministische Direktausführung
    "ciel.sandbox.turn",  # Sandbox-Agent: LLM-Turn abgeschlossen
    "ciel.sandbox.tool_call",  # Sandbox-Agent: Tool-Aufruf beendet (ok/Fehler/Timeout)
    "ciel.sandbox.skill_reloaded",  # Meta-Tool request_additional_skill hat nachgeladen
    "ciel.synth.macro_created",  # Synthesizer hat ein Makro-Tool registriert
    "ciel.synth.chain_observed",  # Synthesizer: erfolgreiche Kette geloggt
    "ciel.graph.event",  # Modul E: typisiertes Graph-Telemetry-Event (Payload traegt den Typ)
)


__all__ = ["CIEL_EVENT_KINDS", "emit"]
