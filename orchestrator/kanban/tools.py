from __future__ import annotations

from collections.abc import Callable
from typing import Any

import core.schemacheck

from .bus import TokenStore
from .service import KanbanService

__all__ = ["TOOL_DEFINITIONS", "KanbanToolbox", "register_kanban_tools"]

TOOL_DEFINITIONS = [
    {
        "name": "kanban_show",
        "description": "Zeigt einen Task und seine Kinder an.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"}
            },
        },
    },
    {
        "name": "kanban_create",
        "description": "Erstellt einen neuen Child-Task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "required_skills": {"type": "array", "items": {"type": "string"}},
                "dependencies": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title"],
        },
    },
    {
        "name": "kanban_block",
        "description": "Blockiert den eigenen Task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "kanban_complete",
        "description": "Schließt den eigenen Task ab.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "result_payload": {"type": "object"},
            },
            "required": ["result_payload"],
        },
    },
    {
        "name": "kanban_heartbeat",
        "description": "Sendet einen Heartbeat für den eigenen Task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note": {"type": "string"},
            },
        },
    },
]

class KanbanToolbox:
    def __init__(self, service: KanbanService, tokens: TokenStore) -> None:
        self._service = service
        self._tokens = tokens

    async def call(self, name: str, arguments: dict[str, Any], token: str) -> dict[str, Any]:
        claims = await self._tokens.get(token)
        if not claims:
            raise PermissionError("invalid or expired task token")

        task_id = claims["task_id"]
        worker_uid = claims["worker_uid"]
        actor = f"worker:{worker_uid}"

        tool_def = next((t for t in TOOL_DEFINITIONS if t["name"] == name), None)
        if not tool_def:
            raise KeyError(f"Unbekanntes Tool: {name}")

        try:
            core.schemacheck.validate(arguments, tool_def.get("inputSchema", {}) or {}) # type: ignore
        except Exception as e:
            raise ValueError(f"Ungültige Argumente für {name}: {e}") from e

        if name == "kanban_show":
            target_id = arguments.get("task_id", task_id)
            if target_id != task_id:
                task_data = await self._service.show(task_id)
                child_ids = [c["id"] for c in task_data["children"]]
                if target_id not in child_ids:
                    raise PermissionError(f"Zugriff auf Task {target_id} verweigert")
            return await self._service.show(target_id)

        if name == "kanban_create":
            task_data = await self._service.show(task_id)
            board_id = task_data["task"]["board_id"]
            new_task = await self._service.create_task(
                board_id=board_id,
                title=arguments["title"],
                description=arguments.get("description", ""),
                parent_id=task_id,
                dependencies=arguments.get("dependencies", []),
                required_skills=arguments.get("required_skills", []),
                actor=actor,
            )
            return {"task": new_task.to_dict()}

        if name == "kanban_block":
            task = await self._service.block(task_id, reason=arguments["reason"], actor=actor)
            return {"task": task.to_dict()}

        if name == "kanban_complete":
            task = await self._service.complete(task_id, result_payload=arguments["result_payload"], actor=actor)
            return {"task": task.to_dict()}

        if name == "kanban_heartbeat":
            await self._service.heartbeat(task_id, worker_uid=worker_uid)
            return {"status": "ok"}

        raise KeyError(f"Tool {name} nicht implementiert")

class RegistryProtocol:
    def register(
        self,
        tool: Any,
        *,
        handler: Any | None = None,
        origin: str = "fastmcp",
        persist: bool = True
    ) -> Any: ...

def register_kanban_tools(registry: Any, toolbox: KanbanToolbox, token_provider: Callable[[], str]) -> None:
    import importlib
    importlib.import_module("apollo.ciel.registry")

    _registry: RegistryProtocol = registry

    for tool_def in TOOL_DEFINITIONS:
        name_str: str = str(tool_def["name"])

        def make_handler(tool_name: str) -> Callable[[dict[str, Any]], Any]:
            async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
                token = token_provider()
                return await toolbox.call(tool_name, arguments, token)
            return handler

        _registry.register(
            tool_def,
            handler=make_handler(name_str),
            origin="kanban",
            persist=False
        )
