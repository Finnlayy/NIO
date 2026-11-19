"""Tests für NIO Phase 3 (Ciel): Abbruch, Ausführungsumgebung und delegate_task.

Abgedeckt:
* SubprocessExecutionEnv: Eltern- und Enkelprozess sind nach ``cancel()`` in < 0.6 s beendet.
* SandboxAgent: Abbruch während eines hängenden Tools und während des LLM-Calls committet
  einen ``ABORTED_CLEAN``-Knoten ohne verwaiste Tool-Messages.
* Delegation: Scope-Ablehnung, erlaubte Tools, unveränderter Elternzustand, kein
  ``delegate_task`` im Kind, TIER_2 im Kind ohne Ticket, Timeout als Receipt ``TIMEOUT``.
* Token-Semantik (Kind-Tokens, Idempotenz) und Argumentprüfung.

Keine Netzwerkzugriffe, keine Dienste. Subprozesse laufen nur über ``sh`` in ``tmp_path``.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from apollo.ciel import (
    AbortReason,
    AssistantMessage,
    CancellationToken,
    ColdStorageRegistry,
    ExecutionAbortedError,
    LocalExecutionEnv,
    ReceiptStatus,
    RegistryFunctionExecutor,
    SandboxAgent,
    ScriptedLLMClient,
    SubAgentDelegator,
    SubprocessExecutionEnv,
    ToolCall,
    parse_task_spec,
)
from apollo.ciel.dag_state import DAGStateManager, InMemoryDAGStore, TurnStatus
from apollo.ciel.policy_gate import InMemoryPolicyStore, PermissionTier, PreExecutionPolicyEngine
from apollo.ciel.sandbox_agent import ABORTED_MARKER
from apollo.ciel.subagent_delegator import DELEGATE_TOOL_NAME

SESSION = "s-phase3"


def _registry(handlers: dict[str, Callable[[dict[str, Any]], Any]]) -> ColdStorageRegistry:
    registry = ColdStorageRegistry()
    for name, handler in handlers.items():
        registry.register(
            {
                "name": name,
                "description": f"Werkzeug {name}",
                "parameters": {"type": "object", "properties": {}},
                "handler": handler,
            },
            is_deterministic=True,
        )
    return registry


def _policy(tiers: dict[str, PermissionTier]) -> PreExecutionPolicyEngine:
    return PreExecutionPolicyEngine(InMemoryPolicyStore(), tool_tiers=tiers)


def _lebt(pid: int) -> bool:
    """Prüft über /proc, ob ein Prozess noch läuft. Zombies gelten als beendet."""
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            state = handle.read().rsplit(")", 1)[1].split()[0]
    except FileNotFoundError:
        return False
    return state not in ("Z", "X")


def _pid_bereit(path: Path) -> bool:
    """True, sobald die Datei eine PID enthält."""
    return path.exists() and path.read_text().strip() != ""


async def _head_node(dag: DAGStateManager, session: str) -> tuple[Any, Any]:
    view = await dag.lineage(session)
    assert view.head_turn_id is not None
    node = await dag.get_node(session, view.head_turn_id)
    assert node is not None
    return view, node


# ---------------------------------------------------------------------------
# CancellationToken
# ---------------------------------------------------------------------------


def test_token_kind_feuert_mit_eltern_aber_nicht_umgekehrt() -> None:
    async def _go() -> tuple[bool, bool, str]:
        parent = CancellationToken()
        child = parent.child()
        child.cancel(AbortReason.TIMEOUT, "nur das Kind")
        parent_after_child = parent.cancelled
        parent.cancel(AbortReason.USER_ABORT, "Elternteil")
        return parent_after_child, child.cancelled, child.reason.value if child.reason else ""

    parent_after_child, child_cancelled, child_reason = asyncio.run(_go())
    assert parent_after_child is False
    assert child_cancelled is True
    assert child_reason == "TIMEOUT"


def test_token_erste_ursache_gewinnt_und_callbacks_laufen_einmal() -> None:
    seen: list[str] = []
    token = CancellationToken()
    token.on_cancel(lambda reason, detail: seen.append(f"{reason.value}:{detail}"))
    token.cancel(AbortReason.USER_ABORT, "erst")
    token.cancel(AbortReason.TIMEOUT, "später")
    assert seen == ["USER_ABORT:erst"]
    assert token.reason == AbortReason.USER_ABORT
    with pytest.raises(ExecutionAbortedError):
        token.raise_if_cancelled()


def test_local_env_timeout_liefert_timed_out() -> None:
    async def _slow(arguments: dict[str, Any]) -> Any:
        await asyncio.sleep(10)
        return {}

    registry = _registry({"slow": _slow})
    env = LocalExecutionEnv(RegistryFunctionExecutor(registry))
    result = asyncio.run(env.execute(ToolCall(id="c1", name="slow"), token=CancellationToken(), timeout_s=0.05))
    assert result.ok is False
    assert result.timed_out is True


# ---------------------------------------------------------------------------
# SubprocessExecutionEnv
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not os.path.isdir("/proc/self"), reason="Prozessprüfung benötigt Linux /proc")
def test_subprocess_abbruch_beendet_eltern_und_enkelprozess_unter_0_6s(tmp_path: Path) -> None:
    parent_file = tmp_path / "parent.pid"
    child_file = tmp_path / "child.pid"
    script = f'sleep 30 & echo $! > "{child_file}"; echo $$ > "{parent_file}"; wait'
    env = SubprocessExecutionEnv(lambda call: ["sh", "-c", script])

    async def _go() -> tuple[Any, float, int, int]:
        token = CancellationToken()
        task = asyncio.ensure_future(env.execute(ToolCall(id="c1", name="hang"), token=token, timeout_s=20))
        for _ in range(300):
            if _pid_bereit(parent_file) and _pid_bereit(child_file):
                break
            await asyncio.sleep(0.02)
        parent_pid = int(parent_file.read_text())
        child_pid = int(child_file.read_text())
        started = time.monotonic()
        token.cancel(AbortReason.USER_ABORT)
        result = await asyncio.wait_for(task, timeout=3)
        return result, time.monotonic() - started, parent_pid, child_pid

    result, elapsed, parent_pid, child_pid = asyncio.run(_go())
    assert result.ok is False
    assert result.error == "ABORTED:USER_ABORT"
    assert elapsed < 0.6, f"Abbruch dauerte {elapsed:.3f}s"
    assert not _lebt(parent_pid), "Elternprozess lebt noch"
    assert not _lebt(child_pid), "Enkelprozess lebt noch"


# ---------------------------------------------------------------------------
# SandboxAgent: Abbruch
# ---------------------------------------------------------------------------


def test_abort_waehrend_haengendem_tool_committet_aborted_clean_ohne_waisen() -> None:
    tool_started = asyncio.Event()

    async def _haengend(arguments: dict[str, Any]) -> Any:
        tool_started.set()
        await asyncio.sleep(10)
        return {"ok": True}

    registry = _registry({"haengend": _haengend})
    llm = ScriptedLLMClient([AssistantMessage(content="", tool_calls=[ToolCall(id="c1", name="haengend", arguments={})])])
    dag = DAGStateManager(InMemoryDAGStore())
    agent = SandboxAgent(registry=registry, llm=llm, dag_manager=dag, policy_engine=_policy({"haengend": PermissionTier.TIER_1_GUARD}))

    async def _go() -> tuple[int, Any, float]:
        task = asyncio.ensure_future(agent.run("Werkzeug starten", session_id=SESSION))
        await asyncio.wait_for(tool_started.wait(), timeout=3)
        await asyncio.sleep(0.05)
        started = time.monotonic()
        cancelled = agent.abort(SESSION, AbortReason.USER_ABORT)
        result = await asyncio.wait_for(task, timeout=1.0)
        return cancelled, result, time.monotonic() - started

    cancelled, result, elapsed = asyncio.run(_go())
    assert cancelled == 1
    assert elapsed < 0.5
    assert result.final_answer == ABORTED_MARKER == "[ABORTED_CLEAN]"
    view, node = asyncio.run(_head_node(dag, SESSION))
    assert node.status == TurnStatus.ABORTED_CLEAN
    assert not any(m.get("role") == "tool" for m in view.messages), "verwaiste Tool-Message im DAG"
    assert not any(m.get("tool_calls") for m in view.messages), "halber Assistant-Tool-Call im DAG"


def test_abort_waehrend_llm_call_kehrt_sofort_zurueck() -> None:
    llm_started = asyncio.Event()

    class _LangsamesLLM:
        async def complete(
            self,
            *,
            system: str,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]],
            token: CancellationToken | None = None,
        ) -> AssistantMessage:
            llm_started.set()
            await asyncio.sleep(10)
            return AssistantMessage(content="zu spät")

    dag = DAGStateManager(InMemoryDAGStore())
    agent = SandboxAgent(registry=_registry({}), llm=_LangsamesLLM(), dag_manager=dag)

    async def _go() -> tuple[Any, float]:
        task = asyncio.ensure_future(agent.run("nichts Besonderes", session_id="s-llm"))
        await asyncio.wait_for(llm_started.wait(), timeout=3)
        await asyncio.sleep(0.05)
        started = time.monotonic()
        agent.abort("s-llm", AbortReason.USER_ABORT)
        result = await asyncio.wait_for(task, timeout=1.0)
        return result, time.monotonic() - started

    result, elapsed = asyncio.run(_go())
    assert elapsed < 0.5
    assert result.final_answer == ABORTED_MARKER
    assert "ABORTED:USER_ABORT" in result.errors
    _view, node = asyncio.run(_head_node(dag, "s-llm"))
    assert node.status == TurnStatus.ABORTED_CLEAN


# ---------------------------------------------------------------------------
# Delegation
# ---------------------------------------------------------------------------


def _delegate_call(call_id: str, **args: Any) -> AssistantMessage:
    return AssistantMessage(content="", tool_calls=[ToolCall(id=call_id, name=DELEGATE_TOOL_NAME, arguments=args)])


def _receipt_of(result: Any) -> dict[str, Any]:
    delegated = [r for r in result.tool_results if r.name == DELEGATE_TOOL_NAME]
    assert len(delegated) == 1, "genau ein Receipt im Eltern-Buffer erwartet"
    assert delegated[0].ok is True
    return dict(delegated[0].result)


def test_delegation_scope_policy_und_elternzustand_unveraendert() -> None:
    calls: dict[str, list[dict[str, Any]]] = {"read_market": [], "nuke_account": []}

    async def read_market(arguments: dict[str, Any]) -> Any:
        calls["read_market"].append(dict(arguments))
        return {"price": 1}

    async def nuke_account(arguments: dict[str, Any]) -> Any:
        calls["nuke_account"].append(dict(arguments))
        return {"nuked": True}

    registry = _registry({"read_market": read_market, "nuke_account": nuke_account})
    llm = ScriptedLLMClient(
        [
            _delegate_call("d1", objective="Marktpreis lesen", allowed_tools=["read_market"], max_turns=3, timeout_s=5, context_slice={"symbol": "BTC"}),
            AssistantMessage(
                content="",
                tool_calls=[
                    ToolCall(id="k1", name="nuke_account", arguments={}),
                    ToolCall(id="k2", name="read_market", arguments={"symbol": "BTC"}),
                    ToolCall(id="k3", name=DELEGATE_TOOL_NAME, arguments={"objective": "rekursiv"}),
                ],
            ),
            AssistantMessage(content="Preis gelesen"),
            AssistantMessage(content="fertig"),
        ]
    )
    policy = _policy({"read_market": PermissionTier.TIER_1_GUARD, "nuke_account": PermissionTier.TIER_1_GUARD})
    delegator = SubAgentDelegator(registry=registry, llm=llm, policy_engine=policy)
    agent = SandboxAgent(registry=registry, llm=llm, policy_engine=policy, delegator=delegator)

    parent_state: dict[str, Any] = {"symbol": "ETH", "nested": {"a": 1}}
    original = {"symbol": "ETH", "nested": {"a": 1}}
    result = asyncio.run(agent.run("Marktdaten holen", parent_state, session_id="s-deleg"))

    receipt = _receipt_of(result)
    assert receipt["status"] == ReceiptStatus.COMPLETED
    assert receipt["executed_tools"] == ["read_market"]
    assert receipt["summary"] == "Preis gelesen"
    assert calls["nuke_account"] == [], "nicht erlaubtes Tool wurde ausgeführt"
    assert calls["read_market"] == [{"symbol": "BTC"}]
    # llm.seen_tools: 0 Eltern, 1..2 Kind, 3 Eltern
    child_tools = llm.seen_tools[1]
    assert "read_market" in child_tools
    assert "nuke_account" not in child_tools
    assert DELEGATE_TOOL_NAME not in child_tools, "Kind sieht delegate_task"
    assert parent_state == original, "Elternzustand wurde verändert"
    assert result.final_answer == "fertig"


def test_kind_tier2_ergibt_failed_ohne_ticket() -> None:
    calls: list[dict[str, Any]] = []

    async def risky(arguments: dict[str, Any]) -> Any:
        calls.append(dict(arguments))
        return {"ok": True}

    registry = _registry({"risky": risky})
    llm = ScriptedLLMClient(
        [
            _delegate_call("d1", objective="riskante Order", allowed_tools=["risky"], timeout_s=5),
            AssistantMessage(content="", tool_calls=[ToolCall(id="k1", name="risky", arguments={"qty": 1})]),
            AssistantMessage(content="abgebrochen"),
            AssistantMessage(content="fertig"),
        ]
    )
    policy = _policy({"risky": PermissionTier.TIER_2_APPROVAL})
    delegator = SubAgentDelegator(registry=registry, llm=llm, policy_engine=policy)
    agent = SandboxAgent(registry=registry, llm=llm, policy_engine=policy, delegator=delegator)

    result = asyncio.run(agent.run("Order platzieren", {"qty": 0}, session_id="s-t2"))

    receipt = _receipt_of(result)
    assert receipt["status"] == ReceiptStatus.FAILED
    assert "TIER_2" in receipt["summary"]
    assert calls == []
    assert asyncio.run(policy.pending_tickets()) == [], "Kind hat ein eigenes Ticket angelegt"


def test_delegation_timeout_liefert_receipt_timeout() -> None:
    class _ElternDannHaengendesKind:
        def __init__(self) -> None:
            self.calls = 0
            self.seen_tools: list[list[str]] = []

        async def complete(
            self,
            *,
            system: str,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]],
            token: CancellationToken | None = None,
        ) -> AssistantMessage:
            self.calls += 1
            self.seen_tools.append([str(t.get("name", "?")) for t in tools])
            if self.calls == 1:
                return _delegate_call("d1", objective="langsam", allowed_tools=[], timeout_s=0.15)
            if self.calls == 2:
                await asyncio.sleep(5)
            return AssistantMessage(content="fertig")

    llm = _ElternDannHaengendesKind()
    registry = _registry({})
    delegator = SubAgentDelegator(registry=registry, llm=llm)
    agent = SandboxAgent(registry=registry, llm=llm, delegator=delegator)

    started = time.monotonic()
    result = asyncio.run(agent.run("Teilziel delegieren", {}, session_id="s-timeout"))
    elapsed = time.monotonic() - started

    receipt = _receipt_of(result)
    assert receipt["status"] == ReceiptStatus.TIMEOUT
    assert elapsed < 2.0
    assert result.final_answer == "fertig"


@pytest.mark.parametrize(
    "arguments",
    [
        {"objective": ""},
        {"objective": "x", "max_turns": 13},
        {"objective": "x", "max_turns": 0},
        {"objective": "x", "timeout_s": 0.05},
        {"objective": "x", "timeout_s": 121},
        {"objective": "x", "allowed_tools": "read_market"},
    ],
)
def test_task_spec_lehnt_ungueltige_grenzen_ab(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        parse_task_spec(arguments)


def test_task_spec_akzeptiert_grenzwerte() -> None:
    spec = parse_task_spec({"objective": "x", "max_turns": 12, "timeout_s": 0.1, "allowed_tools": ["a"]})
    assert spec.max_turns == 12
    assert spec.timeout_s == pytest.approx(0.1)
    assert spec.allowed_tools == ["a"]
