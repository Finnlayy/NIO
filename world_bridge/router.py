"""Command-Router POST /api/world/command (T8) — D3 serverseitige Welt-Isolation.
fail-closed world_id; required_skills-Guard; workspace_repo-Allowlist je Welt;
Gate-Welt-Pruefung ueber den Welt-Zustand (Store); promote nur shadow + Operator-Gate.
Kein gemeinsamer Client-Pool. Gates: live=echte kanban-CIEL-Tickets, shadow=MCP-State."""
from __future__ import annotations
from typing import Any
from .adapters import WorldAdapter
from .state import StateStore


class CommandError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class CommandRouter:
    def __init__(self, adapters: dict[str, WorldAdapter],
                 repo_allowlist: dict[str, set[str]], store: StateStore) -> None:
        self._adapters = adapters
        self._allow = {w: set(v) for w, v in repo_allowlist.items()}
        self._store = store

    def _world(self, world_id: Any) -> WorldAdapter:
        if world_id not in self._adapters:
            raise CommandError(f"ungueltige/fehlende world_id: {world_id!r}", 400)
        return self._adapters[world_id]

    async def handle(self, body: dict[str, Any]) -> dict[str, Any]:
        cmd = body.get("command")
        world_id = body.get("world_id")
        adapter = self._world(world_id)  # fail-closed
        args = body.get("args") or {}
        if cmd == "dispatch_prompt":
            return await self._dispatch(adapter, world_id, args)
        if cmd == "resolve_gate":
            return await self._resolve(adapter, world_id, args)
        if cmd == "promote_limb_or_config":
            return await self._promote(adapter, world_id, args, body)
        raise CommandError(f"unbekanntes command: {cmd!r}", 400)

    async def _dispatch(self, adapter: WorldAdapter, world_id: str, args: dict) -> dict:
        skills = args.get("required_skills") or []
        if not skills:
            raise CommandError("required_skills darf nicht leer sein (Routing-Guard)", 400)
        repo = args.get("workspace_repo") or adapter.repo_path
        if repo not in self._allow.get(world_id, set()):
            raise CommandError(f"workspace_repo {repo!r} nicht erlaubt fuer Welt {world_id!r} (D3)", 403)
        task = await adapter.client.create_task({
            "board_id": adapter.board_id,
            "title": args.get("title", ""),
            "description": args.get("description", ""),
            "required_skills": list(skills),
            "workspace_repo": repo,
            "status": "blocked",
            "priority": int(args.get("priority", 0)),
        })
        return {"ok": True, "world_id": world_id, "task_id": task.get("id")}

    async def _resolve(self, adapter: WorldAdapter, world_id: str, args: dict) -> dict:
        gate_id = args.get("gate_id")
        action = args.get("action")
        if action not in ("approve", "reject"):
            raise CommandError("action muss approve|reject sein", 400)
        if not gate_id:
            raise CommandError("gate_id fehlt", 400)
        world_state = self._store.get(world_id)
        gate = world_state.gates.get(gate_id)
        if gate is None:
            raise CommandError(f"Gate {gate_id!r} gehoert nicht zur Welt {world_id!r} (D3)", 403)
        if gate.get("source") == "kanban":
            await adapter.client.resolve_approval(gate_id, action)
        del world_state.gates[gate_id]
        return {"ok": True, "world_id": world_id, "gate_id": gate_id, "action": action}

    async def _promote(self, adapter: WorldAdapter, world_id: str, args: dict, body: dict) -> dict:
        if world_id != "shadow":
            raise CommandError("promote nur aus shadow (D3)", 403)
        if not body.get("operator_modal_confirmed"):
            raise CommandError("Operator-Modal-Bestaetigung erforderlich", 403)
        if not args.get("gate_approved"):
            raise CommandError("resolve_gate(approve) erforderlich vor promote", 403)
        return {"ok": True, "world_id": world_id, "promoted": args.get("limb_or_config"),
                "note": "Orchestrator merged nach Git-Guardrails (Guide/Operator-Schritt)"}
