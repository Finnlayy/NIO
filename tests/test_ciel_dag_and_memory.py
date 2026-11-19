"""NIO Phase 2: DAG-Turn-Checkpoints, Working-Memory-Pin, episodisches FTS5-Gedächtnis, Kanban-Bridge.

Alle Tests laufen ohne Redis und ohne Netzwerk. Die Redis-Adapter werden gegen
kleine In-Process-Fakes geprüft (``redis.asyncio``-Pipeline und RESP-MULTI/EXEC).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apollo.ciel import (
    AssistantMessage,
    ColdStorageRegistry,
    DAGStateManager,
    EpisodicMemoryStore,
    InMemoryDAGStore,
    RedisDAGStore,
    RegistryFunctionExecutor,
    SandboxAgent,
    ScriptedLLMClient,
    ToolCall,
    TurnStatus,
    WorkingMemoryPin,
    register_recall_tool,
)
from apollo.ciel.dag_state import ACTIVE_KEY_FMT, BRANCHES_KEY_FMT, NODES_KEY_FMT
from apollo.ciel.memory_tier import _sanitize_fts5_query
from apollo.ciel.policy_gate import InMemoryPolicyStore, PermissionTier, PreExecutionPolicyEngine
from orchestrator.kanban.memory_bridge import KANBAN_EXPERIENCE_CATEGORY, KanbanMemoryBridge
from orchestrator.kanban.models import Experience

SID = "session-dag-1"
POLICY_SESSION = "policy-session-1"


# ---------------------------------------------------------------------------
# Fakes für die Redis-Adapter
# ---------------------------------------------------------------------------


class _FakeData:
    """Gemeinsamer Datenspeicher der Fakes (Hashes und Strings)."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def hset(self, key: str, field: str, value: str) -> int:
        self.hashes.setdefault(key, {})[field] = value
        return 1

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def set(self, key: str, value: str) -> bool:
        self.strings[key] = value
        return True

    def expire(self, key: str, ttl: int) -> bool:
        self.ttls[key] = ttl
        return True


class _FakePipeline:
    """Nachgebildete ``redis.asyncio``-Pipeline mit ``transaction=True``."""

    def __init__(self, data: _FakeData) -> None:
        self._data = data
        self._ops: list[tuple[str, tuple[Any, ...]]] = []

    def hset(self, *args: Any) -> _FakePipeline:
        self._ops.append(("hset", args))
        return self

    def set(self, *args: Any) -> _FakePipeline:
        self._ops.append(("set", args))
        return self

    def expire(self, *args: Any) -> _FakePipeline:
        self._ops.append(("expire", args))
        return self

    async def execute(self) -> list[Any]:
        results = [getattr(self._data, name)(*args) for name, args in self._ops]
        self._ops = []
        return results


class FakeAsyncioRedis:
    """Fake für einen ``redis.asyncio``-kompatiblen Client."""

    def __init__(self) -> None:
        self.data = _FakeData()

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        assert transaction is True
        return _FakePipeline(self.data)

    async def hgetall(self, key: str) -> dict[str, str]:
        return self.data.hgetall(key)

    async def get(self, key: str) -> str | None:
        return self.data.get(key)


class FakeRespRedis:
    """Fake für ``RedisClient.execute`` mit MULTI/EXEC/DISCARD-Warteschlange."""

    def __init__(self) -> None:
        self.data = _FakeData()
        self._queue: list[tuple[Any, ...]] | None = None
        self.commands: list[str] = []

    async def execute(self, *args: Any) -> Any:
        cmd = str(args[0]).upper()
        self.commands.append(cmd)
        if cmd == "MULTI":
            self._queue = []
            return "OK"
        if cmd == "DISCARD":
            self._queue = None
            return "OK"
        if cmd == "EXEC":
            assert self._queue is not None
            results = [self._run(item) for item in self._queue]
            self._queue = None
            return results
        if self._queue is not None:
            self._queue.append(args)
            return "QUEUED"
        return self._run(args)

    def _run(self, args: tuple[Any, ...]) -> Any:
        cmd = str(args[0]).upper()
        if cmd == "HSET":
            return self.data.hset(args[1], args[2], args[3])
        if cmd == "HGETALL":
            flat: list[str] = []
            for key, value in self.data.hgetall(args[1]).items():
                flat.extend([key, value])
            return flat
        if cmd == "GET":
            return self.data.get(args[1])
        if cmd == "SET":
            return self.data.set(args[1], args[2])
        if cmd == "EXPIRE":
            return self.data.expire(args[1], int(args[2]))
        raise AssertionError(f"unerwarteter Befehl im Fake: {cmd}")


# ---------------------------------------------------------------------------
# DAG: Commit, Undo, Retry
# ---------------------------------------------------------------------------


async def _commit_three(mgr: DAGStateManager) -> tuple[str, str, str]:
    t1 = await mgr.commit_turn(
        SID,
        user_input="eins",
        messages_delta=[{"role": "user", "content": "eins"}],
        working_state={"pos": "A"},
    )
    t2 = await mgr.commit_turn(
        SID,
        user_input="zwei",
        messages_delta=[{"role": "user", "content": "zwei"}, {"role": "assistant", "content": "antwort 2"}],
        working_state={"pos": "B"},
    )
    t3 = await mgr.commit_turn(
        SID,
        user_input="drei",
        messages_delta=[{"role": "user", "content": "drei"}],
        working_state={"pos": "C"},
    )
    return t1.turn_id, t2.turn_id, t3.turn_id


def test_linearer_commit_von_drei_turns_ergibt_vollstaendige_lineage() -> None:
    async def _run() -> tuple[tuple[str, str, str], Any, int]:
        mgr = DAGStateManager(InMemoryDAGStore())
        ids = await _commit_three(mgr)
        view = await mgr.lineage(SID)
        node = await mgr.get_node(SID, ids[2])
        assert node is not None
        return ids, view, node.depth

    ids, view, depth = asyncio.run(_run())
    assert view.ordered_turn_ids == list(ids)
    assert view.head_turn_id == ids[2]
    assert [m["content"] for m in view.messages] == ["eins", "zwei", "antwort 2", "drei"]
    assert view.working_state == {"pos": "C"}
    assert depth == 2


def test_undo_stellt_working_state_von_t1_wieder_her_und_loescht_nichts() -> None:
    async def _run() -> tuple[tuple[str, str, str], Any, Any]:
        mgr = DAGStateManager(InMemoryDAGStore())
        ids = await _commit_three(mgr)
        view = await mgr.undo(SID, steps=2)
        t2_node = await mgr.get_node(SID, ids[1])
        return ids, view, t2_node

    ids, view, t2_node = asyncio.run(_run())
    assert view.head_turn_id == ids[0]
    assert view.working_state == {"pos": "A"}
    assert view.ordered_turn_ids == [ids[0]]
    assert t2_node is not None
    assert t2_node.working_state == {"pos": "B"}
    assert t2_node.user_input == "zwei"


def test_undo_ueber_die_wurzel_hinaus_wird_abgewiesen() -> None:
    async def _run() -> None:
        mgr = DAGStateManager(InMemoryDAGStore())
        await mgr.commit_turn(SID, working_state={"x": 1})
        await mgr.undo(SID)
        await mgr.undo(SID)

    with pytest.raises(ValueError):
        asyncio.run(_run())


def test_retry_from_parent_und_neuer_commit_ergibt_main_und_fix_branch_mit_gemeinsamem_parent() -> None:
    async def _run() -> tuple[tuple[str, str], dict[str, str | None], Any]:
        mgr = DAGStateManager(InMemoryDAGStore())
        t1 = await mgr.commit_turn(SID, user_input="eins", working_state={"pos": "A"})
        t2 = await mgr.commit_turn(SID, user_input="zwei", working_state={"pos": "B"})
        await mgr.retry_from_parent(SID, new_branch_name="fix-branch")
        t2b = await mgr.commit_turn(SID, user_input="fix", working_state={"pos": "B2"})
        branches = await mgr.list_branches(SID)
        return (t1.turn_id, t2.turn_id), branches, t2b

    (t1_id, t2_id), branches, t2b = asyncio.run(_run())
    assert branches == {"main": t2_id, "fix-branch": t2b.turn_id}
    assert t2b.parent_turn_id == t1_id
    assert t2b.branch_name == "fix-branch"


def test_retry_laesst_den_alten_branch_unveraendert() -> None:
    async def _run() -> tuple[tuple[str, str, str], str | None, str | None]:
        mgr = DAGStateManager(InMemoryDAGStore())
        ids = await _commit_three(mgr)
        await mgr.retry_from_parent(SID, new_branch_name="fix-branch")
        t2b = await mgr.commit_turn(SID, user_input="fix", working_state={"pos": "B2"})
        t3_node = await mgr.get_node(SID, ids[2])
        assert t3_node is not None
        return ids, t2b.parent_turn_id, t3_node.parent_turn_id

    ids, t2b_parent, t3_parent = asyncio.run(_run())
    assert t2b_parent == ids[1]
    assert t3_parent == ids[1]


def test_checkout_wechselt_branch_und_setzt_kopf() -> None:
    async def _run() -> tuple[tuple[str, str, str], Any]:
        mgr = DAGStateManager(InMemoryDAGStore())
        ids = await _commit_three(mgr)
        view = await mgr.checkout_lineage(SID, target_turn_id=ids[0], branch_name="main")
        return ids, view

    ids, view = asyncio.run(_run())
    assert view.head_turn_id == ids[0]
    assert view.ordered_turn_ids == [ids[0]]


def test_checkout_mit_fremder_session_id_wird_abgewiesen() -> None:
    async def _run() -> None:
        mgr = DAGStateManager(InMemoryDAGStore())
        node = await mgr.commit_turn("andere-session", working_state={})
        await mgr.checkout_lineage(SID, target_turn_id=node.turn_id)

    with pytest.raises(ValueError):
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# DAG: Stores bleiben semantisch gleich (In-Memory, Redis-Pipeline, Redis-RESP)
# ---------------------------------------------------------------------------


def _make_store(kind: str) -> Any:
    if kind == "memory":
        return InMemoryDAGStore()
    if kind == "redis_asyncio":
        return RedisDAGStore(FakeAsyncioRedis())
    return RedisDAGStore(FakeRespRedis())


@pytest.mark.parametrize("kind", ["memory", "redis_asyncio", "redis_resp"])
def test_store_parity_commit_undo_retry(kind: str) -> None:
    async def _run() -> dict[str, Any]:
        mgr = DAGStateManager(_make_store(kind), ttl_seconds=600)
        ids = await _commit_three(mgr)
        undone = await mgr.undo(SID, steps=1)
        await mgr.retry_from_parent(SID, new_branch_name="fix")
        t_fix = await mgr.commit_turn(SID, user_input="fix", working_state={"pos": "F"})
        t3_node = await mgr.get_node(SID, ids[2])
        assert t3_node is not None
        return {
            "ids": ids,
            "undone_head": undone.head_turn_id,
            "branches": await mgr.list_branches(SID),
            "fix_parent": t_fix.parent_turn_id,
            "fix_depth": t_fix.depth,
            "fix_turn": t_fix.turn_id,
            "lineage_fix": (await mgr.lineage(SID, "fix")).ordered_turn_ids,
            "t3_state": t3_node.working_state,
        }

    out = asyncio.run(_run())
    ids = out["ids"]
    assert out["undone_head"] == ids[1]
    assert out["branches"] == {"main": ids[1], "fix": out["fix_turn"]}
    assert out["fix_parent"] == ids[0]
    assert out["fix_depth"] == 1
    assert out["lineage_fix"] == [ids[0], out["fix_turn"]]
    assert out["t3_state"] == {"pos": "C"}


def test_redis_schluesselschema_und_ttl_werden_gesetzt() -> None:
    async def _run() -> FakeRespRedis:
        client = FakeRespRedis()
        mgr = DAGStateManager(RedisDAGStore(client), ttl_seconds=123)
        await mgr.commit_turn(SID, working_state={"a": 1})
        return client

    client = asyncio.run(_run())
    assert len(client.data.hashes[NODES_KEY_FMT.format(sid=SID)]) == 1
    assert BRANCHES_KEY_FMT.format(sid=SID) in client.data.hashes
    assert client.data.strings[ACTIVE_KEY_FMT.format(sid=SID)] == "main"
    assert client.data.ttls[NODES_KEY_FMT.format(sid=SID)] == 123
    assert "MULTI" in client.commands and "EXEC" in client.commands


def test_redis_pipeline_schreibt_knoten_ueber_transaction() -> None:
    async def _run() -> FakeAsyncioRedis:
        client = FakeAsyncioRedis()
        mgr = DAGStateManager(RedisDAGStore(client))
        await mgr.commit_turn(SID, working_state={"a": 1})
        return client

    client = asyncio.run(_run())
    assert len(client.data.hashes[NODES_KEY_FMT.format(sid=SID)]) == 1


# ---------------------------------------------------------------------------
# Working-Memory-Pin
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("max_chars", [0, 1, 3, 5, 40, 1600])
def test_working_memory_pin_ueberschreitet_max_chars_nie(max_chars: int) -> None:
    pin = WorkingMemoryPin(max_chars=max_chars)
    states: list[dict[str, Any]] = [
        {},
        {"symbol": "BTC", "qty": 3},
        {"blob": "x" * 5000},
        {f"k{i}": {"nested": list(range(200))} for i in range(30)},
    ]
    for state in states:
        assert len(pin.render(state)) <= max_chars


def test_working_memory_pin_ist_deterministisch_und_sortiert() -> None:
    pin = WorkingMemoryPin()
    assert pin.render({"b": 1, "a": 2}) == pin.render({"a": 2, "b": 1})
    assert pin.render({"b": 1, "a": 2}).startswith("a: 2")


def test_working_memory_pin_kappt_mit_ellipse() -> None:
    text = WorkingMemoryPin(max_chars=40).render({"blob": "y" * 500})
    assert len(text) == 40
    assert text.endswith("...")


# ---------------------------------------------------------------------------
# Episodisches Gedächtnis
# ---------------------------------------------------------------------------

_TRADE = "Order SOL/USDC platziert: Menge 3, Kurs 145.2"
_HALT = "Halt auf halt:symbol:BTC nach Tagesverlust gesetzt"
_NOTE = "Allgemeine Notiz über Ethereum Staking und Gasgebühren"


def _seed_episodes(store: EpisodicMemoryStore) -> None:
    store.store_episode(session_id="s1", category="trade", content=_TRADE, memory_id="ep-trade", created_at_ms=1)
    store.store_episode(session_id="s1", category="risk", content=_HALT, memory_id="ep-halt", created_at_ms=2)
    store.store_episode(session_id="s1", category="note", content=_NOTE, memory_id="ep-note", created_at_ms=3)


def test_sanitize_fts5_query_quotet_und_verknuepft_tokens() -> None:
    assert _sanitize_fts5_query("halt:symbol:BTC") == '"halt" OR "symbol" OR "btc"'
    assert _sanitize_fts5_query("SOL/USDC") == '"sol" OR "usdc"'
    assert _sanitize_fts5_query("/:/") == ""


@pytest.mark.parametrize("prefer_fts", [True, False], ids=["fts5", "bm25_fallback"])
def test_recall_mit_sonderzeichen_wirft_nicht_und_rankt_relevante_episode_oben(prefer_fts: bool) -> None:
    store = EpisodicMemoryStore(prefer_fts=prefer_fts)
    if prefer_fts and not store.uses_fts:
        pytest.skip("SQLite ohne FTS5-Modul")
    assert store.uses_fts is prefer_fts
    _seed_episodes(store)

    trade = store.recall("SOL/USDC", top_k=3)
    halt = store.recall("halt:symbol:BTC", top_k=3)
    assert trade and trade[0].memory_id == "ep-trade"
    assert halt and halt[0].memory_id == "ep-halt"
    assert all(hit.memory_id != "ep-note" for hit in trade)


@pytest.mark.parametrize("prefer_fts", [True, False], ids=["fts5", "bm25_fallback"])
def test_recall_mit_fts_operatoren_im_text_wird_entschaerft(prefer_fts: bool) -> None:
    store = EpisodicMemoryStore(prefer_fts=prefer_fts)
    if prefer_fts and not store.uses_fts:
        pytest.skip("SQLite ohne FTS5-Modul")
    _seed_episodes(store)
    assert store.recall('NEAR( OR AND "') == []
    assert store.recall("/:/") == []
    assert store.recall("SOL", session_id="andere") == []
    assert store.recall("SOL", category="trade")[0].memory_id == "ep-trade"


def test_store_episode_ist_idempotent_bei_gleicher_id() -> None:
    store = EpisodicMemoryStore()
    store.store_episode(session_id="s", category="c", content="alpha beta", memory_id="same")
    store.store_episode(session_id="s", category="c", content="alpha beta", memory_id="same")
    assert len(store.recall("alpha", top_k=10)) == 1


# ---------------------------------------------------------------------------
# Recall-Tool über den Executor
# ---------------------------------------------------------------------------


def test_recall_tool_ist_ueber_registry_function_executor_ausfuehrbar() -> None:
    async def _run() -> tuple[Any, str, list[str]]:
        registry = ColdStorageRegistry()
        store = EpisodicMemoryStore()
        _seed_episodes(store)
        schema = register_recall_tool(registry, store)
        executor = RegistryFunctionExecutor(registry)
        result = await executor.execute("recall_episodic_memory", {"query": "SOL/USDC", "top_k": 2})
        return result, schema.name, list(schema.required_state_keys)

    result, name, required_state = asyncio.run(_run())
    assert name == "recall_episodic_memory"
    assert required_state == []
    assert result["query"] == "SOL/USDC"
    assert result["hits"][0]["memory_id"] == "ep-trade"
    assert len(result["hits"]) <= 2


# ---------------------------------------------------------------------------
# Kanban-Bridge
# ---------------------------------------------------------------------------


class _FakeExperienceSource:
    def __init__(self, experiences: list[Experience]) -> None:
        self._experiences = experiences

    async def list_experiences(self, *, worker_uid: str | None = None, limit: int = 100) -> list[Experience]:
        return list(self._experiences[:limit])


def test_kanban_bridge_zweimal_indizieren_erzeugt_keine_dubletten() -> None:
    experiences = [
        Experience(
            id="x-1",
            worker_uid="w-1",
            task_id="t-1",
            summary="Pull-to-Refresh im Frontend korrigiert",
            lessons=["Scroll-Container prüfen"],
            skills_delta=["css-overscroll"],
            outcome="success",
        ),
        Experience(
            id="x-2",
            worker_uid="w-2",
            task_id="t-2",
            summary="Build-Fehler bei Typen behoben",
            lessons=[],
            skills_delta=[],
            outcome="failed",
        ),
    ]

    async def _run() -> tuple[int, int, int]:
        memory = EpisodicMemoryStore()
        bridge = KanbanMemoryBridge(_FakeExperienceSource(experiences), memory)
        first = await bridge.index_experiences()
        second = await bridge.index_experiences()
        hits = memory.recall("Pull-to-Refresh Typen", top_k=10, category=KANBAN_EXPERIENCE_CATEGORY)
        return first, second, len(hits)

    first, second, hit_count = asyncio.run(_run())
    assert first == 2
    assert second == 0
    assert hit_count == 2


# ---------------------------------------------------------------------------
# Sandbox-Agent: DAG-Commit und Resume aus dem DAG
# ---------------------------------------------------------------------------


def _risky_registry(calls: list[dict[str, Any]]) -> ColdStorageRegistry:
    async def _risky(arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append(dict(arguments))
        return {"ok": True}

    registry = ColdStorageRegistry()
    registry.register(
        {
            "name": "risky",
            "description": "Platziert eine riskante Order.",
            "parameters": {"type": "object", "properties": {"qty": {"type": "integer"}}, "required": ["qty"]},
            "handler": _risky,
        },
        required_state_keys=["qty"],
        is_deterministic=True,
    )
    return registry


def _policy(store: InMemoryPolicyStore) -> PreExecutionPolicyEngine:
    return PreExecutionPolicyEngine(store, tool_tiers={"risky": PermissionTier.TIER_2_APPROVAL})


def test_phase1_resume_funktioniert_nach_neuaufbau_allein_aus_dem_dag() -> None:
    async def _run() -> tuple[list[dict[str, Any]], Any, Any, Any, bool]:
        calls: list[dict[str, Any]] = []
        engine = _policy(InMemoryPolicyStore())
        dag = DAGStateManager(InMemoryDAGStore())

        first = SandboxAgent(
            registry=_risky_registry(calls),
            llm=ScriptedLLMClient([AssistantMessage(content="", tool_calls=[ToolCall(id="c1", name="risky", arguments={"qty": 1})])]),
            policy_engine=engine,
            dag_manager=dag,
        )
        waiting = await first.run("riskante Order platzieren", session_id=POLICY_SESSION)
        assert waiting.final_answer.startswith("WAITING_APPROVAL:")
        ticket_id = waiting.final_answer.split(":", 1)[1]
        assert calls == []

        # Neuer Agent mit neuer Registry; DAG und Policy sind dieselben, der Lauf kommt allein aus dem DAG.
        rebuilt = SandboxAgent(
            registry=_risky_registry(calls),
            llm=ScriptedLLMClient([AssistantMessage(content="fertig")]),
            policy_engine=engine,
            dag_manager=dag,
        )
        await engine.resolve_ticket(ticket_id, approved=True, operator_id="finn")
        resumed = await rebuilt.resume_after_approval(POLICY_SESSION, ticket_id)
        view = await dag.lineage(POLICY_SESSION)
        head = await dag.get_node(POLICY_SESSION, view.head_turn_id or "")
        second_resume = await rebuilt.resume_after_approval(POLICY_SESSION, ticket_id)
        return calls, resumed, view, head, bool(second_resume.errors)

    calls, resumed, view, head, second_rejected = asyncio.run(_run())
    assert calls == [{"qty": 1}]
    assert resumed.final_answer == "fertig"
    assert resumed.errors == []
    assert len(view.ordered_turn_ids) == 2
    assert head is not None
    assert head.status == TurnStatus.COMPLETED
    assert second_rejected is True


def test_waiting_knoten_enthaelt_ausstehenden_call_und_ticket() -> None:
    async def _run() -> tuple[str, Any]:
        calls: list[dict[str, Any]] = []
        dag = DAGStateManager(InMemoryDAGStore())
        agent = SandboxAgent(
            registry=_risky_registry(calls),
            llm=ScriptedLLMClient([AssistantMessage(content="", tool_calls=[ToolCall(id="c1", name="risky", arguments={"qty": 2})])]),
            policy_engine=_policy(InMemoryPolicyStore()),
            dag_manager=dag,
        )
        waiting = await agent.run("riskante Order platzieren", session_id=POLICY_SESSION)
        view = await dag.lineage(POLICY_SESSION)
        node = await dag.get_node(POLICY_SESSION, view.head_turn_id or "")
        return waiting.final_answer.split(":", 1)[1], node

    ticket_id, node = asyncio.run(_run())
    assert node is not None
    assert node.status == TurnStatus.WAITING_APPROVAL
    assert node.pending is not None
    assert node.pending["ticket_id"] == ticket_id
    assert node.pending["call"]["arguments"] == {"qty": 2}


def test_abgeschlossener_turn_wird_als_dag_knoten_committet() -> None:
    async def _run() -> Any:
        dag = DAGStateManager(InMemoryDAGStore())
        agent = SandboxAgent(
            registry=ColdStorageRegistry(),
            llm=ScriptedLLMClient([AssistantMessage(content="hallo zurück")]),
            dag_manager=dag,
        )
        await agent.run("sag hallo", session_id="plain-session")
        return await dag.lineage("plain-session")

    view = asyncio.run(_run())
    assert len(view.ordered_turn_ids) == 1
    assert view.messages[0]["content"] == "sag hallo"


def test_llm_fehler_wird_als_failed_committet() -> None:
    class _BrokenLLM:
        async def complete(self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AssistantMessage:
            raise RuntimeError("Netz weg")

    async def _run() -> Any:
        dag = DAGStateManager(InMemoryDAGStore())
        agent = SandboxAgent(registry=ColdStorageRegistry(), llm=_BrokenLLM(), dag_manager=dag)  # type: ignore[arg-type]
        await agent.run("irgendwas", session_id="broken-session")
        view = await dag.lineage("broken-session")
        return await dag.get_node("broken-session", view.head_turn_id or "")

    node = asyncio.run(_run())
    assert node is not None
    assert node.status == TurnStatus.FAILED
