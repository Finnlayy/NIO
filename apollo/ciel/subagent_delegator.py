"""Sub-Agenten-Delegation über das Meta-Tool ``delegate_task`` (NIO Phase 3).

Ein Elternlauf kann ein eng begrenztes Teilziel an einen Kind-Agenten abgeben:

* Der Kind-Agent sieht und führt nur ``allowed_tools`` aus (Scoped-Executor lehnt alles andere ab).
* ``delegate_task`` ist im Kind nie verfügbar (keine Rekursion).
* Er läuft mit ``copy.deepcopy(parent_state) | context_slice``; der Elternzustand bleibt unverändert.
* Abbruch des Elternteils wirkt auf das Kind (Kind-Token); ``timeout_s`` begrenzt den Lauf.
* Dieselbe Policy-Engine gilt im Kind. Ein TIER_2-Call im Kind ergibt ``FAILED`` mit Hinweis
  und legt kein eigenes Freigabe-Ticket an.
* Nur der :class:`SubAgentReceipt` landet im Eltern-Buffer.
"""

from __future__ import annotations

import asyncio
import copy
import uuid
from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Any, Final

from .errors import CielError
from .execution_env import AbortReason, CancellationToken
from .models import BaseModel, Field, ToolCall
from .ncm_gate import RegistryFunctionExecutor, ToolExecutor
from .policy_gate import PermissionTier, PreExecutionPolicyEngine
from .registry import ColdStorageRegistry

#: Name des Meta-Tools, mit dem der Elternlauf ein Teilziel delegiert.
DELEGATE_TOOL_NAME: Final[str] = "delegate_task"

#: Obergrenzen der Aufgabenspezifikation (Pflichtbereiche laut NIO-Plan).
MAX_TURNS_RANGE: Final[tuple[int, int]] = (1, 12)
TIMEOUT_RANGE_S: Final[tuple[float, float]] = (0.1, 120.0)
SUMMARY_LIMIT: Final[int] = 1200

DELEGATE_TOOL_SCHEMA: Final[dict[str, Any]] = {
    "name": DELEGATE_TOOL_NAME,
    "description": (
        "Delegiert ein eng begrenztes Teilziel an einen Sub-Agenten mit eigener Werkzeugmenge. "
        "Args: objective (str), allowed_tools (list[str]), max_turns (1-12), timeout_s (0.1-120), "
        "context_slice (dict). Liefert einen Receipt mit status, summary und executed_tools."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "objective": {"type": "string", "description": "Konkretes Teilziel in einem Satz."},
            "allowed_tools": {"type": "array", "items": {"type": "string"}, "description": "Erlaubte Tool-Namen."},
            "max_turns": {"type": "integer", "minimum": MAX_TURNS_RANGE[0], "maximum": MAX_TURNS_RANGE[1]},
            "timeout_s": {"type": "number", "minimum": TIMEOUT_RANGE_S[0], "maximum": TIMEOUT_RANGE_S[1]},
            "context_slice": {"type": "object", "description": "Zusätzlicher Kontext, überschreibt Elternzustand."},
        },
        "required": ["objective"],
    },
}


class ReceiptStatus(StrEnum):
    """Endstatus eines Sub-Agenten-Laufs."""

    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class ToolOutOfScope(CielError):
    """Der Sub-Agent hat ein Tool aufgerufen, das nicht in ``allowed_tools`` steht."""

    def __init__(self, name: str) -> None:
        self.tool_name = name
        super().__init__(f"Tool {name!r} ist für diesen Sub-Agenten nicht freigegeben.")


class SubAgentTaskSpec(BaseModel):
    """Vom Elternlauf übergebene Aufgabe. Grenzen werden zusätzlich in :func:`parse_task_spec` geprüft."""

    objective: str
    allowed_tools: list[str] = Field(default_factory=list)
    max_turns: int = Field(default=4, ge=MAX_TURNS_RANGE[0], le=MAX_TURNS_RANGE[1])
    timeout_s: float = Field(default=30.0, ge=TIMEOUT_RANGE_S[0], le=TIMEOUT_RANGE_S[1])
    context_slice: dict[str, Any] = Field(default_factory=dict)


class SubAgentReceipt(BaseModel):
    """Ergebnis eines Sub-Agenten, wie es in den Eltern-Buffer geht."""

    task_id: str
    status: ReceiptStatus
    turns_used: int = 0
    executed_tools: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=SUMMARY_LIMIT)
    extracted_data: dict[str, Any] = Field(default_factory=dict)


def parse_task_spec(arguments: Mapping[str, Any]) -> SubAgentTaskSpec:
    """Prüft die Tool-Argumente und liefert eine Aufgabe. Wirft ``ValueError`` bei Verstößen."""
    objective = arguments.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("delegate_task braucht 'objective' (nicht-leerer str).")
    allowed = arguments.get("allowed_tools", [])
    if not isinstance(allowed, list) or not all(isinstance(name, str) and name for name in allowed):
        raise ValueError("delegate_task: 'allowed_tools' muss eine Liste nicht-leerer Tool-Namen sein.")
    max_turns = arguments.get("max_turns", 4)
    if isinstance(max_turns, bool) or not isinstance(max_turns, int) or not MAX_TURNS_RANGE[0] <= max_turns <= MAX_TURNS_RANGE[1]:
        raise ValueError(f"delegate_task: 'max_turns' muss ganze Zahl {MAX_TURNS_RANGE[0]}..{MAX_TURNS_RANGE[1]} sein.")
    timeout = arguments.get("timeout_s", 30.0)
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or not TIMEOUT_RANGE_S[0] <= timeout <= TIMEOUT_RANGE_S[1]:
        raise ValueError(f"delegate_task: 'timeout_s' muss zwischen {TIMEOUT_RANGE_S[0]} und {TIMEOUT_RANGE_S[1]} liegen.")
    context = arguments.get("context_slice", {})
    if not isinstance(context, dict):
        raise ValueError("delegate_task: 'context_slice' muss ein Objekt sein.")
    return SubAgentTaskSpec(
        objective=objective,
        allowed_tools=list(allowed),
        max_turns=max_turns,
        timeout_s=float(timeout),
        context_slice=dict(context),
    )


class ScopedToolExecutor:
    """Lässt nur die freigegebenen Tools zu; alles andere wird vor dem Inneren abgelehnt."""

    def __init__(self, inner: ToolExecutor, allowed: Iterable[str]) -> None:
        self._inner = inner
        self._allowed = frozenset(allowed)

    async def execute(self, name: str, arguments: Mapping[str, Any]) -> Any:
        if name not in self._allowed:
            raise ToolOutOfScope(name)
        return await self._inner.execute(name, arguments)

    def can_execute(self, name: str) -> bool:
        return name in self._allowed and self._inner.can_execute(name)


class SubAgentDelegator:
    """Führt ``delegate_task``-Aufträge aus und liefert je Auftrag einen :class:`SubAgentReceipt`."""

    def __init__(
        self,
        *,
        registry: ColdStorageRegistry,
        llm: Any,
        executor: ToolExecutor | None = None,
        policy_engine: PreExecutionPolicyEngine | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._registry = registry
        self._llm = llm
        self._executor: ToolExecutor = executor or RegistryFunctionExecutor(registry)
        self._policy = policy_engine
        self._bus = event_bus

    async def delegate(
        self,
        arguments: Mapping[str, Any],
        *,
        parent_state: Mapping[str, Any],
        parent_token: CancellationToken,
        session_id: str,
        strategy_id: str = "default",
    ) -> SubAgentReceipt:
        """Führt den Auftrag aus. Wirft ``ValueError`` nur bei ungültigen Argumenten."""
        # Lazy-Import vermeidet den Zyklus sandbox_agent -> subagent_delegator -> sandbox_agent.
        from .sandbox_agent import META_TOOL_NAME, SandboxAgent

        spec = parse_task_spec(arguments)
        task_id = uuid.uuid4().hex[:12]
        child_token = parent_token.child()
        tier2_hit: list[str] = []

        def _tier2_guard(call: ToolCall) -> str | None:
            if self._policy is not None and self._policy.tier_for(call.name) == PermissionTier.TIER_2_APPROVAL:
                tier2_hit.append(call.name)
                return (
                    f"TIER_2 ({call.name!r}) ist im Sub-Agenten nicht erlaubt; "
                    "kein Freigabe-Ticket angelegt. Teilziel fehlgeschlagen."
                )
            return None

        child = SandboxAgent(
            registry=self._registry,
            llm=self._llm,
            executor=ScopedToolExecutor(self._executor, spec.allowed_tools),
            event_bus=self._bus,
            max_turns=spec.max_turns,
            policy_engine=self._policy,
            tool_scope=spec.allowed_tools,
            call_filter=_tier2_guard,
        )
        child_state: dict[str, Any] = copy.deepcopy(dict(parent_state)) | spec.context_slice

        try:
            result = await asyncio.wait_for(
                child.run_scoped(
                    spec.objective,
                    child_state,
                    token=child_token,
                    session_id=f"sub-{task_id}",
                    strategy_id=strategy_id,
                ),
                timeout=spec.timeout_s,
            )
        except TimeoutError:
            child_token.cancel(AbortReason.TIMEOUT, f"Teilziel überschritt {spec.timeout_s:g}s")
            return SubAgentReceipt(
                task_id=task_id,
                status=ReceiptStatus.TIMEOUT,
                summary=f"Teilziel überschritt das Zeitlimit von {spec.timeout_s:g}s.",
            )

        executed = [r.name for r in result.tool_results if r.ok and r.name != META_TOOL_NAME]
        failed = [r.name for r in result.tool_results if not r.ok]
        extracted = {
            "results": {r.name: r.result for r in result.tool_results if r.ok and r.name != META_TOOL_NAME},
            "failed": failed,
        }
        if child_token.cancelled:
            status = ReceiptStatus.ABORTED
            summary = f"Teilziel abgebrochen ({child_token.reason.value if child_token.reason else 'ABORTED'})."
        elif tier2_hit:
            status = ReceiptStatus.FAILED
            summary = f"TIER_2 im Sub-Agenten nicht erlaubt ({', '.join(sorted(set(tier2_hit)))}); kein Ticket angelegt."
        elif any(error.startswith("llm_error:") for error in result.errors):
            status = ReceiptStatus.FAILED
            summary = "LLM-Fehler im Sub-Agenten."
        else:
            status = ReceiptStatus.COMPLETED
            summary = result.final_answer

        return SubAgentReceipt(
            task_id=task_id,
            status=status,
            turns_used=result.turns,
            executed_tools=executed,
            summary=summary[:SUMMARY_LIMIT],
            extracted_data=extracted,
        )


__all__ = [
    "DELEGATE_TOOL_NAME",
    "DELEGATE_TOOL_SCHEMA",
    "MAX_TURNS_RANGE",
    "TIMEOUT_RANGE_S",
    "ReceiptStatus",
    "ScopedToolExecutor",
    "SubAgentDelegator",
    "SubAgentReceipt",
    "SubAgentTaskSpec",
    "ToolOutOfScope",
    "parse_task_spec",
]
