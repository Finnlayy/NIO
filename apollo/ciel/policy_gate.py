"""Pre-Execution Policy Engine für Apollo Ciel (NIO Phase 1).

Vor JEDEM Tool-Call entscheidet diese Schicht deterministisch:

* ``ausführen`` (``OK``),
* ``ablehnen`` (Kill-Switch, Strategie-Status, Tagesverlust, Symbol-Halt,
  Rate-Limit, Bounds-Verletzung) oder
* ``warten`` (TIER_2: Operator-Freigabe über ein Ticket).

Die Sperrprüfungen laufen für TIER_1 und TIER_2 in genau einem Roundtrip:
Redis (Lua, :data:`LUA_PRE_EXECUTION_GATE`) oder der Python-Fallback
:func:`_eval_fallback` mit identischer Semantik (In-Memory, Tests ohne Redis).

Kopplung: keine Imports aus ``orchestrator``/``core``/``workspace``. Der Redis-
Zugriff läuft über einen injizierten ``eval``-Shim (siehe
:func:`redis_asyncio_eval_shim` und :func:`resp_eval_shim`), Audit und
Benachrichtigung über injizierte Callables.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final, Protocol

from .errors import CielError
from .models import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Konstanten und Schlüssel
# ---------------------------------------------------------------------------

#: Globaler Not-Aus (existiert und ist nicht ``"0"``/leer → aktiv).
KILL_SWITCH_KEY: Final[str] = "nio:policy:kill_switch"
#: Präfix für den Strategie-Zustand (Hash, Felder siehe :func:`_eval_fallback`).
M8_STATE_PREFIX: Final[str] = "m8:state:"
#: Präfix für Symbol-Halts (String mit TTL, existiert → gesperrt).
HALT_SYMBOL_PREFIX: Final[str] = "halt:symbol:"
#: Präfix für Rate-Limit-Zähler je Session und Tool.
RATELIMIT_PREFIX: Final[str] = "nio:ratelimit:"
#: Präfix für den Tagesverlust (USD, je UTC-Datum).
DAILY_PNL_PREFIX: Final[str] = "sigma:daily_pnl_usd:"
#: Präfix für Freigabe-Tickets (JSON-String je Ticket).
TICKET_PREFIX: Final[str] = "nio:policy:ticket:"
#: Menge aller Ticket-Schlüssel (für ``list_tickets``).
TICKET_INDEX_KEY: Final[str] = "nio:policy:tickets"


class PermissionTier(StrEnum):
    """Berechtigungsstufe eines Tools."""

    TIER_0_AUTO = "TIER_0_AUTO"
    TIER_1_GUARD = "TIER_1_GUARD"
    TIER_2_APPROVAL = "TIER_2_APPROVAL"


class PolicyVerdictCode(StrEnum):
    """Ergebnis einer Policy-Prüfung."""

    OK = "OK"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    DRAWDOWN_CIRCUIT_BREAKER = "DRAWDOWN_CIRCUIT_BREAKER"
    SYMBOL_HALTED = "SYMBOL_HALTED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BOUNDS_VIOLATION = "BOUNDS_VIOLATION"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_INVALID = "APPROVAL_INVALID"


class TicketStatus(StrEnum):
    """Lebenszyklus eines Freigabe-Tickets: PENDING → APPROVED/REJECTED → CONSUMED."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


# ---------------------------------------------------------------------------
# Modelle
# ---------------------------------------------------------------------------


class ApprovalTicket(BaseModel):
    """Operator-Freigabe für genau einen Tool-Call mit exakt diesen Argumenten."""

    model_config = ConfigDict(extra="ignore")

    id: str
    session_id: str
    tool: str
    arguments_sha256: str
    status: TicketStatus = TicketStatus.PENDING
    created_ms: int = 0
    expires_ms: int = 0
    operator_id: str = ""
    reason: str = ""


class PolicyDecision(BaseModel):
    """Entscheidung der Policy-Engine für einen Tool-Call."""

    model_config = ConfigDict(extra="ignore")

    allowed: bool
    code: PolicyVerdictCode
    reason: str = ""
    tier: PermissionTier = PermissionTier.TIER_1_GUARD
    ticket: ApprovalTicket | None = None


# ---------------------------------------------------------------------------
# Lua-Gate (ein Roundtrip) und Ticket-Skripte
# ---------------------------------------------------------------------------

#: Lua-Skript der Sperrprüfung. KEYS: 1 Kill-Switch, 2 m8-Zustand, 3 Symbol-Halt,
#: 4 Rate-Limit, 5 Tagesverlust. ARGV: 1 now_ms, 2 window_ms, 3 max_calls,
#: 4 max_daily_loss_usd, 5 Tier. Rückgabe: JSON ``{"code": ..., "reason": ...}``.
LUA_PRE_EXECUTION_GATE: Final[str] = """
local function out(code, reason)
  return cjson.encode({code = code, reason = reason})
end
if ARGV[5] == 'TIER_0_AUTO' then
  return out('OK', '')
end
local kill = redis.call('GET', KEYS[1])
if kill and kill ~= '' and kill ~= '0' then
  return out('KILL_SWITCH_ACTIVE', 'Kill-Switch aktiv')
end
local status = redis.call('HGET', KEYS[2], 'status')
local mult = redis.call('HGET', KEYS[2], 'budget_multiplier')
if status == 'QUARANTINED' or status == 'RETIRED' then
  return out('DRAWDOWN_CIRCUIT_BREAKER', 'Strategie-Status ' .. status)
end
if mult and tonumber(mult) == 0 then
  return out('DRAWDOWN_CIRCUIT_BREAKER', 'Strategie-Budget-Multiplikator ist 0')
end
local pnl = tonumber(redis.call('GET', KEYS[5]) or '')
if pnl and pnl <= -tonumber(ARGV[4]) then
  return out('DRAWDOWN_CIRCUIT_BREAKER', string.format('Tagesverlust %.2f USD', pnl))
end
if redis.call('EXISTS', KEYS[3]) == 1 then
  return out('SYMBOL_HALTED', 'Symbol ist gehalten')
end
local n = redis.call('INCR', KEYS[4])
if n == 1 then
  redis.call('PEXPIRE', KEYS[4], ARGV[2])
end
if n > tonumber(ARGV[3]) then
  return out('RATE_LIMIT_EXCEEDED', 'Rate-Limit ueberschritten')
end
return out('OK', '')
"""

#: KEYS[1] Ticket-Schlüssel, ARGV[1] Ticket-JSON, KEYS[2] Index-Menge.
_LUA_TICKET_PUT: Final[str] = """
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SADD', KEYS[2], KEYS[1])
return 1
"""

#: KEYS[1] Ticket-Schlüssel, ARGV[1] erwarteter Status, ARGV[2] neues Ticket-JSON.
_LUA_TICKET_CAS: Final[str] = """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
local cur = cjson.decode(raw)
if cur['status'] ~= ARGV[1] then
  return 0
end
redis.call('SET', KEYS[1], ARGV[2])
return 1
"""

#: KEYS[1] Ticket-Schlüssel → JSON oder leerer String.
_LUA_TICKET_GET: Final[str] = "return redis.call('GET', KEYS[1]) or ''"

#: KEYS[1] Index-Menge → Liste der Ticket-Schlüssel.
_LUA_TICKET_INDEX: Final[str] = "return redis.call('SMEMBERS', KEYS[1])"

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

BoundsValidator = Callable[[Mapping[str, Any]], str | None]
EvalShim = Callable[[str, list[str], list[str]], Awaitable[Any]]
AuditCallback = Callable[[str, dict[str, Any]], Any]
TicketCallback = Callable[[ApprovalTicket], Any]


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _utc_date(now_ms: int) -> str:
    return datetime.fromtimestamp(now_ms / 1000, tz=UTC).strftime("%Y-%m-%d")


def arguments_sha256(arguments: Mapping[str, Any]) -> str:
    """Kanonischer Hash der Tool-Argumente (Ticket-Bindung)."""
    canonical = json.dumps(dict(arguments), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _decode(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return str(raw)


def _verdict(code: PolicyVerdictCode, reason: str = "") -> str:
    return json.dumps({"code": code.value, "reason": reason}, ensure_ascii=False)


def _as_number(raw: Any) -> float | None:
    """Wandelt einen Store-Wert in eine Zahl; nicht numerisch → ``None`` (wie Lua ``tonumber``)."""
    if raw is None or isinstance(raw, dict):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _ticket_json(ticket: ApprovalTicket) -> str:
    return json.dumps(ticket.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# Python-Fallback (identische Semantik zu LUA_PRE_EXECUTION_GATE)
# ---------------------------------------------------------------------------


def _eval_fallback(keys: Sequence[str], args: Sequence[str], store: InMemoryPolicyStore) -> str:
    """Python-Äquivalent zu :data:`LUA_PRE_EXECUTION_GATE`.

    Gleiche Reihenfolge, gleiche Bedingungen, gleiche JSON-Rückgabe. ``store``
    liefert die Werte mit TTL-Auswertung zum Zeitpunkt ``now_ms``.
    """
    now_ms = int(args[0])
    window_ms = int(args[1])
    max_calls = int(args[2])
    max_daily_loss = float(args[3])
    tier = args[4]
    if tier == PermissionTier.TIER_0_AUTO.value:
        return _verdict(PolicyVerdictCode.OK)

    kill = store._live(keys[0], now_ms)
    if kill is not None and kill not in ("", "0"):
        return _verdict(PolicyVerdictCode.KILL_SWITCH_ACTIVE, "Kill-Switch aktiv")

    strategy = store._live(keys[1], now_ms)
    fields: dict[str, str] = strategy if isinstance(strategy, dict) else {}
    status = fields.get("status")
    mult = fields.get("budget_multiplier")
    if status in ("QUARANTINED", "RETIRED"):
        return _verdict(PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER, f"Strategie-Status {status}")
    if mult is not None and _as_number(mult) == 0:
        return _verdict(PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER, "Strategie-Budget-Multiplikator ist 0")

    pnl = _as_number(store._live(keys[4], now_ms))
    if pnl is not None and pnl <= -max_daily_loss:
        return _verdict(PolicyVerdictCode.DRAWDOWN_CIRCUIT_BREAKER, f"Tagesverlust {pnl:.2f} USD")

    if store._live(keys[2], now_ms) is not None:
        return _verdict(PolicyVerdictCode.SYMBOL_HALTED, "Symbol ist gehalten")

    count = store._incr(keys[3], now_ms)
    if count == 1:
        store._pexpire(keys[3], window_ms, now_ms)
    if count > max_calls:
        return _verdict(PolicyVerdictCode.RATE_LIMIT_EXCEEDED, "Rate-Limit ueberschritten")
    return _verdict(PolicyVerdictCode.OK)


# ---------------------------------------------------------------------------
# Store-Protokoll und Adapter
# ---------------------------------------------------------------------------


class PolicyStore(Protocol):
    """Speicher der Policy-Engine: Sperr-Gate plus Ticket-Persistenz."""

    async def gate(self, keys: list[str], args: list[str]) -> str: ...

    async def put_ticket(self, ticket: ApprovalTicket) -> None: ...

    async def get_ticket(self, ticket_id: str) -> ApprovalTicket | None: ...

    async def compare_and_set_ticket(self, ticket_id: str, expected: TicketStatus, updated: ApprovalTicket) -> bool: ...

    async def list_tickets(self) -> list[ApprovalTicket]: ...


class InMemoryPolicyStore:
    """In-Memory-Store mit TTL-Auswertung; Referenz für Tests ohne Redis."""

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}
        self._expires: dict[str, int] = {}
        self._tickets: dict[str, ApprovalTicket] = {}

    # -- Setup-Helfer (Tests, Betriebsdaten-Stub) -----------------------------

    def set_value(self, key: str, value: str, *, expires_at_ms: int | None = None) -> None:
        """Setzt einen String-Schlüssel, optional mit absoluter Ablaufzeit in ms."""
        self._values[key] = str(value)
        if expires_at_ms is None:
            self._expires.pop(key, None)
        else:
            self._expires[key] = expires_at_ms

    def set_hash(self, key: str, mapping: Mapping[str, Any]) -> None:
        """Setzt einen Hash-Schlüssel (z. B. ``m8:state:{id}``)."""
        self._values[key] = {str(k): str(v) for k, v in mapping.items()}
        self._expires.pop(key, None)

    # -- Primitive für _eval_fallback -----------------------------------------

    def _live(self, key: str, now_ms: int) -> Any | None:
        expires = self._expires.get(key)
        if expires is not None and now_ms >= expires:
            self._values.pop(key, None)
            self._expires.pop(key, None)
            return None
        return self._values.get(key)

    def _incr(self, key: str, now_ms: int) -> int:
        current = self._live(key, now_ms)
        count = int(current or 0) + 1
        self._values[key] = str(count)
        return count

    def _pexpire(self, key: str, ttl_ms: int, now_ms: int) -> None:
        self._expires[key] = now_ms + ttl_ms

    # -- PolicyStore ----------------------------------------------------------

    async def gate(self, keys: list[str], args: list[str]) -> str:
        return _eval_fallback(keys, args, self)

    async def put_ticket(self, ticket: ApprovalTicket) -> None:
        self._tickets[ticket.id] = ticket

    async def get_ticket(self, ticket_id: str) -> ApprovalTicket | None:
        return self._tickets.get(ticket_id)

    async def compare_and_set_ticket(self, ticket_id: str, expected: TicketStatus, updated: ApprovalTicket) -> bool:
        current = self._tickets.get(ticket_id)
        if current is None or current.status != expected:
            return False
        self._tickets[ticket_id] = updated
        return True

    async def list_tickets(self) -> list[ApprovalTicket]:
        return list(self._tickets.values())


class RedisPolicyStore:
    """Redis-Store über einen ``eval(script, keys, args)``-Shim.

    Der Shim kapselt den Client (``redis.asyncio`` oder ``RedisClient``); siehe
    :func:`redis_asyncio_eval_shim` und :func:`resp_eval_shim`.
    """

    def __init__(self, eval_shim: EvalShim) -> None:
        self._eval = eval_shim

    async def gate(self, keys: list[str], args: list[str]) -> str:
        return _decode(await self._eval(LUA_PRE_EXECUTION_GATE, keys, args))

    async def put_ticket(self, ticket: ApprovalTicket) -> None:
        await self._eval(_LUA_TICKET_PUT, [TICKET_PREFIX + ticket.id, TICKET_INDEX_KEY], [_ticket_json(ticket)])

    async def get_ticket(self, ticket_id: str) -> ApprovalTicket | None:
        raw = _decode(await self._eval(_LUA_TICKET_GET, [TICKET_PREFIX + ticket_id], []))
        if not raw:
            return None
        return ApprovalTicket.model_validate(json.loads(raw))

    async def compare_and_set_ticket(self, ticket_id: str, expected: TicketStatus, updated: ApprovalTicket) -> bool:
        result = await self._eval(_LUA_TICKET_CAS, [TICKET_PREFIX + ticket_id], [str(expected.value), _ticket_json(updated)])
        return int(result) == 1

    async def list_tickets(self) -> list[ApprovalTicket]:
        members = await self._eval(_LUA_TICKET_INDEX, [TICKET_INDEX_KEY], [])
        tickets: list[ApprovalTicket] = []
        for member in members or []:
            ticket = await self.get_ticket(_decode(member).removeprefix(TICKET_PREFIX))
            if ticket is not None:
                tickets.append(ticket)
        return tickets


def redis_asyncio_eval_shim(client: Any) -> EvalShim:
    """Shim für einen ``redis.asyncio``-kompatiblen Client (``client.eval``)."""

    async def _eval(script: str, keys: list[str], args: list[str]) -> Any:
        return await client.eval(script, len(keys), *keys, *args)

    return _eval


def resp_eval_shim(client: Any) -> EvalShim:
    """Shim für ``orchestrator.kanban.redis_resp.RedisClient`` (``execute``)."""

    async def _eval(script: str, keys: list[str], args: list[str]) -> Any:
        return await client.execute("EVAL", script, len(keys), *keys, *args)

    return _eval


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PreExecutionPolicyEngine:
    """Deterministische Vorab-Prüfung jedes Tool-Calls.

    ``on_audit(action, payload)`` erhält ``create``/``approve``/``reject``/``consume``;
    der Payload enthält nur ``arguments_sha256``, nie die Roh-Argumente.
    Fehler im Audit propagieren (fail-closed). ``on_ticket(ticket)`` wird beim
    Anlegen eines Tickets aufgerufen; Fehler dort blockieren nicht, das Ticket
    bleibt persistiert.

    ``clock`` (optional) liefert die Zeit in ms und ist für Tests gedacht.
    """

    def __init__(
        self,
        store: PolicyStore,
        *,
        tool_tiers: Mapping[str, PermissionTier],
        default_rate_limit: int = 30,
        window_ms: int = 60_000,
        max_daily_loss_usd: float = 250.0,
        approval_ttl_ms: int = 300_000,
        on_audit: AuditCallback | None = None,
        on_ticket: TicketCallback | None = None,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._store = store
        self._tiers: dict[str, PermissionTier] = {str(name): PermissionTier(tier) for name, tier in tool_tiers.items()}
        self._validators: dict[str, BoundsValidator] = {}
        self._default_rate_limit = default_rate_limit
        self._window_ms = window_ms
        self._max_daily_loss = max_daily_loss_usd
        self._approval_ttl_ms = approval_ttl_ms
        self._on_audit = on_audit
        self._on_ticket = on_ticket
        self._clock = clock or _now_ms

    def register_tool_tier(
        self,
        name: str,
        tier: PermissionTier,
        bounds_validator: BoundsValidator | None = None,
    ) -> None:
        """Ordnet einem Tool eine Stufe zu, optional mit Bounds-Prüfung auf den Argumenten."""
        self._tiers[name] = PermissionTier(tier)
        if bounds_validator is not None:
            self._validators[name] = bounds_validator
        else:
            self._validators.pop(name, None)

    def tier_for(self, tool_name: str) -> PermissionTier:
        """Unbekannte Tools sind standardmäßig TIER_1_GUARD (nie TIER_0)."""
        return self._tiers.get(tool_name, PermissionTier.TIER_1_GUARD)

    async def evaluate(
        self,
        session_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
        *,
        strategy_id: str = "default",
        symbol: str | None = None,
        approval_ticket_id: str | None = None,
    ) -> PolicyDecision:
        """Entscheidet über einen Tool-Call: ausführen, ablehnen oder auf Freigabe warten.

        TIER_0 umgeht Kill-Switch und Redis vollständig (nur Bounds-Prüfung).
        """
        tier = self.tier_for(tool_name)
        if tier == PermissionTier.TIER_0_AUTO:
            return self._bounds_decision(tool_name, tier, arguments)

        now = self._clock()
        keys = [
            KILL_SWITCH_KEY,
            M8_STATE_PREFIX + strategy_id,
            HALT_SYMBOL_PREFIX + (symbol or ""),
            f"{RATELIMIT_PREFIX}{session_id}:{tool_name}",
            DAILY_PNL_PREFIX + _utc_date(now),
        ]
        args = [str(now), str(self._window_ms), str(self._default_rate_limit), repr(float(self._max_daily_loss)), tier.value]
        verdict = json.loads(await self._store.gate(keys, args))
        code = PolicyVerdictCode(verdict["code"])
        if code != PolicyVerdictCode.OK:
            return PolicyDecision(allowed=False, code=code, reason=str(verdict.get("reason", "")), tier=tier)

        bounds = self._bounds_decision(tool_name, tier, arguments)
        if not bounds.allowed or tier == PermissionTier.TIER_1_GUARD:
            return bounds
        return await self._evaluate_approval(session_id, tool_name, arguments, approval_ticket_id, now)

    def _bounds_decision(self, tool_name: str, tier: PermissionTier, arguments: Mapping[str, Any]) -> PolicyDecision:
        validator = self._validators.get(tool_name)
        if validator is not None:
            problem = validator(arguments)
            if problem:
                return PolicyDecision(allowed=False, code=PolicyVerdictCode.BOUNDS_VIOLATION, reason=problem, tier=tier)
        return PolicyDecision(allowed=True, code=PolicyVerdictCode.OK, tier=tier)

    async def _evaluate_approval(
        self,
        session_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
        approval_ticket_id: str | None,
        now: int,
    ) -> PolicyDecision:
        """TIER_2: ohne Ticket neues Ticket anlegen; mit Ticket Freigabe prüfen und einmalig verbrauchen."""
        tier = PermissionTier.TIER_2_APPROVAL
        if approval_ticket_id is None:
            new_ticket = ApprovalTicket(
                id=uuid.uuid4().hex,
                session_id=session_id,
                tool=tool_name,
                arguments_sha256=arguments_sha256(arguments),
                status=TicketStatus.PENDING,
                created_ms=now,
                expires_ms=now + self._approval_ttl_ms,
            )
            await self._store.put_ticket(new_ticket)
            await self._audit("create", new_ticket)
            await self._notify(new_ticket)
            return PolicyDecision(
                allowed=False,
                code=PolicyVerdictCode.WAITING_APPROVAL,
                reason=f"Operator-Freigabe nötig (Ticket {new_ticket.id})",
                tier=tier,
                ticket=new_ticket,
            )

        ticket = await self._store.get_ticket(approval_ticket_id)

        def _invalid(reason: str) -> PolicyDecision:
            return PolicyDecision(allowed=False, code=PolicyVerdictCode.APPROVAL_INVALID, reason=reason, tier=tier, ticket=ticket)

        if ticket is None:
            return _invalid("Ticket unbekannt")
        if ticket.tool != tool_name or ticket.session_id != session_id:
            return _invalid("Ticket gehört nicht zu diesem Tool oder dieser Session")
        if ticket.arguments_sha256 != arguments_sha256(arguments):
            return _invalid("Argumente weichen vom Ticket ab")
        if ticket.status == TicketStatus.CONSUMED:
            return _invalid("Ticket ist bereits verbraucht")
        if ticket.status == TicketStatus.REJECTED:
            return PolicyDecision(
                allowed=False, code=PolicyVerdictCode.APPROVAL_REJECTED, reason="Operator hat abgelehnt", tier=tier, ticket=ticket
            )
        if ticket.status == TicketStatus.EXPIRED:
            return _invalid("Ticket ist abgelaufen")
        if now > ticket.expires_ms and ticket.status in (TicketStatus.PENDING, TicketStatus.APPROVED):
            expired = ticket.model_copy(update={"status": TicketStatus.EXPIRED})
            await self._store.compare_and_set_ticket(ticket.id, TicketStatus(ticket.status), expired)
            return _invalid("Ticket ist abgelaufen")
        if ticket.status == TicketStatus.PENDING:
            return PolicyDecision(
                allowed=False,
                code=PolicyVerdictCode.WAITING_APPROVAL,
                reason=f"Operator-Freigabe ausstehend (Ticket {ticket.id})",
                tier=tier,
                ticket=ticket,
            )
        # APPROVED: einmalig verbrauchen (CAS verhindert doppelte Ausführung).
        consumed = ticket.model_copy(update={"status": TicketStatus.CONSUMED})
        if not await self._store.compare_and_set_ticket(ticket.id, TicketStatus.APPROVED, consumed):
            return _invalid("Ticket wurde parallel verbraucht")
        await self._audit("consume", consumed)
        return PolicyDecision(allowed=True, code=PolicyVerdictCode.OK, reason="Freigabe verbraucht", tier=tier, ticket=consumed)

    async def resolve_ticket(self, ticket_id: str, *, approved: bool, operator_id: str, reason: str = "") -> ApprovalTicket:
        """Operator-Entscheidung: PENDING → APPROVED oder REJECTED (nur einmal möglich)."""
        ticket = await self._store.get_ticket(ticket_id)
        if ticket is None:
            raise CielError(f"Unbekanntes Ticket {ticket_id!r}")
        if ticket.status != TicketStatus.PENDING:
            raise CielError(f"Ticket {ticket_id!r} ist nicht PENDING (Status {ticket.status})")
        if self._clock() > ticket.expires_ms:
            expired = ticket.model_copy(update={"status": TicketStatus.EXPIRED})
            await self._store.compare_and_set_ticket(ticket_id, TicketStatus.PENDING, expired)
            raise CielError(f"Ticket {ticket_id!r} ist abgelaufen")
        new_status = TicketStatus.APPROVED if approved else TicketStatus.REJECTED
        updated = ticket.model_copy(update={"status": new_status, "operator_id": operator_id, "reason": reason})
        if not await self._store.compare_and_set_ticket(ticket_id, TicketStatus.PENDING, updated):
            raise CielError(f"Ticket {ticket_id!r} wurde parallel geändert")
        await self._audit("approve" if approved else "reject", updated)
        return updated

    async def pending_tickets(self, session_id: str | None = None) -> list[ApprovalTicket]:
        """Offene, nicht abgelaufene Tickets (optional je Session), nach Anlage sortiert."""
        now = self._clock()
        tickets = await self._store.list_tickets()
        pending = [
            t
            for t in tickets
            if t.status == TicketStatus.PENDING and now <= t.expires_ms and (session_id is None or t.session_id == session_id)
        ]
        return sorted(pending, key=lambda t: t.created_ms)

    async def _audit(self, action: str, ticket: ApprovalTicket) -> None:
        if self._on_audit is None:
            return
        payload = {
            "ticket_id": ticket.id,
            "session_id": ticket.session_id,
            "tool": ticket.tool,
            "arguments_sha256": ticket.arguments_sha256,
            "status": str(ticket.status),
            "operator_id": ticket.operator_id,
            "reason": ticket.reason,
        }
        await _maybe_await(self._on_audit(action, payload))

    async def _notify(self, ticket: ApprovalTicket) -> None:
        if self._on_ticket is None:
            return
        try:
            await _maybe_await(self._on_ticket(ticket))
        except Exception:
            # Benachrichtigung ist ein Nebenpfad: das Ticket ist bereits persistiert.
            return


__all__ = [
    "DAILY_PNL_PREFIX",
    "HALT_SYMBOL_PREFIX",
    "KILL_SWITCH_KEY",
    "LUA_PRE_EXECUTION_GATE",
    "M8_STATE_PREFIX",
    "RATELIMIT_PREFIX",
    "ApprovalTicket",
    "InMemoryPolicyStore",
    "PermissionTier",
    "PolicyDecision",
    "PolicyStore",
    "PolicyVerdictCode",
    "PreExecutionPolicyEngine",
    "RedisPolicyStore",
    "TicketStatus",
    "arguments_sha256",
    "redis_asyncio_eval_shim",
    "resp_eval_shim",
]
