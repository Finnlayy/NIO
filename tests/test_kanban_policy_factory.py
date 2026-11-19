"""Tests für die Policy-Factory in ``orchestrator/kanban/runtime.py`` (NIO Phase 1).

Die Factory verdrahtet die Ciel-Policy mit Audit-Ledger und Notifier. Sie wird
nur gebaut, nicht global eingeschaltet. Die Tests laufen über einen echten
In-Memory-SQLite-Store, damit die Hash-Kette des Ledgers tatsächlich geprüft wird.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from apollo.ciel.policy_gate import PermissionTier, PolicyVerdictCode, TicketStatus
from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.runtime import build_pre_execution_policy
from orchestrator.kanban.store import SqliteKanbanStore


class _Notifier:
    """Notifier-Stub: sammelt Benachrichtigungen."""

    def __init__(self) -> None:
        self.texte: list[str] = []

    async def alert(self, text: str) -> bool:
        self.texte.append(text)
        return True


async def _mit_store(ablauf: Any) -> Any:
    store = SqliteKanbanStore(":memory:")
    await store.init()
    try:
        return await ablauf(store)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            await close()


def test_factory_schreibt_ticket_lebenszyklus_ins_hash_ledger() -> None:
    async def ablauf(store: Any) -> dict[str, Any]:
        ledger = AuditLedger(store)
        notifier = _Notifier()
        runtime = SimpleNamespace(redis=None, ledger=ledger, notifier=notifier)
        engine = build_pre_execution_policy(runtime, tool_tiers={"risky": PermissionTier.TIER_2_APPROVAL})

        decision = await engine.evaluate("s1", "risky", {"qty": 1})
        assert decision.code == PolicyVerdictCode.WAITING_APPROVAL
        assert decision.ticket is not None
        await engine.resolve_ticket(decision.ticket.id, approved=True, operator_id="finn", reason="ok")
        consumed = await engine.evaluate("s1", "risky", {"qty": 1}, approval_ticket_id=decision.ticket.id)

        entries = await ledger.entries()
        return {
            "ticket_id": decision.ticket.id,
            "consumed_code": consumed.code,
            "entries": [(e.actor, e.action, e.category, e.subject) for e in entries],
            "verify": await ledger.verify(),
            "notifiziert": list(notifier.texte),
        }

    ergebnis = asyncio.run(_mit_store(ablauf))
    assert ergebnis["consumed_code"] == PolicyVerdictCode.OK
    assert [(actor, action) for actor, action, _c, _s in ergebnis["entries"]] == [
        ("policy", "approval.create"),
        ("policy", "approval.approve"),
        ("policy", "approval.consume"),
    ]
    # Kategorie bleibt im bestehenden CHECK-Constraint, Subject ist die Ticket-ID.
    assert all(category == "system" for _a, _x, category, _s in ergebnis["entries"])
    assert all(subject == ergebnis["ticket_id"] for _a, _x, _c, subject in ergebnis["entries"])
    assert ergebnis["verify"] == []  # Hash-Kette intakt
    assert len(ergebnis["notifiziert"]) == 1
    assert ergebnis["ticket_id"] in ergebnis["notifiziert"][0]


def test_factory_ohne_tool_tiers_stuft_unbekannte_tools_als_tier1_ein() -> None:
    async def ablauf(store: Any) -> PermissionTier:
        runtime = SimpleNamespace(redis=None, ledger=AuditLedger(store), notifier=_Notifier())
        engine = build_pre_execution_policy(runtime)
        return engine.tier_for("irgendein_tool")

    assert asyncio.run(_mit_store(ablauf)) == PermissionTier.TIER_1_GUARD


def test_factory_ticket_status_bleibt_pending_ohne_resolve() -> None:
    async def ablauf(store: Any) -> TicketStatus:
        runtime = SimpleNamespace(redis=None, ledger=AuditLedger(store), notifier=_Notifier())
        engine = build_pre_execution_policy(runtime, tool_tiers={"risky": PermissionTier.TIER_2_APPROVAL})
        decision = await engine.evaluate("s1", "risky", {"qty": 1})
        assert decision.ticket is not None
        pending = await engine.pending_tickets("s1")
        assert [t.id for t in pending] == [decision.ticket.id]
        return pending[0].status

    assert asyncio.run(_mit_store(ablauf)) == TicketStatus.PENDING
