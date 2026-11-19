"""Tests für die Pre-Execution Policy Engine (NIO Phase 1, Ciel).

Abgedeckt:
* Tier-Regeln (TIER_0 umgeht Sperren, TIER_1 blockiert bei Kill-Switch, Strategie-Status,
  Tagesverlust, Symbol-Halt, Rate-Limit ab max_calls+1).
* Python-Fallback liefert für acht Szenarien die erwarteten Codes; der Lua-Vergleich
  gegen einen echten Redis läuft nur, wenn Redis erreichbar ist (sonst ``skip``).
* TIER_2 im SandboxAgent: kein Lauf ohne Freigabe, genau eine Ausführung nach Resume,
  veränderte Argumente und zweites Resume werden abgelehnt.
* ``on_audit`` für create/approve/reject/consume.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import pytest

from apollo.ciel import (
    AssistantMessage,
    ColdStorageRegistry,
    SandboxAgent,
    ScriptedLLMClient,
    ToolCall,
)
from apollo.ciel.errors import CielError
from apollo.ciel.policy_gate import (
    DAILY_PNL_PREFIX,
    HALT_SYMBOL_PREFIX,
    KILL_SWITCH_KEY,
    M8_STATE_PREFIX,
    RATELIMIT_PREFIX,
    InMemoryPolicyStore,
    PermissionTier,
    PolicyVerdictCode,
    PreExecutionPolicyEngine,
    RedisPolicyStore,
    TicketStatus,
    arguments_sha256,
    redis_asyncio_eval_shim,
)

#: Fester Zeitpunkt (UTC 2027-01-15 08:00:00) für deterministische Tests.
T0_MS = 1_800_000_000_000
DATE = datetime.fromtimestamp(T0_MS / 1000, tz=UTC).strftime("%Y-%m-%d")
SESSION = "s1"
TOOL = "tool_x"


class Uhr:
    """Steuerbare Uhr für die Engine (Millisekunden)."""

    def __init__(self, now: int = T0_MS) -> None:
        self.now = now

    def __call__(self) -> int:
        return self.now


def _engine(store: Any, *, clock: Uhr | None = None, **kwargs: Any) -> PreExecutionPolicyEngine:
    tiers = {
        TOOL: PermissionTier.TIER_1_GUARD,
        "risky": PermissionTier.TIER_2_APPROVAL,
        "reader": PermissionTier.TIER_0_AUTO,
    }
    return PreExecutionPolicyEngine(store, tool_tiers=tiers, clock=clock or Uhr(), **kwargs)


# ---------------------------------------------------------------------------
# Acht Szenarien für den Gate-Vergleich
# ---------------------------------------------------------------------------

#: (id, Operationen, Symbol, erwarteter Code).
#: Operation: ("set", key, wert, expire_at_ms|None) oder ("hset", key, mapping).
SCENARIOS: list[tuple[str, list[tuple[Any, ...]], str | None, PolicyVerdictCode]] = [
    ("ok", [], None, PolicyVerdictCode.OK),
    ("kill_switch", [("set", KILL_SWITCH_KEY, "1", None)], None, PolicyVerdictCode.KILL_SWITCH_ACTIVE),
    (
        "quarantined",
        [("hset", M8_STATE_PREFIX + "default", {"status": "QUARANTINED"})],
        None,
        PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER,
    ),
    (
        "retired",
        [("hset", M8_STATE_PREFIX + "default", {"status": "RETIRED"})],
        None,
        PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER,
    ),
    (
        "budget_multiplier_null",
        [("hset", M8_STATE_PREFIX + "default", {"status": "ACTIVE", "budget_multiplier": "0"})],
        None,
        PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER,
    ),
    ("tagesverlust", [("set", DAILY_PNL_PREFIX + DATE, "-300", None)], None, PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER),
    (
        "symbol_halt",
        [("set", HALT_SYMBOL_PREFIX + "BTC", "1", T0_MS + 300_000)],
        "BTC",
        PolicyVerdictCode.SYMBOL_HALTED,
    ),
    (
        "rate_limit",
        [("set", f"{RATELIMIT_PREFIX}{SESSION}:{TOOL}", "30", None)],
        None,
        PolicyVerdictCode.RATE_LIMIT_EXCEEDED,
    ),
]

#: Alle Schlüssel, die die Szenarien berühren (für das Aufräumen in Redis).
_SCENARIO_KEYS: list[str] = [
    KILL_SWITCH_KEY,
    M8_STATE_PREFIX + "default",
    HALT_SYMBOL_PREFIX + "BTC",
    f"{RATELIMIT_PREFIX}{SESSION}:{TOOL}",
    DAILY_PNL_PREFIX + DATE,
]


def _apply_in_memory(store: InMemoryPolicyStore, ops: list[tuple[Any, ...]]) -> None:
    for op in ops:
        if op[0] == "set":
            _, key, value, expires = op
            store.set_value(key, value, expires_at_ms=expires)
        elif op[0] == "hset":
            _, key, mapping = op
            store.set_hash(key, mapping)


# ---------------------------------------------------------------------------
# Tier-Regeln
# ---------------------------------------------------------------------------


def test_tier0_laeuft_durch_auch_mit_kill_switch() -> None:
    store = InMemoryPolicyStore()
    store.set_value(KILL_SWITCH_KEY, "1")
    decision = asyncio.run(_engine(store).evaluate(SESSION, "reader", {}))
    assert decision.allowed is True
    assert decision.code == PolicyVerdictCode.OK


def test_tier1_blockiert_bei_kill_switch() -> None:
    store = InMemoryPolicyStore()
    store.set_value(KILL_SWITCH_KEY, "1")
    decision = asyncio.run(_engine(store).evaluate(SESSION, TOOL, {}))
    assert decision.allowed is False
    assert decision.code == PolicyVerdictCode.KILL_SWITCH_ACTIVE


def test_tier1_blockiert_bei_quarantined_strategie() -> None:
    store = InMemoryPolicyStore()
    store.set_hash(M8_STATE_PREFIX + "default", {"status": "QUARANTINED"})
    decision = asyncio.run(_engine(store).evaluate(SESSION, TOOL, {}))
    assert decision.code == PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER


def test_tier1_blockiert_bei_tagesverlust_ueber_limit() -> None:
    store = InMemoryPolicyStore()
    store.set_value(DAILY_PNL_PREFIX + DATE, "-251.00")
    decision = asyncio.run(_engine(store, max_daily_loss_usd=250.0).evaluate(SESSION, TOOL, {}))
    assert decision.code == PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER


def test_tier1_erlaubt_tagesverlust_knapp_unter_limit() -> None:
    store = InMemoryPolicyStore()
    store.set_value(DAILY_PNL_PREFIX + DATE, "-249.99")
    decision = asyncio.run(_engine(store, max_daily_loss_usd=250.0).evaluate(SESSION, TOOL, {}))
    assert decision.code == PolicyVerdictCode.OK


def test_tier1_blockiert_bei_symbol_halt_und_gibt_nach_ttl_frei() -> None:
    store = InMemoryPolicyStore()
    store.set_value(HALT_SYMBOL_PREFIX + "BTC", "1", expires_at_ms=T0_MS + 300_000)
    decision = asyncio.run(_engine(store).evaluate(SESSION, TOOL, {}, symbol="BTC"))
    assert decision.code == PolicyVerdictCode.SYMBOL_HALTED
    later = _engine(store, clock=Uhr(T0_MS + 300_000))
    assert asyncio.run(later.evaluate(SESSION, TOOL, {}, symbol="BTC")).code == PolicyVerdictCode.OK


def test_tier1_rate_limit_blockiert_ab_max_calls_plus_eins() -> None:
    engine = _engine(InMemoryPolicyStore(), default_rate_limit=2, window_ms=60_000)
    codes = [asyncio.run(engine.evaluate(SESSION, TOOL, {})).code for _ in range(3)]
    assert codes == [PolicyVerdictCode.OK, PolicyVerdictCode.OK, PolicyVerdictCode.RATE_LIMIT_EXCEEDED]


def test_rate_limit_fenster_setzt_zaehler_nach_ablauf_zurueck() -> None:
    clock = Uhr()
    engine = _engine(InMemoryPolicyStore(), clock=clock, default_rate_limit=1, window_ms=1_000)
    assert asyncio.run(engine.evaluate(SESSION, TOOL, {})).code == PolicyVerdictCode.OK
    assert asyncio.run(engine.evaluate(SESSION, TOOL, {})).code == PolicyVerdictCode.RATE_LIMIT_EXCEEDED
    clock.now += 1_000
    assert asyncio.run(engine.evaluate(SESSION, TOOL, {})).code == PolicyVerdictCode.OK


def test_unbekanntes_tool_ist_tier1_nicht_tier0() -> None:
    store = InMemoryPolicyStore()
    engine = _engine(store)
    assert engine.tier_for("gibt_es_nicht") == PermissionTier.TIER_1_GUARD
    store.set_value(KILL_SWITCH_KEY, "1")
    decision = asyncio.run(engine.evaluate(SESSION, "gibt_es_nicht", {}))
    assert decision.code == PolicyVerdictCode.KILL_SWITCH_ACTIVE


def test_bounds_verletzung_wird_abgelehnt() -> None:
    engine = _engine(InMemoryPolicyStore())

    def _max_qty(arguments: Any) -> str | None:
        return "qty über 10" if int(arguments.get("qty", 0)) > 10 else None

    engine.register_tool_tier(TOOL, PermissionTier.TIER_1_GUARD, _max_qty)
    assert asyncio.run(engine.evaluate(SESSION, TOOL, {"qty": 5})).allowed is True
    decision = asyncio.run(engine.evaluate(SESSION, TOOL, {"qty": 50}))
    assert decision.code == PolicyVerdictCode.BOUNDS_VIOLATION
    assert decision.reason == "qty über 10"


# ---------------------------------------------------------------------------
# Gate-Parität: Python-Fallback (immer) und Lua gegen echten Redis (nur wenn erreichbar)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("scenario_id", "ops", "symbol", "expected"), SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_python_fallback_liefert_erwarteten_code(
    scenario_id: str,
    ops: list[tuple[Any, ...]],
    symbol: str | None,
    expected: PolicyVerdictCode,
) -> None:
    store = InMemoryPolicyStore()
    _apply_in_memory(store, ops)
    decision = asyncio.run(_engine(store).evaluate(SESSION, TOOL, {}, symbol=symbol))
    assert decision.code == expected, scenario_id
    assert decision.allowed is (expected == PolicyVerdictCode.OK)


def test_lua_gate_und_fallback_liefern_identische_ergebnisse() -> None:
    """Lua gegen echten Redis (``NIO_TEST_REDIS_URL``, Standard db 15). Ohne erreichbares Redis: skip."""
    try:
        import redis.asyncio as redis_asyncio  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("redis-Paket nicht installiert: Lua-Vergleich übersprungen")
    url = os.environ.get("NIO_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")

    async def _vergleich() -> int:
        client = redis_asyncio.from_url(url, socket_connect_timeout=0.5)
        try:
            await client.ping()
        except Exception:
            await client.aclose()
            pytest.skip(f"kein Redis unter {url}: Lua-Vergleich übersprungen")
        # Schutz vor Fremddaten: der Test löscht Schlüssel, daher nur in einer leeren Test-DB.
        if await client.dbsize() != 0:
            await client.aclose()
            pytest.skip(f"Test-DB unter {url} ist nicht leer: Lua-Vergleich übersprungen (eigene DB via NIO_TEST_REDIS_URL)")
        try:
            for scenario_id, ops, symbol, expected in SCENARIOS:
                # Nur die Schlüssel der Szenarien werden gelöscht, keine ganze DB.
                await client.delete(*_SCENARIO_KEYS)
                for op in ops:
                    if op[0] == "set":
                        _, key, value, expires = op
                        await client.set(key, value)
                        if expires is not None:
                            await client.pexpireat(key, expires)
                    elif op[0] == "hset":
                        _, key, mapping = op
                        await client.hset(key, mapping=mapping)
                redis_engine = _engine(RedisPolicyStore(redis_asyncio_eval_shim(client)))
                redis_code = (await redis_engine.evaluate(SESSION, TOOL, {}, symbol=symbol)).code

                fallback_store = InMemoryPolicyStore()
                _apply_in_memory(fallback_store, ops)
                fallback_code = (await _engine(fallback_store).evaluate(SESSION, TOOL, {}, symbol=symbol)).code

                assert redis_code == fallback_code == expected, scenario_id
            return len(SCENARIOS)
        finally:
            await client.delete(*_SCENARIO_KEYS)
            await client.aclose()

    assert asyncio.run(_vergleich()) == len(SCENARIOS)


# ---------------------------------------------------------------------------
# TIER_2 im SandboxAgent
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


def _risky_agent(
    calls: list[dict[str, Any]],
    engine: PreExecutionPolicyEngine,
) -> SandboxAgent:
    llm = ScriptedLLMClient(
        [
            AssistantMessage(content="", tool_calls=[ToolCall(id="c1", name="risky", arguments={"qty": 1})]),
            AssistantMessage(content="fertig"),
        ]
    )
    return SandboxAgent(registry=_risky_registry(calls), llm=llm, policy_engine=engine)


def test_tier2_fuehrt_nicht_aus_und_erzeugt_pending_ticket() -> None:
    calls: list[dict[str, Any]] = []
    engine = _engine(InMemoryPolicyStore())
    agent = _risky_agent(calls, engine)
    result = asyncio.run(agent.run("riskante Order platzieren", session_id=SESSION))
    assert calls == []
    pending = asyncio.run(engine.pending_tickets(SESSION))
    assert len(pending) == 1
    assert pending[0].status == TicketStatus.PENDING
    assert result.final_answer == f"WAITING_APPROVAL:{pending[0].id}"


def test_tier2_resume_fuehrt_genau_einmal_aus_und_setzt_fort() -> None:
    calls: list[dict[str, Any]] = []
    engine = _engine(InMemoryPolicyStore())
    agent = _risky_agent(calls, engine)
    waiting = asyncio.run(agent.run("riskante Order platzieren", session_id=SESSION))
    ticket_id = waiting.final_answer.split(":", 1)[1]
    asyncio.run(engine.resolve_ticket(ticket_id, approved=True, operator_id="finn"))
    resumed = asyncio.run(agent.resume_after_approval(SESSION, ticket_id))
    assert calls == [{"qty": 1}]
    assert resumed.final_answer == "fertig"
    assert resumed.errors == []
    assert resumed.tool_calls == ["risky"]


def test_tier2_resume_mit_veraenderten_argumenten_ist_ungueltig() -> None:
    calls: list[dict[str, Any]] = []
    store = InMemoryPolicyStore()
    engine = _engine(store)
    agent = _risky_agent(calls, engine)
    waiting = asyncio.run(agent.run("riskante Order platzieren", session_id=SESSION))
    ticket_id = waiting.final_answer.split(":", 1)[1]
    asyncio.run(engine.resolve_ticket(ticket_id, approved=True, operator_id="finn"))

    tampered = asyncio.run(
        agent.execute_tool(
            ToolCall(id="x", name="risky", arguments={"qty": 999}),
            session_id=SESSION,
            approval_ticket_id=ticket_id,
        )
    )
    assert tampered.ok is False
    assert tampered.error.startswith("POLICY:APPROVAL_INVALID")
    assert calls == []
    # Der Fehlversuch verbraucht das Ticket nicht.
    stored = asyncio.run(store.get_ticket(ticket_id))
    assert stored is not None and stored.status == TicketStatus.APPROVED

    asyncio.run(agent.resume_after_approval(SESSION, ticket_id))
    assert calls == [{"qty": 1}]


def test_tier2_zweites_resume_wird_abgelehnt() -> None:
    calls: list[dict[str, Any]] = []
    engine = _engine(InMemoryPolicyStore())
    agent = _risky_agent(calls, engine)
    waiting = asyncio.run(agent.run("riskante Order platzieren", session_id=SESSION))
    ticket_id = waiting.final_answer.split(":", 1)[1]
    asyncio.run(engine.resolve_ticket(ticket_id, approved=True, operator_id="finn"))
    asyncio.run(agent.resume_after_approval(SESSION, ticket_id))
    second = asyncio.run(agent.resume_after_approval(SESSION, ticket_id))
    assert second.errors and second.errors[0].startswith("APPROVAL_INVALID")
    assert calls == [{"qty": 1}]


def test_tier2_abgelehnt_durch_operator_fuehrt_nicht_aus() -> None:
    calls: list[dict[str, Any]] = []
    engine = _engine(InMemoryPolicyStore())
    agent = _risky_agent(calls, engine)
    waiting = asyncio.run(agent.run("riskante Order platzieren", session_id=SESSION))
    ticket_id = waiting.final_answer.split(":", 1)[1]
    asyncio.run(engine.resolve_ticket(ticket_id, approved=False, operator_id="finn", reason="zu groß"))
    resumed = asyncio.run(agent.resume_after_approval(SESSION, ticket_id))
    assert calls == []
    assert any(e.startswith("POLICY:APPROVAL_REJECTED") for e in resumed.errors)


def test_tier2_abgelaufenes_ticket_ist_ungueltig() -> None:
    calls: list[dict[str, Any]] = []
    clock = Uhr()
    engine = _engine(InMemoryPolicyStore(), clock=clock, approval_ttl_ms=1_000)
    agent = _risky_agent(calls, engine)
    waiting = asyncio.run(agent.run("riskante Order platzieren", session_id=SESSION))
    ticket_id = waiting.final_answer.split(":", 1)[1]
    clock.now += 2_000
    resumed = asyncio.run(agent.resume_after_approval(SESSION, ticket_id))
    assert calls == []
    assert any("abgelaufen" in e for e in resumed.errors)


def test_resume_mit_unbekanntem_ticket_liefert_fehler() -> None:
    agent = _risky_agent([], _engine(InMemoryPolicyStore()))
    result = asyncio.run(agent.resume_after_approval(SESSION, "gibt-es-nicht"))
    assert result.errors and result.errors[0].startswith("APPROVAL_INVALID")


def test_ohne_policy_engine_laeuft_tool_direkt() -> None:
    calls: list[dict[str, Any]] = []
    llm = ScriptedLLMClient(
        [
            AssistantMessage(content="", tool_calls=[ToolCall(id="c1", name="risky", arguments={"qty": 2})]),
            AssistantMessage(content="fertig"),
        ]
    )
    agent = SandboxAgent(registry=_risky_registry(calls), llm=llm)
    result = asyncio.run(agent.run("riskante Order platzieren"))
    assert calls == [{"qty": 2}]
    assert result.final_answer == "fertig"


def test_mit_policy_engine_kein_system1_bypass() -> None:
    """Der Gate-Bypass würde Tools ohne Prüfung ausführen; mit Policy-Engine entscheidet das LLM."""
    calls_ohne: list[dict[str, Any]] = []
    ohne_policy = SandboxAgent(registry=_risky_registry(calls_ohne), llm=ScriptedLLMClient([]))
    intent = ohne_policy.registry.anchor_text("risky")
    assert asyncio.run(ohne_policy.run(intent, {"qty": 3})).path == "system1_bypass"
    assert calls_ohne == [{"qty": 3}]

    calls_mit: list[dict[str, Any]] = []
    llm = ScriptedLLMClient([AssistantMessage(content="kein Tool nötig")])
    mit_policy = SandboxAgent(registry=_risky_registry(calls_mit), llm=llm, policy_engine=_engine(InMemoryPolicyStore()))
    result = asyncio.run(mit_policy.run(intent, {"qty": 3}, session_id=SESSION))
    assert result.path == "system2_jit"
    assert llm.calls == 1
    assert calls_mit == []


# ---------------------------------------------------------------------------
# Audit und Ticket-Verwaltung
# ---------------------------------------------------------------------------


def test_on_audit_wird_fuer_create_approve_consume_aufgerufen() -> None:
    audit: list[tuple[str, dict[str, Any]]] = []
    calls: list[dict[str, Any]] = []

    async def _on_audit(action: str, payload: dict[str, Any]) -> None:
        audit.append((action, payload))

    engine = _engine(InMemoryPolicyStore(), on_audit=_on_audit)
    agent = _risky_agent(calls, engine)
    waiting = asyncio.run(agent.run("riskante Order platzieren", session_id=SESSION))
    ticket_id = waiting.final_answer.split(":", 1)[1]
    asyncio.run(engine.resolve_ticket(ticket_id, approved=True, operator_id="finn", reason="ok"))
    asyncio.run(agent.resume_after_approval(SESSION, ticket_id))

    assert [action for action, _ in audit] == ["create", "approve", "consume"]
    for _action, payload in audit:
        assert payload["ticket_id"] == ticket_id
        assert payload["arguments_sha256"] == arguments_sha256({"qty": 1})
        assert "qty" not in payload  # keine Roh-Argumente im Audit
    assert audit[1][1]["operator_id"] == "finn"


def test_on_audit_wird_fuer_reject_aufgerufen() -> None:
    audit: list[str] = []

    async def _on_audit(action: str, payload: dict[str, Any]) -> None:
        audit.append(action)

    engine = _engine(InMemoryPolicyStore(), on_audit=_on_audit)
    decision = asyncio.run(engine.evaluate(SESSION, "risky", {"qty": 1}))
    assert decision.ticket is not None
    asyncio.run(engine.resolve_ticket(decision.ticket.id, approved=False, operator_id="finn"))
    assert audit == ["create", "reject"]


def test_ticket_gilt_nur_fuer_eine_session() -> None:
    engine = _engine(InMemoryPolicyStore())
    waiting = asyncio.run(engine.evaluate(SESSION, "risky", {"qty": 1}))
    assert waiting.ticket is not None
    asyncio.run(engine.resolve_ticket(waiting.ticket.id, approved=True, operator_id="finn"))
    fremd = asyncio.run(engine.evaluate("andere-session", "risky", {"qty": 1}, approval_ticket_id=waiting.ticket.id))
    assert fremd.code == PolicyVerdictCode.APPROVAL_INVALID


def test_resolve_ist_nur_einmal_moeglich() -> None:
    engine = _engine(InMemoryPolicyStore())
    waiting = asyncio.run(engine.evaluate(SESSION, "risky", {"qty": 1}))
    assert waiting.ticket is not None
    asyncio.run(engine.resolve_ticket(waiting.ticket.id, approved=True, operator_id="finn"))
    with pytest.raises(CielError, match="nicht PENDING"):
        asyncio.run(engine.resolve_ticket(waiting.ticket.id, approved=False, operator_id="finn"))


def test_pending_tickets_filtert_nach_session() -> None:
    engine = _engine(InMemoryPolicyStore())
    asyncio.run(engine.evaluate("a", "risky", {"qty": 1}))
    asyncio.run(engine.evaluate("b", "risky", {"qty": 2}))
    assert len(asyncio.run(engine.pending_tickets())) == 2
    assert len(asyncio.run(engine.pending_tickets("a"))) == 1


def test_on_ticket_wird_beim_anlegen_aufgerufen_und_fehler_blockieren_nicht() -> None:
    gemeldet: list[str] = []

    def _on_ticket(ticket: Any) -> None:
        gemeldet.append(ticket.id)
        raise RuntimeError("Telegram nicht erreichbar")

    engine = _engine(InMemoryPolicyStore(), on_ticket=_on_ticket)
    decision = asyncio.run(engine.evaluate(SESSION, "risky", {"qty": 1}))
    assert decision.code == PolicyVerdictCode.WAITING_APPROVAL
    assert decision.ticket is not None
    assert gemeldet == [decision.ticket.id]
