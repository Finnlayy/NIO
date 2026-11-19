"""NIO Phase 5: Micro-Compaction älterer Tool-Ergebnisse und Blob-Zugriff über ``fetch_blob``."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from apollo.ciel.compactor import (
    FETCH_BLOB_TOOL_NAME,
    RECEIPT_MARKER,
    DictBlobStore,
    MicroCompactor,
    RedisBlobStore,
    blob_key,
    is_receipt,
)
from apollo.ciel.models import AssistantMessage
from apollo.ciel.registry import ColdStorageRegistry
from apollo.ciel.sandbox_agent import SandboxAgent, ScriptedLLMClient


def _big_json(seed: str, size: int = 8 * 1024) -> str:
    """Ein JSON-Ergebnis mit Skalaren und einer Liste, ca. ``size`` Bytes groß."""
    items = [{"id": i, "pad": "x" * 64} for i in range(max(1, size // 80))]
    return json.dumps({"status": "ok", "symbol": seed, "price": 1.5, "items": items}, ensure_ascii=False)


def _tool_turn(call_id: str, content: str, name: str = "scan") -> list[dict[str, Any]]:
    return [
        {"role": "assistant", "content": "", "tool_calls": [{"id": call_id, "name": name, "arguments": {}}]},
        {"role": "tool", "tool_call_id": call_id, "name": name, "content": content},
    ]


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Compaction
# ---------------------------------------------------------------------------


def test_two_large_results_compacted_to_small_receipts() -> None:
    first, second = _big_json("AAA"), _big_json("BBB")
    messages = [*_tool_turn("c1", first), *_tool_turn("c2", second)]
    compactor = MicroCompactor(byte_threshold=1024, keep_recent_tool_turns=1)

    out = _run(compactor.compact(messages, session_id="s1"))

    old_tool = out[1]
    assert old_tool["role"] == "tool"
    assert old_tool["tool_call_id"] == "c1"
    assert len(old_tool["content"].encode("utf-8")) < 600
    assert is_receipt(old_tool["content"])
    receipt = json.loads(old_tool["content"])
    assert receipt["_receipt"] == RECEIPT_MARKER
    assert receipt["status"] == "ok"
    assert receipt["symbol"] == "AAA"
    assert receipt["price"] == 1.5
    assert receipt["items_count"] == len(json.loads(first)["items"])


def test_blob_restores_original_losslessly() -> None:
    original = _big_json("AAA")
    store = DictBlobStore()
    compactor = MicroCompactor(byte_threshold=1024, keep_recent_tool_turns=1, blob_store=store)
    messages = [*_tool_turn("c1", original), *_tool_turn("c2", "small")]

    out = _run(compactor.compact(messages, session_id="s1"))

    ref = json.loads(out[1]["content"])["blob_ref"]
    assert ref == blob_key("s1", "c1") == "nio:blob:s1:c1"
    assert _run(store.get(ref)) == original


def test_last_tool_result_is_untouched() -> None:
    last = _big_json("CCC")
    messages = [*_tool_turn("c1", _big_json("AAA")), *_tool_turn("c2", last)]
    compactor = MicroCompactor(byte_threshold=1024, keep_recent_tool_turns=1)

    out = _run(compactor.compact(messages, session_id="s1"))

    assert out[-1]["content"] == last
    assert out[-1]["tool_call_id"] == "c2"


def test_compacting_twice_creates_no_nested_receipts() -> None:
    messages = [*_tool_turn("c1", _big_json("AAA")), *_tool_turn("c2", _big_json("BBB"))]
    compactor = MicroCompactor(byte_threshold=1024, keep_recent_tool_turns=1)

    once = _run(compactor.compact(messages, session_id="s1"))
    twice = _run(compactor.compact(once, session_id="s1"))

    assert twice == once
    assert json.loads(twice[1]["content"])["_receipt"] == RECEIPT_MARKER
    assert twice[1]["content"].count('"_receipt"') == 1


def test_small_results_are_not_compacted() -> None:
    messages = [*_tool_turn("c1", '{"status":"ok"}'), *_tool_turn("c2", "later")]
    out = _run(MicroCompactor(byte_threshold=1024).compact(messages, session_id="s1"))
    assert out == [dict(m) for m in messages]


def test_non_json_result_gets_preview_receipt() -> None:
    text = "lorem ipsum " * 400
    messages = [*_tool_turn("c1", text), *_tool_turn("c2", "later")]
    out = _run(MicroCompactor(byte_threshold=1024).compact(messages, session_id="s1"))
    receipt = json.loads(out[1]["content"])
    assert receipt["json"] is False
    assert receipt["preview"] == text[:120]
    assert len(out[1]["content"].encode("utf-8")) < 600


def test_input_messages_are_not_mutated() -> None:
    messages = [*_tool_turn("c1", _big_json("AAA")), *_tool_turn("c2", "later")]
    snapshot = json.dumps(messages, sort_keys=True)
    _run(MicroCompactor(byte_threshold=1024).compact(messages, session_id="s1"))
    assert json.dumps(messages, sort_keys=True) == snapshot


def test_redis_blob_store_with_execute_client() -> None:
    class FakeExecuteClient:
        def __init__(self) -> None:
            self.data: dict[str, str] = {}

        async def execute(self, cmd: str, *args: str) -> Any:
            if cmd == "SET":
                self.data[args[0]] = args[1]
                return "OK"
            if cmd == "GET":
                value = self.data.get(args[0])
                return value.encode("utf-8") if value is not None else None
            raise AssertionError(cmd)

    client = FakeExecuteClient()
    store = RedisBlobStore(client)
    original = _big_json("RRR")
    messages = [*_tool_turn("c1", original), *_tool_turn("c2", "later")]
    out = _run(MicroCompactor(byte_threshold=1024, blob_store=store).compact(messages, session_id="s9"))
    ref = json.loads(out[1]["content"])["blob_ref"]
    assert client.data[ref] == original
    assert _run(store.get(ref)) == original


# ---------------------------------------------------------------------------
# Agent-Integration: Kompaktion ab Turn 2, fetch_blob, Sessionsgrenze
# ---------------------------------------------------------------------------


class _CapturingLLM(ScriptedLLMClient):
    """Spielt ein Skript ab und merkt sich Nachrichten und Tool-Namen jedes Calls."""

    def __init__(self, script: list[dict[str, Any]]) -> None:
        super().__init__(script)
        self.seen_messages: list[list[dict[str, Any]]] = []
        self.seen_tool_names: list[list[str]] = []

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        token: Any = None,
    ) -> AssistantMessage:
        self.seen_messages.append([dict(m) for m in messages])
        self.seen_tool_names.append([str(t.get("name")) for t in tools])
        return await super().complete(system=system, messages=messages, tools=tools, token=token)


def _agent_registry() -> ColdStorageRegistry:
    async def _big_handler(arguments: dict[str, Any]) -> str:
        return _big_json(str(arguments.get("symbol", "?")))

    registry = ColdStorageRegistry()
    registry.register(
        {
            "name": "scan",
            "description": "Scan a market symbol.",
            "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}},
            "handler": _big_handler,
        }
    )
    return registry


def test_agent_compacts_from_turn_two_and_keeps_stored_history_intact() -> None:
    llm = _CapturingLLM(
        [
            {"content": "", "tool_calls": [{"id": "c1", "name": "scan", "arguments": {"symbol": "AAA"}}]},
            {"content": "", "tool_calls": [{"id": "c2", "name": "scan", "arguments": {"symbol": "BBB"}}]},
            {"content": "done", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=_agent_registry(), llm=llm, compactor=MicroCompactor(byte_threshold=1024))

    result = _run(agent.run_scoped("scan two symbols", {}, session_id="sess-a"))

    assert result.final_answer == "done"
    # Turn 1 sieht den Originalverlauf: noch kein Receipt.
    assert not any(is_receipt(str(m.get("content", ""))) for m in llm.seen_messages[0])
    # Im dritten Call ist das ältere Ergebnis c1 ein Receipt, das letzte (c2) unverändert.
    third = {m.get("tool_call_id"): str(m.get("content", "")) for m in llm.seen_messages[2] if m.get("role") == "tool"}
    assert is_receipt(third["c1"])
    assert not is_receipt(third["c2"])
    assert len(third["c1"].encode("utf-8")) < 600
    # Die gespeicherten Tool-Ergebnisse bleiben vollständig.
    assert len(result.tool_results) == 2
    assert result.tool_results[0].result == _big_json("AAA")


def test_fetch_blob_returns_original_and_is_offered_to_llm() -> None:
    original_c1 = _big_json("AAA")
    llm = _CapturingLLM(
        [
            {"content": "", "tool_calls": [{"id": "c1", "name": "scan", "arguments": {"symbol": "AAA"}}]},
            {"content": "", "tool_calls": [{"id": "c2", "name": "scan", "arguments": {"symbol": "BBB"}}]},
            {
                "content": "",
                "tool_calls": [{"id": "f1", "name": FETCH_BLOB_TOOL_NAME, "arguments": {"blob_ref": "nio:blob:sess-b:c1"}}],
            },
            {"content": "fetched", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=_agent_registry(), llm=llm, compactor=MicroCompactor(byte_threshold=1024))

    result = _run(agent.run_scoped("fetch", {}, session_id="sess-b"))

    assert FETCH_BLOB_TOOL_NAME in llm.seen_tool_names[0]
    fetch = next(r for r in result.tool_results if r.name == FETCH_BLOB_TOOL_NAME)
    assert fetch.ok is True
    assert fetch.result["content"] == original_c1


def test_fetch_blob_rejects_foreign_session_reference() -> None:
    llm = _CapturingLLM(
        [
            {"content": "", "tool_calls": [{"id": "c1", "name": "scan", "arguments": {"symbol": "AAA"}}]},
            {"content": "", "tool_calls": [{"id": "c2", "name": "scan", "arguments": {"symbol": "BBB"}}]},
            {
                "content": "",
                "tool_calls": [{"id": "f1", "name": FETCH_BLOB_TOOL_NAME, "arguments": {"blob_ref": "nio:blob:OTHER:c1"}}],
            },
            {"content": "stop", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=_agent_registry(), llm=llm, compactor=MicroCompactor(byte_threshold=1024))

    result = _run(agent.run_scoped("fetch foreign", {}, session_id="sess-c"))

    fetch = next(r for r in result.tool_results if r.name == FETCH_BLOB_TOOL_NAME)
    assert fetch.ok is False
    assert "nicht in dieser Session" in fetch.error


def test_without_compactor_no_fetch_tool_and_no_receipts() -> None:
    llm = _CapturingLLM(
        [
            {"content": "", "tool_calls": [{"id": "c1", "name": "scan", "arguments": {"symbol": "AAA"}}]},
            {"content": "ok", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=_agent_registry(), llm=llm)
    _run(agent.run_scoped("plain", {}, session_id="sess-d"))
    assert FETCH_BLOB_TOOL_NAME not in llm.seen_tool_names[0]
    assert not any(is_receipt(str(m.get("content", ""))) for m in llm.seen_messages[1])
