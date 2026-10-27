"""TDD-Verifikation des Ciel JIT-Tool-Orchestrators (Module A-E).

Beweist (Pflichtregel 4):

1. Bei 150 registrierten Dummy-Tools landen maximal 3 Tools + 1 Meta-Tool
   im LLM-Prompt-Payload.
2. Der System-1 Bypass feuert bei hoher Confidence ohne LLM-Aufruf.
3. Das Nachladen via ``request_additional_skill`` funktioniert zur Laufzeit.
4. Die ``CielGraphEvent``-Payloads (``SYSTEM_1_BYPASS``, ``SYSTEM_2_JIT``,
   ``CIEL_MACRO_EVOLUTION`` inkl. ``saved_tokens_estimate``) werden korrekt
   auf dem Event-Bus emittiert.

Dazu: Makro-Synthese (Modul D), Graph-Telemetry (Modul E),
SQLite-Cache-Roundtrip, FastMCP-Wrapper-Kompatibilität, Timeout-Safety und
Event-Bus-Anbindung.

Alle Tests laufen mit Plain-pytest (``asyncio.run`` in sync Tests) und sind
grün — mit wie ohne installiertem pydantic/onnxruntime.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from apollo.ciel import (
    GRAPH_EVENT_KIND,
    META_TOOL_NAME,
    CielFastMCPWrapper,
    CielGraphEvent,
    CielGraphEventType,
    CielTelemetryPublisher,
    ColdStorageRegistry,
    EventBusGraphSubscriber,
    MacroSkillSynthesizer,
    NCMGate,
    RegistryFunctionExecutor,
    RoutingMode,
    SandboxAgent,
    ScriptedLLMClient,
    ToolCall,
    build_ciel_layer,
)

# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------


async def _echo_handler(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"echo": dict(arguments)}


async def _weather_handler(arguments: dict[str, Any]) -> str:
    return f"weather:{arguments.get('city', '?')}"


class ExplodingLLM:
    """LLM-Stub, der bei jedem Aufruf explodiert (beweist 0 LLM-Calls)."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        self.calls += 1
        raise AssertionError("LLM wurde aufgerufen, obwohl der System-1 Bypass feuern muss (0 Tokens erwartet).")


def _dummy_tool(index: int) -> dict[str, Any]:
    topics = ("invoice", "calendar", "backup", "sensor", "ledger", "ticket", "inventory", "shipment")
    topic = topics[index % len(topics)]
    return {
        "name": f"dummy_tool_{index:03d}",
        "description": f"Dummy skill number {index} for {topic} bookkeeping and archival chores.",
        "parameters": {"type": "object", "properties": {"payload": {"type": "string"}}, "required": ["payload"]},
        "handler": _echo_handler,
    }


def _registry_with_150_dummies() -> ColdStorageRegistry:
    registry = ColdStorageRegistry()
    dummies = [_dummy_tool(i) for i in range(150)]
    dummies.append(
        {
            "name": "priority_escalate_ticket",
            "description": "Escalate a priority customer support ticket to the on-call engineer.",
            "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]},
            "handler": _echo_handler,
        }
    )
    registry.register_many(dummies)
    assert len(registry) == 151
    return registry


class _FakeFastMCPTool:
    def __init__(self, name: str, description: str, parameters: dict[str, Any], fn: Any) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn


class _FakeFastMCPServer:
    """Minimaler FastMCP-Doppelgänger (Tool-Decorator + Dict + call_tool)."""

    def __init__(self) -> None:
        self._tools: dict[str, _FakeFastMCPTool] = {}

    def tool(self, *dargs: Any, **dkwargs: Any) -> Any:
        name = dkwargs.get("name")
        description = dkwargs.get("description", "")

        def _decorator(func: Any) -> Any:
            tool_name = name or getattr(func, "__name__", "unnamed")
            self._tools[tool_name] = _FakeFastMCPTool(tool_name, description or tool_name, {"type": "object", "properties": {}}, func)
            return func

        if dargs and callable(dargs[0]) and len(dargs) == 1:
            return _decorator(dargs[0])
        return _decorator

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        tool = self._tools[name]
        result = tool.fn(dict(arguments or {}))
        if asyncio.iscoroutine(result):
            return await result
        return result


# ---------------------------------------------------------------------------
# Pflichtregel 4 / Beweis 1: max. 3 Tools + 1 Meta-Tool bei 150+ Tools
# ---------------------------------------------------------------------------


def test_prompt_payload_max_3_plus_meta_with_150_tools() -> None:
    registry = _registry_with_150_dummies()
    gate = NCMGate(registry)
    agent = SandboxAgent(registry=registry, gate=gate, llm=ScriptedLLMClient([]))

    decision = asyncio.run(gate.route("Escalate the priority customer support ticket please"))
    assert decision.path == "system2_jit"  # paraphrasiert + nicht deterministisch → Reasoning
    assert len(decision.top_tools) == 3
    assert "priority_escalate_ticket" in decision.top_tools  # Ziel-Skill per NCM gefunden

    payload = agent.build_prompt_payload("Escalate the priority customer support ticket please", {}, decision.top_tools)
    names = [t["name"] for t in payload["tools"]]
    assert len(payload["tools"]) == 4, f"erwartet 3 Skills + 1 Meta-Tool, bekam: {names}"
    assert names[-1] == META_TOOL_NAME
    assert "priority_escalate_ticket" in names
    # Der Rest der 151 Tools bleibt im Cold-Storage, nicht im Prompt:
    assert len(registry) == 151
    assert payload["system"]  # hart hinterlegter System-Prompt ist gesetzt
    assert "request_additional_skill" in payload["system"]
    assert "NEVER hallucinate" in payload["system"] or "never" in payload["system"].lower()


# ---------------------------------------------------------------------------
# Pflichtregel 4 / Beweis 2: System-1 Bypass ohne LLM-Aufruf
# ---------------------------------------------------------------------------


def test_system1_bypass_fires_without_llm_call() -> None:
    registry = ColdStorageRegistry()
    registry.register(
        {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            "handler": _weather_handler,
        },
        required_state_keys=["city"],
        is_deterministic=True,
    )
    llm = ExplodingLLM()
    agent = SandboxAgent(registry=registry, llm=llm)  # type: ignore[arg-type]

    intent = registry.anchor_text("get_weather")  # identischer Text → Cosine 1.0
    result = asyncio.run(agent.run(intent, {"city": "Bitburg"}))

    assert result.path == "system1_bypass"
    assert result.llm_calls == 0
    assert llm.calls == 0
    assert result.final_answer == "weather:Bitburg"
    assert result.tool_calls == ["get_weather"]
    assert not result.errors


def test_bypass_requires_full_state_and_determinism() -> None:
    registry = ColdStorageRegistry()
    registry.register(
        {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            "handler": _weather_handler,
        },
        required_state_keys=["city"],
        is_deterministic=True,
    )
    registry.register(
        {
            "name": "draft_poem",
            "description": "Draft a poem about any topic.",
            "parameters": {"type": "object", "properties": {}, "required": []},
            "handler": _echo_handler,
        },
        is_deterministic=False,  # nicht deterministisch → nie Bypass
    )
    gate = NCMGate(registry)

    # Hohe Confidence, aber State unvollständig → JIT (kein Bypass).
    decision = asyncio.run(gate.route(registry.anchor_text("get_weather"), {}))
    assert decision.path == "system2_jit"
    assert decision.missing_state_keys == ["city"]

    # Hohe Confidence, aber nicht deterministisch → JIT (kein Bypass).
    decision2 = asyncio.run(gate.route(registry.anchor_text("draft_poem"), {}))
    assert decision2.path == "system2_jit"
    assert decision2.tool == "draft_poem"


# ---------------------------------------------------------------------------
# Pflichtregel 4 / Beweis 3: request_additional_skill lädt JIT nach
# ---------------------------------------------------------------------------


def test_request_additional_skill_reloads_at_runtime() -> None:
    registry = ColdStorageRegistry()
    for i in range(3):
        registry.register(
            {
                "name": f"summarize_report_{i}",
                "description": f"Summarize the quarterly financial report section {i} for management review.",
                "parameters": {"type": "object", "properties": {"section": {"type": "string"}}, "required": []},
                "handler": _echo_handler,
            }
        )
    registry.register(
        {
            "name": "translate_text",
            "description": "Translate English text to French language.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            "handler": _echo_handler,
        }
    )
    gate = NCMGate(registry)
    decision = asyncio.run(gate.route("Summarize the quarterly financial report for management"))
    assert decision.path == "system2_jit"
    assert "translate_text" not in decision.top_tools  # fehlt in der initialen JIT-Teilmenge

    llm = ScriptedLLMClient(
        [
            {
                "content": "Need translation first.",
                "tool_calls": [{"id": "c1", "name": META_TOOL_NAME, "arguments": {"intent_query": "translate english text to french"}}],
            },
            {"content": "Translating now.", "tool_calls": [{"id": "c2", "name": "translate_text", "arguments": {"text": "hello world"}}]},
            {"content": "Done: translated.", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=registry, gate=gate, llm=llm)
    result = asyncio.run(agent.run("Summarize the quarterly financial report for management"))

    assert result.path == "system2_jit"
    assert result.llm_calls == 3
    assert "translate_text" in result.tool_calls  # nachgeladener Skill wurde ausgeführt
    echo = next(r for r in result.tool_results if r.name == "translate_text")
    assert echo.ok and echo.result == {"echo": {"text": "hello world"}}
    # Meta-Tool-Resultat enthielt das nachgeladene Schema:
    meta = next(r for r in result.tool_results if r.name == META_TOOL_NAME)
    assert meta.ok and meta.result["injected_skill"]["name"] == "translate_text"
    # Spätere Turns sahen den nachgeladenen Skill im Prompt:
    assert any("translate_text" in seen for seen in llm.seen_tools[1:])
    # Initiale Turns sahen weiterhin nur 3 + Meta:
    assert len(llm.seen_tools[0]) == 4
    assert not result.errors


# ---------------------------------------------------------------------------
# Modul D: Makro-Synthese nach 3x Erfolg
# ---------------------------------------------------------------------------


def test_macro_synthesis_after_three_consecutive_runs() -> None:
    calls: list[str] = []

    async def step_a(arguments: dict[str, Any]) -> str:
        calls.append("tool_a")
        return f"a:{arguments.get('ticket_id', '?')}"

    async def step_b(arguments: dict[str, Any]) -> str:
        calls.append("tool_b")
        return f"b<-[{arguments.get('previous_result', '?')}]"

    registry = ColdStorageRegistry()
    registry.register(
        {
            "name": "tool_a",
            "description": "First step fetches the ticket record.",
            "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]},
            "handler": step_a,
        },
        required_state_keys=["ticket_id"],
        is_deterministic=True,
    )
    registry.register(
        {
            "name": "tool_b",
            "description": "Second step notifies the owner.",
            "parameters": {"type": "object", "properties": {}, "required": []},
            "handler": step_b,
        },
        is_deterministic=True,
    )
    synth = MacroSkillSynthesizer(registry)

    first = asyncio.run(synth.log_execution(["tool_a", "tool_b"], success=True))
    second = asyncio.run(synth.log_execution(["tool_a", "tool_b"], success=True))
    assert first is not None and not first.created
    assert second is not None and not second.created
    assert "macro__tool_a__tool_b" not in registry

    third = asyncio.run(synth.log_execution(["tool_a", "tool_b"], success=True))
    assert third is not None and third.created
    assert third.macro_name == "macro__tool_a__tool_b"
    assert third.macro_name in registry

    # Makro läuft in einem Turn: beide Schritte, previous_result verkettet.
    executor = RegistryFunctionExecutor(registry)
    assert executor.can_execute(third.macro_name)
    outcome = asyncio.run(executor.execute(third.macro_name, {"ticket_id": "T-42"}))
    assert calls == ["tool_a", "tool_b"]
    assert outcome["result"] == "b<-[a:T-42]"
    assert outcome["steps"] == ["tool_a", "tool_b"]

    # Fehlschlag setzt die Streak zurück (nur hintereinander zählt).
    asyncio.run(synth.log_execution(["tool_a", "tool_b"], success=False))
    assert synth.streaks == {}


# ---------------------------------------------------------------------------
# Modul A: SQLite-Cache-Roundtrip + FastMCP-Wrapper-Kompatibilität
# ---------------------------------------------------------------------------


def test_registry_sqlite_cache_roundtrip(tmp_path: Any) -> None:
    cache = tmp_path / "ciel_cold.db"
    registry = ColdStorageRegistry(cache_path=cache)
    registry.register(
        {
            "name": "cached_skill",
            "description": "A skill that survives restarts via cache.",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
            "handler": _echo_handler,
        },
        required_state_keys=["q"],
        is_deterministic=True,
    )
    assert cache.is_file()

    reloaded = ColdStorageRegistry(cache_path=cache)
    assert "cached_skill" in reloaded  # Schema überlebt den Restart
    record = reloaded.require("cached_skill")
    assert record.required_state_keys == ["q"] and record.is_deterministic

    # Handler sind prozesslokal → schema-only bis register_handler:
    executor = RegistryFunctionExecutor(reloaded)
    assert not executor.can_execute("cached_skill")
    reloaded.register_handler("cached_skill", _echo_handler)
    assert executor.can_execute("cached_skill")
    assert asyncio.run(executor.execute("cached_skill", {"q": "hi"})) == {"echo": {"q": "hi"}}


def test_fastmcp_wrapper_is_backward_compatible() -> None:
    server = _FakeFastMCPServer()

    @server.tool(name="sys_ping", description="Ping the system bus.")
    async def sys_ping(arguments: dict[str, Any]) -> str:
        return "pong"

    registry = ColdStorageRegistry()
    wrapper = CielFastMCPWrapper(server, registry=registry)
    intercepted = asyncio.run(wrapper.ainit())
    assert intercepted == 1
    assert "sys_ping" in registry  # ins Cold-Storage abgefangen

    # Prompt bleibt kalt (keine Voll-Injektion):
    assert wrapper.tools_for_prompt() == []

    # Bestandsroute läuft unverändert weiter (über Wrapper wie direkt):
    assert asyncio.run(wrapper.call_tool("sys_ping", {})) == "pong"
    assert asyncio.run(server.call_tool("sys_ping", {})) == "pong"

    # Decorator-Interception: läuft auf dem Server weiter + spiegelt ins Cold-Storage.
    @wrapper.tool(name="sys_echo", description="Echo back.")
    async def sys_echo(arguments: dict[str, Any]) -> dict[str, Any]:
        return dict(arguments)

    assert "sys_echo" in server._tools  # Original-Registrierung ungebrochen
    assert "sys_echo" in registry  # zusätzlich gespiegelt


def test_build_ciel_layer_wiring() -> None:
    server = _FakeFastMCPServer()

    @server.tool(name="sys_ping", description="Ping the system bus.")
    async def sys_ping(arguments: dict[str, Any]) -> str:
        return "pong"

    layer = asyncio.run(build_ciel_layer(server, llm=ScriptedLLMClient([])))
    assert len(layer.registry) == 1
    assert layer.wrapper is not None and layer.wrapper.wrapped is server
    assert layer.gate.registry is layer.registry
    assert layer.agent.registry is layer.registry
    assert layer.synthesizer.registry is layer.registry


# ---------------------------------------------------------------------------
# Pflichtregel 3: Timeout-Safety — hängendes Tool blockiert nie den Loop
# ---------------------------------------------------------------------------


def test_hanging_tool_never_blocks_event_loop() -> None:
    async def hang_forever(arguments: dict[str, Any]) -> str:
        await asyncio.sleep(30)
        return "never"

    registry = ColdStorageRegistry()
    registry.register(
        {
            "name": "hang",
            "description": "A tool that hangs forever.",
            "parameters": {"type": "object", "properties": {}, "required": []},
            "handler": hang_forever,
        },
        timeout_sec=0.05,
    )
    agent = SandboxAgent(registry=registry, llm=ScriptedLLMClient([]))
    started = time.monotonic()
    result = asyncio.run(agent.execute_tool(ToolCall(id="t1", name="hang", arguments={})))
    elapsed = time.monotonic() - started

    assert not result.ok and result.timed_out
    assert "Timeout" in result.error
    assert elapsed < 10, f"Event-Loop wurde blockiert ({elapsed:.1f}s)"


# ---------------------------------------------------------------------------
# NEU-Brücke: Limb-Operations werden lesend als Tools gespiegelt (kein Bruch)
# ---------------------------------------------------------------------------


def test_limb_registry_mirror_is_read_only() -> None:
    import tempfile
    from pathlib import Path

    from core.config import NeuConfig
    from orchestrator.runner import LimbRegistry

    from . import REPO_ROOT

    registry_file = Path(REPO_ROOT) / "limbs" / "registry.json"
    before = registry_file.read_bytes()
    with tempfile.TemporaryDirectory(prefix="ciel-test-") as tmp:
        config = NeuConfig.load(REPO_ROOT, mode="dev", runtime_dir=Path(tmp) / "runtime", workspace_dir=Path(tmp) / "workspace")
        limb_registry = LimbRegistry(config)
        mirror = ColdStorageRegistry.from_limb_registry(limb_registry)
    assert len(mirror) > 0
    assert "echo.sys.ping" in mirror  # Limb-Operation als Cold-Storage-Tool
    assert mirror.require("echo.sys.ping").origin == "limb"
    assert registry_file.read_bytes() == before  # lesend: limbs/registry.json unverändert


# ---------------------------------------------------------------------------
# Event-Bus-Anbindung (abwärtskompatibel: neue ciel.*-Kinds, kein Bruch)
# ---------------------------------------------------------------------------


def test_ciel_emits_events_on_nio_event_bus() -> None:
    from orchestrator.events import CollectingSink, EventBus

    sink = CollectingSink()
    bus = EventBus([sink])
    registry = ColdStorageRegistry(event_bus=bus)
    registry.register(
        {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            "handler": _weather_handler,
        },
        required_state_keys=["city"],
        is_deterministic=True,
    )
    gate = NCMGate(registry, event_bus=bus)
    decision = asyncio.run(gate.route(registry.anchor_text("get_weather"), {"city": "Bitburg"}))

    assert decision.path == "system1_bypass"
    kinds = sink.kinds()
    assert "ciel.gate.decision" in kinds
    assert "ciel.gate.bypass_executed" in kinds


# ---------------------------------------------------------------------------
# Modul E: CielGraphEvent-Payloads auf dem Event-Bus (TDD-Forderung 4)
# ---------------------------------------------------------------------------


def _graph_payloads(sink: Any) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in sink.records:
        if record.get("kind") != GRAPH_EVENT_KIND:
            continue
        payload = record.get("payload", {})
        grouped.setdefault(str(payload.get("event", "?")), []).append(payload)
    return grouped


def test_graph_telemetry_cold_sync_and_routing_modes() -> None:
    from orchestrator.events import CollectingSink, EventBus

    sink = CollectingSink()
    bus = EventBus([sink])
    publisher = CielTelemetryPublisher()
    publisher.add_sync_subscriber(EventBusGraphSubscriber(bus))

    registry = ColdStorageRegistry(event_bus=bus, telemetry=publisher)
    for i in range(150):
        registry.register(_dummy_tool(i))
    registry.register(
        {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            "handler": _weather_handler,
        },
        required_state_keys=["city"],
        is_deterministic=True,
    )
    assert len(registry) == 151
    assert registry.publish_cold_state_sync()  # CIEL_COLD_STATE_SYNC (non-blocking)

    gate = NCMGate(registry, event_bus=bus, telemetry=publisher)
    bypass = asyncio.run(gate.route(registry.anchor_text("get_weather"), {"city": "Bitburg"}))
    assert bypass.path == "system1_bypass"
    jit = asyncio.run(gate.route("Escalate the invoice bookkeeping chores for archival"))
    assert jit.path == "system2_jit"
    asyncio.run(publisher.drain())
    asyncio.run(publisher.close())

    grouped = _graph_payloads(sink)

    # 1. CIEL_COLD_STATE_SYNC: alle Tool-Nodes als COLD inkl. Cluster + node_id.
    cold = grouped[CielGraphEventType.COLD_STATE_SYNC.value][0]
    assert len(cold["active_nodes"]) == 151
    assert {n["status"] for n in cold["active_nodes"]} == {"COLD"}
    assert all(n["node_id"].startswith("ciel-node-") and n["cluster"] for n in cold["active_nodes"])
    assert cold["detail"]["cold_tokens_total"] == registry.cold_tokens_total > 0

    # 2. CIEL_NCM_ROUTING im Bypass-Modus: 1 injiziertes Schema, Rest gespart.
    routed = grouped[CielGraphEventType.NCM_ROUTING.value]
    assert len(routed) == 2
    bypass_event = next(p for p in routed if p["mode"] == RoutingMode.SYSTEM_1_BYPASS.value)
    assert bypass_event["active_nodes"][0]["tool"] == "get_weather"
    assert bypass_event["active_nodes"][0]["status"] == "HOT"
    assert bypass_event["active_nodes"][0]["confidence_score"] >= 0.88
    assert bypass_event["detail"]["injected"] == ["get_weather"]

    # 3. CIEL_NCM_ROUTING im JIT-Modus: Top-3 mit Confidence-Kanten.
    jit_event = next(p for p in routed if p["mode"] == RoutingMode.SYSTEM_2_JIT.value)
    assert len(jit_event["active_nodes"]) == 3
    assert all("confidence_score" in n and n["node_id"] for n in jit_event["active_nodes"])

    # 4. saved_tokens_estimate: Cold (151) minus injiziert — Bypass spart mehr als JIT.
    assert bypass_event["saved_tokens_estimate"] > jit_event["saved_tokens_estimate"] > 0

    # Payloads validieren gegen das typsichere Schema (pydantic wie Fallback).
    for payload in (cold, bypass_event, jit_event):
        assert CielGraphEvent.model_validate(payload).event == payload["event"]


def test_graph_telemetry_jit_reload_and_macro_evolution() -> None:
    from orchestrator.events import CollectingSink, EventBus

    sink = CollectingSink()
    bus = EventBus([sink])
    publisher = CielTelemetryPublisher()
    publisher.add_sync_subscriber(EventBusGraphSubscriber(bus))

    registry = ColdStorageRegistry(event_bus=bus, telemetry=publisher)
    for i in range(3):
        registry.register(
            {
                "name": f"summarize_report_{i}",
                "description": f"Summarize the quarterly financial report section {i} for management review.",
                "parameters": {"type": "object", "properties": {"section": {"type": "string"}}, "required": []},
                "handler": _echo_handler,
            }
        )
    registry.register(
        {
            "name": "translate_text",
            "description": "Translate English text to French language.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            "handler": _echo_handler,
        }
    )
    gate = NCMGate(registry, event_bus=bus, telemetry=publisher)
    llm = ScriptedLLMClient(
        [
            {
                "content": "Need translation first.",
                "tool_calls": [{"id": "c1", "name": META_TOOL_NAME, "arguments": {"intent_query": "translate english text to french"}}],
            },
            {"content": "Done.", "tool_calls": []},
        ]
    )
    agent = SandboxAgent(registry=registry, gate=gate, llm=llm)  # Telemetrie via Gate-Fallback
    assert agent.telemetry is publisher
    result = asyncio.run(agent.run("Summarize the quarterly financial report for management"))
    assert result.path == "system2_jit"

    synth = MacroSkillSynthesizer(registry, event_bus=bus, telemetry=publisher)
    asyncio.run(synth.log_execution(["summarize_report_0", "translate_text"], success=True))
    asyncio.run(synth.log_execution(["summarize_report_0", "translate_text"], success=True))
    third = asyncio.run(synth.log_execution(["summarize_report_0", "translate_text"], success=True))
    assert third is not None and third.created
    asyncio.run(publisher.drain())
    asyncio.run(publisher.close())

    grouped = _graph_payloads(sink)

    # CIEL_JIT_RELOAD: Nachlade-Kante mit Query + Score.
    reload = grouped[CielGraphEventType.JIT_RELOAD.value][0]
    assert reload["active_nodes"][0]["tool"] == "translate_text"
    assert reload["active_nodes"][0]["status"] == "WARM"
    assert reload["detail"]["query"] == "translate english text to french"

    # CIEL_MACRO_EVOLUTION: neuer Super-Node (HOT) + verschmolzene Parents (WARM).
    evolution = grouped[CielGraphEventType.MACRO_EVOLUTION.value][0]
    assert evolution["active_nodes"][0]["tool"] == third.macro_name
    assert evolution["active_nodes"][0]["status"] == "HOT"
    assert [n["tool"] for n in evolution["active_nodes"][1:]] == ["summarize_report_0", "translate_text"]
    assert {n["status"] for n in evolution["active_nodes"][1:]} == {"WARM"}
    assert CielGraphEvent.model_validate(evolution).event == CielGraphEventType.MACRO_EVOLUTION.value


def test_telemetry_publish_never_blocks() -> None:
    event = CielGraphEvent(event=CielGraphEventType.NCM_ROUTING.value, mode=RoutingMode.SYSTEM_2_JIT.value)

    # Volle Queue ohne Worker: put_nowait droppt gezaehlt, statt zu warten.
    tight = CielTelemetryPublisher(queue_size=2)
    assert tight.publish(event) is True
    assert tight.publish(event) is True
    assert tight.publish(event) is False  # voll → Drop, kein Hang
    assert tight.dropped == 1 and tight.published == 2

    # Lifecycle mit Sync- + Async-Subscriber: drain/close liefern deterministisch.
    async def main() -> tuple[list[CielGraphEvent], list[CielGraphEvent], CielTelemetryPublisher]:
        publisher = CielTelemetryPublisher()
        seen_sync: list[CielGraphEvent] = []
        seen_async: list[CielGraphEvent] = []

        async def record_async(evt: CielGraphEvent) -> None:
            seen_async.append(evt)

        publisher.add_sync_subscriber(seen_sync.append)
        publisher.add_async_subscriber(record_async)
        assert publisher.publish(event) is True
        await publisher.drain()
        await asyncio.sleep(0.05)  # create_task-Fanout abwarten
        await publisher.close()
        return seen_sync, seen_async, publisher

    seen_sync, seen_async, publisher = asyncio.run(main())
    assert len(seen_sync) == 1 and seen_sync[0].mode == RoutingMode.SYSTEM_2_JIT.value
    assert len(seen_async) == 1
    assert publisher.dispatched == 1 and publisher.errors == 0
    assert seen_sync[0].ts  # Zeitstempel wurde beim Publish gesetzt
