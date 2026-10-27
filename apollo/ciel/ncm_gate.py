"""Modul B: System-1 NCM Gatekeeper.

Schaltet sich vor jeden LLM-Call: Der aktuelle Intent/Event-Bus-Payload wird
im Latent Concept Space (ONNX Runtime oder lokaler Embedding-Vektor) gegen
die Cold-Storage-Anchors gematcht.

* **Pfad 1 (System-1 Direct Bypass):** Confidence ``>= 0.88`` **und** alle
  benötigten Parameter liegen im State vor **und** das Tool ist als
  deterministisch markiert → direkte deterministische Ausführung, **0 Tokens**.
* **Pfad 2 (System-2 JIT Injection):** Sonst lädt das Gate nur die Top-3
  relevantesten Tool-Schemas für den Sandbox-Agenten (Modul C).
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Mapping
from typing import Any, Protocol

from .bus import emit
from .embeddings import EmbeddingProvider, cosine_similarity
from .errors import ToolNotExecutable, ToolNotFound, ToolTimeout
from .models import GateDecision, ScoredTool
from .registry import ColdStorageRegistry, ToolHandler, cluster_for, node_id_for
from .telemetry import NODE_COLD, NODE_HOT, NODE_WARM, CielTelemetryPublisher, RoutingMode, routing_event

#: Default-Schwelle für den System-1 Direct Bypass (Cosine-Confidence).
BYPASS_THRESHOLD = 0.88

#: Default-Größe der JIT-injizierten Tool-Teilmenge (Pfad 2).
JIT_TOP_K = 3


class ToolExecutor(Protocol):
    """Schnittstelle für die deterministische Tool-Ausführung (Pfad 1)."""

    async def execute(self, name: str, arguments: Mapping[str, Any]) -> Any: ...

    def can_execute(self, name: str) -> bool: ...


class RegistryFunctionExecutor:
    """Führt Registry-Handler aus (async oder sync via Worker-Thread).

    Versteht zusätzlich Makro-Pipelines (Modul D): Trägt ein Tool unter
    ``meta["pipeline"]`` eine Tool-Namensliste, werden die Schritte sequenziell
    ausgeführt; jeder Schritt erhält die Original-Argumente plus
    ``previous_result`` des Vorgängers (``None`` beim ersten Schritt).
    """

    def __init__(self, registry: ColdStorageRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> ColdStorageRegistry:
        return self._registry

    def can_execute(self, name: str) -> bool:
        record = self._registry.get(name)
        if record is None:
            return False
        if self._registry.get_handler(name) is not None:
            return True
        pipeline = (record.meta or {}).get("pipeline")
        return isinstance(pipeline, list) and all(isinstance(s, str) and self.can_execute(s) for s in pipeline)

    async def execute(self, name: str, arguments: Mapping[str, Any]) -> Any:
        record = self._registry.get(name)
        if record is None:
            raise ToolNotFound(name)
        pipeline = (record.meta or {}).get("pipeline")
        if isinstance(pipeline, list) and pipeline and self._registry.get_handler(name) is None:
            return await self._execute_pipeline(name, [str(s) for s in pipeline], dict(arguments))
        handler = self._registry.get_handler(name)
        if handler is None:
            raise ToolNotExecutable(name)
        return await run_handler(handler, dict(arguments))

    async def _execute_pipeline(self, macro: str, steps: list[str], arguments: dict[str, Any]) -> Any:
        previous: Any = None
        for step in steps:
            step_record = self._registry.require(step)
            step_args = dict(arguments)
            step_args["previous_result"] = previous
            try:
                previous = await asyncio.wait_for(self.execute(step, step_args), timeout=step_record.timeout_sec)
            except TimeoutError as exc:
                raise ToolTimeout(step, step_record.timeout_sec) from exc
        return {"macro": macro, "steps": steps, "result": previous}


def _call_convention(handler: ToolHandler) -> str:
    """Bestimmt anhand der Signatur, wie Argumente übergeben werden.

    ``"single"``: genau ein positionaler Parameter → bekommt das Argument-Dict.
    ``"kwargs"``: sonst → ``handler(**arguments)``.
    """
    try:
        params = list(inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        return "kwargs"
    positional = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    if len(positional) == 1 and not any(p.kind is p.VAR_KEYWORD for p in params):
        return "single"
    return "kwargs"


async def run_handler(handler: ToolHandler, arguments: dict[str, Any]) -> Any:
    """Ruft einen Handler auf — async direkt, sync im Worker-Thread (nie blockierend)."""
    if asyncio.iscoroutinefunction(handler):
        if _call_convention(handler) == "single":
            return await handler(arguments)
        return await handler(**arguments)
    return await run_sync_handler(handler, arguments)


async def run_sync_handler(handler: ToolHandler, arguments: dict[str, Any]) -> Any:
    """Führt einen synchronen (ggf. blockierenden) Handler im Thread aus."""

    def _call() -> Any:
        if _call_convention(handler) == "single":
            return handler(arguments)
        return handler(**arguments)

    return await asyncio.to_thread(_call)


class NCMGate:
    """System-1 NCM Gatekeeper vor jedem LLM-Call."""

    def __init__(
        self,
        registry: ColdStorageRegistry,
        *,
        embedder: EmbeddingProvider | None = None,
        executor: ToolExecutor | None = None,
        event_bus: Any | None = None,
        telemetry: CielTelemetryPublisher | None = None,
        bypass_threshold: float = BYPASS_THRESHOLD,
        top_k: int = JIT_TOP_K,
    ) -> None:
        self._registry = registry
        self._embedder = embedder or registry.embedder
        self._executor = executor or RegistryFunctionExecutor(registry)
        self._bus = event_bus
        self._telemetry = telemetry
        self._threshold = bypass_threshold
        self._top_k = top_k

    @property
    def registry(self) -> ColdStorageRegistry:
        return self._registry

    @property
    def executor(self) -> ToolExecutor:
        return self._executor

    @property
    def bypass_threshold(self) -> float:
        return self._threshold

    @property
    def top_k(self) -> int:
        return self._top_k

    @property
    def telemetry(self) -> CielTelemetryPublisher | None:
        return self._telemetry

    def match_text(self, intent: str, event_payload: Mapping[str, Any] | None = None) -> str:
        """Kombiniert Intent + Event-Bus-Payload zum NCM-Abfragetext."""
        if not event_payload:
            return intent or ""
        try:
            payload_text = json.dumps(dict(event_payload), ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            payload_text = str(event_payload)
        return f"{intent or ''}\n{payload_text}".strip()

    def match(
        self,
        intent: str,
        event_payload: Mapping[str, Any] | None = None,
        *,
        top_k: int | None = None,
    ) -> list[ScoredTool]:
        """Reines NCM-Matching (kein Routing, keine Ausführung)."""
        vector = self._embedder.embed(self.match_text(intent, event_payload))
        scored = [
            ScoredTool(name=name, score=cosine_similarity(vector, record.concept_anchor), record=record)
            for name, record in ((n, self._registry.require(n)) for n in self._registry.names())
            if record.concept_anchor
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[: max(0, self._top_k if top_k is None else top_k)]

    async def route(
        self,
        intent: str,
        state: Mapping[str, Any] | None = None,
        *,
        event_payload: Mapping[str, Any] | None = None,
        execute: bool = True,
    ) -> GateDecision:
        """Routet einen Intent: Pfad 1 (Bypass, 0 Tokens) oder Pfad 2 (JIT Top-3).

        ``state`` ist der State-Payload (z. B. aus dem Event-Bus); enthält er
        alle ``required_state_keys`` des Top-Treffers und liegt die Confidence
        über der Schwelle, wird deterministisch direkt ausgeführt.
        """
        current_state = dict(state or {})
        matches = self.match(intent, event_payload)
        if not matches:
            decision = GateDecision(path="system2_jit", confidence=0.0, reason="leere Registry — kein Matching möglich")
            emit(self._bus, "ciel.gate.decision", decision.model_dump())
            self._publish_routing(intent, [], RoutingMode.SYSTEM_2_JIT.value, [])
            return decision
        best = matches[0]
        top_names = [hit.name for hit in matches]
        required = list(best.record.required_state_keys)
        missing = [key for key in required if key not in current_state]
        bypassable = (
            execute
            and best.score >= self._threshold
            and best.record.is_deterministic
            and not missing
            and self._executor.can_execute(best.name)
        )
        if not bypassable:
            reason = self._jit_reason(best, missing)
            decision = GateDecision(
                path="system2_jit",
                confidence=round(best.score, 4),
                tool=best.name,
                top_tools=top_names,
                required_state_keys=required,
                missing_state_keys=missing,
                reason=reason,
            )
            emit(self._bus, "ciel.gate.decision", decision.model_dump())
            self._publish_routing(intent, matches, RoutingMode.SYSTEM_2_JIT.value, top_names)
            return decision
        arguments = {key: current_state[key] for key in required}
        try:
            result = await asyncio.wait_for(
                self._executor.execute(best.name, arguments),
                timeout=best.record.timeout_sec,
            )
        except TimeoutError:
            decision = GateDecision(
                path="system2_jit",
                confidence=round(best.score, 4),
                tool=best.name,
                top_tools=top_names,
                required_state_keys=required,
                missing_state_keys=missing,
                error=f"System-1-Bypass für {best.name!r} lief ins Timeout ({best.record.timeout_sec:g}s) — Fallback auf JIT.",
                reason="bypass_timeout_fallback",
            )
            emit(self._bus, "ciel.gate.decision", decision.model_dump())
            self._publish_routing(intent, matches, RoutingMode.SYSTEM_2_JIT.value, top_names)
            return decision
        except Exception as exc:
            decision = GateDecision(
                path="system2_jit",
                confidence=round(best.score, 4),
                tool=best.name,
                top_tools=top_names,
                required_state_keys=required,
                missing_state_keys=missing,
                error=f"System-1-Bypass für {best.name!r} scheiterte ({exc}) — Fallback auf JIT.",
                reason="bypass_failed_fallback",
            )
            emit(self._bus, "ciel.gate.decision", decision.model_dump())
            self._publish_routing(intent, matches, RoutingMode.SYSTEM_2_JIT.value, top_names)
            return decision
        decision = GateDecision(
            path="system1_bypass",
            confidence=round(best.score, 4),
            tool=best.name,
            top_tools=[best.name],
            required_state_keys=required,
            result=result,
            llm_calls=0,
            reason=f"confidence {best.score:.3f} >= {self._threshold:g}, deterministisch, State vollständig — 0 Tokens",
        )
        emit(self._bus, "ciel.gate.decision", decision.model_dump())
        emit(self._bus, "ciel.gate.bypass_executed", {"tool": best.name, "confidence": round(best.score, 4)})
        self._publish_routing(intent, matches, RoutingMode.SYSTEM_1_BYPASS.value, [best.name])
        return decision

    def _publish_routing(
        self,
        intent: str,
        matches: list[ScoredTool],
        mode: str,
        injected: list[str],
        *,
        trace_id: str = "",
    ) -> None:
        """Publiziert ``CIEL_NCM_ROUTING`` (Top-3 + Confidence-Kanten + Token-Saver).

        Non-blocking (Queue-``put_nowait``); ohne verdrahteten Publisher No-Op.
        Bypass-Ziel laeuft als HOT, JIT-Kandidaten als WARM, Rest bleibt COLD.
        """
        if self._telemetry is None:
            return
        injected_set = set(injected)
        bypass = mode == RoutingMode.SYSTEM_1_BYPASS.value
        nodes = [
            {
                "node_id": hit.record.node_id or node_id_for(hit.name),
                "tool": hit.name,
                "confidence_score": round(hit.score, 4),
                "status": (NODE_HOT if bypass and idx == 0 else NODE_WARM) if hit.name in injected_set else NODE_COLD,
                "cluster": cluster_for(hit.record.origin, hit.record.meta),
            }
            for idx, hit in enumerate(matches)
        ]
        self._telemetry.publish(
            routing_event(
                nodes,
                mode=mode,
                intent=intent,
                trace_id=trace_id,
                saved_tokens_estimate=self._registry.saved_tokens_estimate(injected),
                detail={"cold_tools": len(self._registry), "injected": list(injected)},
            )
        )

    def _jit_reason(self, best: ScoredTool, missing: list[str]) -> str:
        if best.score < self._threshold:
            return f"confidence {best.score:.3f} < {self._threshold:g} — Reasoning nötig (JIT Top-{self._top_k})"
        if not best.record.is_deterministic:
            return f"Top-Treffer {best.name!r} ist nicht deterministisch — Reasoning nötig (JIT Top-{self._top_k})"
        if missing:
            return f"State unvollständig (fehlt: {', '.join(missing)}) — Reasoning nötig (JIT Top-{self._top_k})"
        if not self._executor.can_execute(best.name):
            return f"Top-Treffer {best.name!r} ist schema-only (kein Handler) — Reasoning nötig (JIT Top-{self._top_k})"
        return f"Ausführung deaktiviert — JIT Top-{self._top_k}"


__all__ = [
    "BYPASS_THRESHOLD",
    "JIT_TOP_K",
    "NCMGate",
    "RegistryFunctionExecutor",
    "ToolExecutor",
    "run_handler",
    "run_sync_handler",
]
