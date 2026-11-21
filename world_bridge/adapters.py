"""Welt-Adapter + kanban-HTTP-Client (T3 shadow / T4 live). D3: eigene Client-Instanz
je Welt, kein gemeinsamer Pool. Wiederverwendung der kanban-API (keine Business-Duplikate).
"""
from __future__ import annotations
import asyncio
import subprocess
from typing import Any, Protocol
from . import mapping as M
from .events import CityEvent, SeqGen


class KanbanAPI(Protocol):
    async def get_workers(self) -> list[dict[str, Any]]: ...
    async def get_tasks(self, board_id: str | None = None) -> list[dict[str, Any]]: ...
    async def get_approvals(self) -> list[dict[str, Any]]: ...
    async def create_task(self, body: dict[str, Any]) -> dict[str, Any]: ...
    async def transition_task(self, task_id: str, target: str, reason: str = "") -> dict[str, Any]: ...
    async def resolve_approval(self, gate_id: str, action: str) -> dict[str, Any]: ...


class HttpKanbanClient:
    """Async-Client gegen die kanban-API (httpx). Eigene Instanz je Welt."""
    def __init__(self, base_url: str, token: str, client: Any = None) -> None:
        import httpx
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = client or httpx.AsyncClient(base_url=self._base, headers=self._headers, timeout=15.0)

    async def _get(self, path: str) -> Any:
        r = await self._client.get(path, headers=self._headers)
        r.raise_for_status()
        return r.json()

    async def _post(self, path: str, body: dict) -> Any:
        r = await self._client.post(path, json=body, headers=self._headers)
        r.raise_for_status()
        return r.json()

    async def get_workers(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/workers")

    async def get_tasks(self, board_id: str | None = None) -> list[dict[str, Any]]:
        data = await self._get("/api/v1/kanban/tasks")
        tasks = [e.get("task", e) for e in data]
        if board_id:
            tasks = [t for t in tasks if t.get("board_id") == board_id]
        return tasks

    async def get_approvals(self) -> list[dict[str, Any]]:
        try:
            return await self._get("/api/v1/runtime/approvals")
        except Exception:
            return []

    async def create_task(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._post("/api/v1/kanban/tasks", body)

    async def transition_task(self, task_id: str, target: str, reason: str = "") -> dict[str, Any]:
        return await self._post(f"/api/v1/kanban/tasks/{task_id}/transition",
                                {"target": target, "reason": reason})

    async def resolve_approval(self, gate_id: str, action: str) -> dict[str, Any]:
        return await self._post(f"/api/v1/runtime/approvals/{gate_id}/{action}", {})

    async def aclose(self) -> None:
        await self._client.aclose()


def git_commit_stand(repo_path: str) -> str:
    try:
        r = subprocess.run(["git", "-C", repo_path, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


_STATIC_DISTRICTS = ("bootstrap", "vault", "tavern", "forge", "tavern_limbs")


class WorldAdapter:
    """Eine Welt (live oder shadow). Eigener Client/Board/Repo — D3-Isolation."""
    def __init__(self, world_id: str, board_id: str, repo_path: str, client: KanbanAPI) -> None:
        if world_id not in ("live", "shadow"):
            raise ValueError(world_id)
        self.world_id = world_id
        self.board_id = board_id
        self.repo_path = repo_path
        self.client = client
        self.seq = SeqGen()
        self._prev: dict[str, Any] | None = None

    async def snapshot(self) -> dict[str, Any]:
        workers = await self.client.get_workers()
        tasks = await self.client.get_tasks(self.board_id)
        approvals = await self.client.get_approvals()
        agents: dict[str, dict] = {}
        for w in workers:
            ev = M.map_worker(w, self.world_id)
            agents[ev.payload["agent_id"]] = ev.payload
        for t in tasks:
            ev = M.map_task(t, self.world_id)
            if ev:
                agents[ev.payload["agent_id"]] = ev.payload
        gates = [M.map_approval(a, self.world_id).payload
                 for a in approvals if not a.get("board_id") or a.get("board_id") == self.board_id]
        districts = [{"district_id": f"district:{d}", "district_type": d} for d in _STATIC_DISTRICTS]
        for g in gates:
            districts.append({"district_id": f"gate:{g['gate_id']}", "district_type": "gate_outpost"})
        active = sum(1 for t in tasks if t.get("status") == "in_progress")
        ready = sum(1 for t in tasks if t.get("status") == "ready")
        orb = M.map_orb({"active_jobs": active, "open_gates": len(gates), "listening": ready > 0},
                        self.world_id).payload
        return {"agents": list(agents.values()), "districts": districts, "gates": gates,
                "orb": orb, "commit_stand": git_commit_stand(self.repo_path)}

    async def poll_events(self) -> list[CityEvent]:
        """Snapshot-Diff -> Events (upserts/removes/orb/gates)."""
        snap = await self.snapshot()
        events: list[CityEvent] = []
        if self._prev is None:
            events.append(CityEvent("world_snapshot", self.world_id, snap, self.seq.next()))
        else:
            pa = {a["agent_id"]: a for a in self._prev["agents"]}
            na = {a["agent_id"]: a for a in snap["agents"]}
            for aid, a in na.items():
                if pa.get(aid) != a:
                    events.append(CityEvent("agent_upsert", self.world_id, a, self.seq.next()))
            for aid in pa.keys() - na.keys():
                events.append(CityEvent("agent_remove", self.world_id, {"agent_id": aid}, self.seq.next()))
            pd = {d["district_id"] for d in self._prev["districts"]}
            for d in snap["districts"]:
                if d["district_id"] not in pd:
                    events.append(CityEvent("district_upsert", self.world_id, d, self.seq.next()))
            nd = {d["district_id"] for d in snap["districts"]}
            for did in pd - nd:
                events.append(CityEvent("district_remove", self.world_id, {"district_id": did}, self.seq.next()))
            pg = {g["gate_id"] for g in self._prev["gates"]}
            for g in snap["gates"]:
                if g["gate_id"] not in pg:
                    events.append(CityEvent("gate_alert", self.world_id, g, self.seq.next()))
            if snap["orb"] != self._prev["orb"]:
                events.append(CityEvent("orb_update", self.world_id, snap["orb"], self.seq.next()))
        self._prev = snap
        return events
