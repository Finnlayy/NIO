"""Tests für die Control-Plane-Routen ``/api/runtime`` (NIO Phase 4).

Abgedeckt: Auth (503 ohne Token, 401 bei fehlendem/falschem Token), der DAG-Lebenszyklus
(undo/retry), Abbruch über das ``SandboxAgent.abort``-Protokoll mit Ledger-Eintrag, der
Freigabe-Lebenszyklus (pending → resolve, 404/409) mit ``operator_id`` aus der Auth und
der SSE-Strom über den Kanban-Bus. Keine Netzwerkzugriffe, keine Dienste; SQLite und
In-Memory-Adapter in einem temporären Verzeichnis.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - Umgebung ohne FastAPI
    TestClient = None  # type: ignore[assignment,misc]

from apollo.ciel.policy_gate import PermissionTier, PolicyVerdictCode
from orchestrator.kanban.bus import InProcessBus
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import KanbanEvent
from orchestrator.kanban.runtime import build_runtime

pytestmark = pytest.mark.skipif(TestClient is None, reason="FastAPI nicht installiert")

if TestClient is not None:
    from orchestrator.kanban.api import _sse_events, build_app

TOKEN = "secret-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class _FakeAgent:
    """Minimaler Agent: nimmt das Abbruch-Protokoll entgegen und protokolliert den Aufruf."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def abort(self, session_id: str, reason: Any = "USER_ABORT", detail: str = "") -> int:
        self.calls.append((session_id, str(reason), detail))
        return 1


@pytest.fixture
def make_runtime(tmp_path: Path):
    created: list[Any] = []

    def factory(token: str = TOKEN) -> Any:
        config = KanbanConfig(
            repo_root=tmp_path,
            store="sqlite",
            sqlite_path=tmp_path / "kanban.db",
            bus="memory",
            sandbox="subprocess",
            workspace_dir=tmp_path / "workspace",
            vault_dir=tmp_path / "vault",
            api_token=token,
            stop_file=tmp_path / "runtime" / "STOP",
        )
        runtime = asyncio.run(build_runtime(config))
        created.append(runtime)
        return runtime

    yield factory
    for runtime in created:
        asyncio.run(runtime.close())


def _commit(runtime: Any, session: str, text: str) -> str:
    async def go() -> str:
        node = await runtime.dag.commit_turn(session, user_input=text)
        return str(node.turn_id)

    return asyncio.run(go())


# -- Auth -----------------------------------------------------------------


def test_ohne_konfiguriertes_token_antwortet_503(make_runtime: Any) -> None:
    client = TestClient(build_app(make_runtime(token="")))
    assert client.get("/api/runtime/session/s1/dag", headers=AUTH).status_code == 503
    assert client.post("/api/runtime/session/s1/abort", json={"reason": "x"}, headers=AUTH).status_code == 503


def test_fehlendes_oder_falsches_token_antwortet_401(make_runtime: Any) -> None:
    client = TestClient(build_app(make_runtime()))
    assert client.get("/api/runtime/session/s1/dag").status_code == 401
    wrong = {"Authorization": "Bearer falsch"}
    assert client.get("/api/runtime/session/s1/dag", headers=wrong).status_code == 401
    assert client.get("/api/runtime/approvals/pending").status_code == 401
    assert client.post("/api/runtime/approvals/x/resolve", json={"approved": True}).status_code == 401


# -- DAG: undo / retry ------------------------------------------------------


def test_dag_undo_und_retry_lebenszyklus(make_runtime: Any) -> None:
    runtime = make_runtime()
    client = TestClient(build_app(runtime))
    t1 = _commit(runtime, "s1", "eins")
    t2 = _commit(runtime, "s1", "zwei")
    _commit(runtime, "s1", "drei")

    dag = client.get("/api/runtime/session/s1/dag", headers=AUTH)
    assert dag.status_code == 200
    assert len(dag.json()["lineage"]["ordered_turn_ids"]) == 3

    undo = client.post("/api/runtime/session/s1/undo", json={"steps": 1}, headers=AUTH)
    assert undo.status_code == 200
    ordered = undo.json()["lineage"]["ordered_turn_ids"]
    assert len(ordered) == 2 and ordered[-1] == t2

    # Retry legt einen Branch am Elternknoten des Kopfes an (= t1) und wechselt dorthin.
    retry = client.post("/api/runtime/session/s1/retry", json={"branch_name": "alt"}, headers=AUTH)
    assert retry.status_code == 200
    body = retry.json()
    assert body["lineage"]["branch_name"] == "alt"
    assert body["branches"]["alt"] == t1


def test_dag_eingaben_werden_validiert(make_runtime: Any) -> None:
    runtime = make_runtime()
    client = TestClient(build_app(runtime))
    _commit(runtime, "s1", "eins")
    assert client.post("/api/runtime/session/s1/undo", json={"steps": 0}, headers=AUTH).status_code == 422
    assert client.post("/api/runtime/session/s1/undo", json={"steps": 51}, headers=AUTH).status_code == 422
    # Undo über die Wurzel hinaus: Fachfehler der DAG-Schicht wird zu 422.
    assert client.post("/api/runtime/session/s1/undo", json={"steps": 5}, headers=AUTH).status_code == 422
    assert client.post("/api/runtime/session/leer/undo", json={"steps": 1}, headers=AUTH).status_code == 422


# -- Abort ----------------------------------------------------------------


def test_abort_ruft_agenten_und_schreibt_ledger(make_runtime: Any) -> None:
    runtime = make_runtime()
    agent = _FakeAgent()
    runtime.agents.register("sandbox-1", agent)
    client = TestClient(build_app(runtime))

    resp = client.post("/api/runtime/session/s1/abort", json={"reason": "Stopp durch Operator"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "status": "ABORT_SIGNAL_SENT"}
    assert agent.calls == [("s1", "USER_ABORT", "Stopp durch Operator")]

    entries = asyncio.run(runtime.ledger.entries())
    assert any(e.action == "runtime.abort" and e.subject == "s1" for e in entries)
    assert client.post("/api/runtime/session/s1/abort", json={"reason": ""}, headers=AUTH).status_code == 422


# -- Freigaben ------------------------------------------------------------


def _pending_ticket(runtime: Any, session: str = "s1") -> str:
    runtime.policy.register_tool_tier("risky", PermissionTier.TIER_2_APPROVAL)

    async def go() -> str:
        decision = await runtime.policy.evaluate(session, "risky", {"qty": 1})
        assert decision.code == PolicyVerdictCode.WAITING_APPROVAL
        assert decision.ticket is not None
        return decision.ticket.id

    return asyncio.run(go())


def test_freigabe_lebenszyklus_mit_operator_aus_auth(make_runtime: Any) -> None:
    runtime = make_runtime()
    client = TestClient(build_app(runtime))
    ticket_id = _pending_ticket(runtime)

    pending = client.get("/api/runtime/approvals/pending", params={"session_id": "s1"}, headers=AUTH)
    assert pending.status_code == 200
    assert [t["id"] for t in pending.json()] == [ticket_id]

    # operator_id im Body ist verboten (extra=forbid) und wird nicht übernommen.
    forged = client.post(
        f"/api/runtime/approvals/{ticket_id}/resolve",
        json={"approved": True, "operator_id": "mallory"},
        headers=AUTH,
    )
    assert forged.status_code == 422

    resolved = client.post(
        f"/api/runtime/approvals/{ticket_id}/resolve",
        json={"approved": True, "reason": "geprüft"},
        headers=AUTH,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "APPROVED"
    assert resolved.json()["operator_id"] == "operator"  # Actor aus der Auth

    assert client.get("/api/runtime/approvals/pending", headers=AUTH).json() == []
    again = client.post(f"/api/runtime/approvals/{ticket_id}/resolve", json={"approved": False}, headers=AUTH)
    assert again.status_code == 409


def test_unbekanntes_ticket_ist_404(make_runtime: Any) -> None:
    client = TestClient(build_app(make_runtime()))
    resp = client.post("/api/runtime/approvals/gibt-es-nicht/resolve", json={"approved": True}, headers=AUTH)
    assert resp.status_code == 404


# -- SSE-Strom ------------------------------------------------------------


def test_approval_strom_liefert_nur_freigabe_und_abbruch_ereignisse() -> None:
    async def go() -> str:
        bus = InProcessBus()
        gen = _sse_events(bus, keepalive_s=5.0)
        first = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0.01)  # Die Subscription läuft erst beim ersten __anext__.
        await bus.publish(KanbanEvent(kind="task.created", task_id="t1"))
        await bus.publish(KanbanEvent(kind="approval.pending", payload={"ticket_id": "tk-1"}))
        frame = await asyncio.wait_for(first, timeout=2)
        await gen.aclose()
        return frame

    frame = asyncio.run(go())
    assert frame.startswith("event: approval.pending\n")
    assert '"ticket_id": "tk-1"' in frame
    assert "task.created" not in frame
