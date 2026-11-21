"""FastMCP-kompatible World-Tools (T7) ueber Standard-MCP-JSON-RPC
(initialize / tools/list / tools/call) — dependency-frei, wie kanban mcp_shim."""
from __future__ import annotations
from typing import Any, Callable
from .state import StateStore
from .events import CityEvent

TOOL_DEFS = {
    "world_register_district": ["world_id", "district_id", "district_type"],
    "world_retire_district": ["world_id", "district_id"],
    "world_sync_agent": ["world_id", "agent_id"],
    "world_set_orb_state": ["world_id", "state"],
    "world_raise_gate": ["world_id", "gate_id", "severity", "prompt"],
}


class MCPToolServer:
    def __init__(self, store: StateStore, on_event: Callable[[CityEvent], None] | None = None) -> None:
        self.store = store
        self.on_event = on_event

    def _emit(self, ev: CityEvent) -> dict:
        self.store.get(ev.world_id).apply(ev)
        if self.on_event:
            self.on_event(ev)
        return ev.to_dict()

    def call_tool(self, name: str, args: dict[str, Any]) -> dict:
        if name not in TOOL_DEFS:
            raise ValueError(f"unbekanntes Tool: {name}")
        for req in TOOL_DEFS[name]:
            if req not in args and not (name == "world_raise_gate" and req == "prompt"):
                raise ValueError(f"Argument fehlt: {req}")
        w = self.store.get(args["world_id"])
        if name == "world_register_district":
            return self._emit(w.register_district(args["district_id"], args["district_type"]))
        if name == "world_retire_district":
            return self._emit(w.retire_district(args["district_id"]))
        if name == "world_sync_agent":
            return self._emit(w.sync_agent(args["agent_id"]))
        if name == "world_set_orb_state":
            return self._emit(w.set_orb_state(args["state"]))
        if name == "world_raise_gate":
            return self._emit(w.raise_gate(args["gate_id"], args["severity"], args.get("prompt", "")))
        raise ValueError(name)

    def handle(self, req: dict[str, Any]) -> dict[str, Any]:
        method = req.get("method")
        mid = req.get("id")
        params = req.get("params") or {}
        try:
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05",
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "nio-world-bridge", "version": "1.0"}}
            elif method == "tools/list":
                result = {"tools": [{"name": n,
                                     "inputSchema": {"type": "object",
                                                     "properties": {a: {"type": "string"} for a in args},
                                                     "required": args}}
                                    for n, args in TOOL_DEFS.items()]}
            elif method == "tools/call":
                result = {"content": [{"type": "text",
                                       "text": __import__("json").dumps(self.call_tool(params["name"], params.get("arguments", {})))}]}
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method {method}"}}
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        except (ValueError, KeyError) as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": str(e)}}
