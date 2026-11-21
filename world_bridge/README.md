# NIO World-Bridge (P2)

Twin-City Sicht-/Steueroberflaeche. FastAPI loopback 127.0.0.1:8750.
Single Source of Truth = NIO kanban (:8740) + Redis. D3: serverseitige Welt-Isolation.

## Module
- nio_world_api_spec.yaml + spec.py: WS/REST/MCP-Vertrag + Validierung/Contract.
- events.py: CityEvent-Modell (world_id, seq, timestamp_ms, payload), Priority gate_alert.
- mapping.py: 7 NIO-Entity -> Stadt-Event (Plan Tabelle 3).
- adapters.py / live.py / shadow.py: kanban-HTTP-Client + Welt-Adapter (eigene Instanz je Welt).
- divergence.py: divergence_diff live-vs-shadow + Commit-Stand.
- state.py: Welt-Zustand (Adapter-Events + MCP-Tools).
- batch.py: Throttle <=15Hz + Priority-Lane gate_alert + Koaleszieren.
- router.py: Command-Router (dispatch_prompt/resolve_gate/promote), D3-Guards fail-closed.
- mcp_tools.py: MCP-JSON-RPC Tools (register/retire_district, sync_agent, set_orb_state, raise_gate).
- bridge.py: FastAPI-App, WS /ws/world Multiplex + Snapshot-Resume, Auth, Static, /api/world/command, /mcp.

## Start (Guide/Operator nach P2-Merge, E2)
1. NIO_WORLD_TOKEN in ~/.config/nio/nio.env setzen (neu).
2. Shadow-Board anlegen (E1), NIO_SHADOW_BOARD_ID in nio.env.
3. systemd: deploy/nio-world-bridge.service nach ~/.config/systemd/user/, daemon-reload, enable --now.
   ODER: NIO_WORLD_TOKEN=... .venv/bin/python -m world_bridge

## Tests
.venv/bin/python -m pytest world_bridge/tests -q

## Hinweise
- Worker-Image hat kein fastmcp; MCP-Tools sind Standard-JSON-RPC (wie kanban mcp_shim).
- Deployment-Aktivierung + Token = Operator/Guide-Schritt (Worker kann kein systemctl).
- Static-Serve liefert P3-Build (client/dist); bis dahin Platzhalter-Index.
