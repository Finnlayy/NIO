import json
from world_bridge.mcp_tools import MCPToolServer, TOOL_DEFS
from world_bridge.state import StateStore

def test_tools_list():
    s=MCPToolServer(StateStore())
    r=s.handle({"jsonrpc":"2.0","id":1,"method":"tools/list"})
    names={t["name"] for t in r["result"]["tools"]}
    assert names==set(TOOL_DEFS)

def test_register_district_emits_and_applies():
    store=StateStore(); events=[]
    s=MCPToolServer(store, on_event=events.append)
    r=s.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"world_register_district","arguments":{"world_id":"live","district_id":"d1","district_type":"forge"}}})
    assert "result" in r
    assert store.get("live").districts["d1"]["district_type"]=="forge"
    assert events[0].type=="district_upsert"

def test_set_orb_state():
    store=StateStore(); s=MCPToolServer(store)
    s.call_tool("world_set_orb_state",{"world_id":"shadow","state":"alert"})
    assert store.get("shadow").orb=="alert"

def test_raise_gate_priority():
    store=StateStore(); ev=[]
    s=MCPToolServer(store,on_event=ev.append)
    s.call_tool("world_raise_gate",{"world_id":"live","gate_id":"g","severity":"critical","prompt":"p"})
    assert ev[0].priority

def test_world_isolation():
    store=StateStore(); s=MCPToolServer(store)
    s.call_tool("world_register_district",{"world_id":"live","district_id":"d","district_type":"vault"})
    assert "d" not in store.get("shadow").districts

def test_bad_tool_error():
    s=MCPToolServer(StateStore())
    r=s.handle({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"nope","arguments":{}}})
    assert "error" in r

def test_initialize():
    s=MCPToolServer(StateStore())
    r=s.handle({"jsonrpc":"2.0","id":1,"method":"initialize"})
    assert r["result"]["serverInfo"]["name"]=="nio-world-bridge"
