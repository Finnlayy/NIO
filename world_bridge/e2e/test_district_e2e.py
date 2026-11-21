"""P4 E2E (U19): register_district -> district_upsert -> Slot/Strasse/A*-Graph.
Backend-Integration: MCP-Tool -> Event -> State -> Batcher (Frontend-Allocator platziert
Gebaeude + Strasse + A*-Lauf aus district_upsert; TS-Logik in allocator.ts/roads.ts)."""
from world_bridge.bridge import Bridge
from world_bridge.adapters import WorldAdapter
from world_bridge.tests.test_adapters import FakeClient


def make_bridge():
    live = WorldAdapter("live", "b1", "/tmp", FakeClient())
    shadow = WorldAdapter("shadow", "b2", "/tmp", FakeClient())
    return Bridge({"live": live, "shadow": shadow}, token="t")


def test_register_district_emits_event_and_state():
    b = make_bridge()
    ev = b.mcp.call_tool("world_register_district",
                         {"world_id": "live", "district_id": "forge-1", "district_type": "forge"})
    assert ev["type"] == "district_upsert"
    assert ev["payload"]["district_type"] == "forge"
    assert b.store.get("live").districts["forge-1"]["district_type"] == "forge"
    assert b.batchers["live"].pending() >= 1  # geht an WS-Client -> Allocator


def test_register_then_retire_district():
    b = make_bridge()
    b.mcp.call_tool("world_register_district", {"world_id": "live", "district_id": "d", "district_type": "vault"})
    ev = b.mcp.call_tool("world_retire_district", {"world_id": "live", "district_id": "d"})
    assert ev["type"] == "district_remove"
    assert "d" not in b.store.get("live").districts


def test_district_world_isolation():
    b = make_bridge()
    b.mcp.call_tool("world_register_district", {"world_id": "shadow", "district_id": "s", "district_type": "tavern"})
    assert "s" in b.store.get("shadow").districts
    assert "s" not in b.store.get("live").districts


def test_sync_agent_and_orb_state():
    b = make_bridge()
    b.mcp.call_tool("world_set_orb_state", {"world_id": "live", "state": "dispatching"})
    assert b.store.get("live").orb == "dispatching"
    ev = b.mcp.call_tool("world_sync_agent", {"world_id": "live", "agent_id": "worker:c"})
    assert ev["type"] == "agent_upsert"
