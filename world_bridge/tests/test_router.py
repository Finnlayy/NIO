import pytest
from world_bridge.router import CommandRouter, CommandError
from world_bridge.adapters import WorldAdapter
from world_bridge.state import StateStore
from world_bridge.tests.test_adapters import FakeClient

NIO="/home/finn-powers/Projects/NIO"; NIN="/home/finn-powers/NIN"

def make_router(live_gates=None):
    live=WorldAdapter("live","b-live",NIO,FakeClient())
    shadow=WorldAdapter("shadow","b-shadow",NIN,FakeClient())
    store=StateStore()
    for g in (live_gates or []):
        store.get("live").gates[g["gate_id"]]={"gate_id":g["gate_id"],"severity":"info","source":"kanban"}
    return CommandRouter({"live":live,"shadow":shadow},{"live":{NIO},"shadow":{NIN}},store), live, shadow, store

@pytest.mark.anyio
async def test_fail_closed_world():
    r,_,_,_=make_router()
    with pytest.raises(CommandError) as e:
        await r.handle({"command":"dispatch_prompt","world_id":"bogus","args":{"required_skills":["code"]}})
    assert e.value.status==400
    with pytest.raises(CommandError):
        await r.handle({"command":"dispatch_prompt","args":{"required_skills":["code"]}})

@pytest.mark.anyio
async def test_dispatch_requires_skills():
    r,_,_,_=make_router()
    with pytest.raises(CommandError):
        await r.handle({"command":"dispatch_prompt","world_id":"live","args":{"title":"x","required_skills":[]}})

@pytest.mark.anyio
async def test_dispatch_repo_allowlist():
    r,_,_,_=make_router()
    with pytest.raises(CommandError) as e:
        await r.handle({"command":"dispatch_prompt","world_id":"shadow","args":{"required_skills":["code"],"workspace_repo":NIO}})
    assert e.value.status==403

@pytest.mark.anyio
async def test_dispatch_ok_creates_on_world_board():
    r,live,shadow,_=make_router()
    res=await r.handle({"command":"dispatch_prompt","world_id":"shadow","args":{"title":"x","description":"d","required_skills":["code"]}})
    assert res["ok"] and res["world_id"]=="shadow"
    assert shadow.client.created and shadow.client.created[0]["board_id"]=="b-shadow"
    assert not live.client.created

@pytest.mark.anyio
async def test_resolve_gate_world_check():
    r,_,_,store=make_router(live_gates=[{"gate_id":"g1"}])
    with pytest.raises(CommandError) as e:
        await r.handle({"command":"resolve_gate","world_id":"shadow","args":{"gate_id":"g1","action":"approve"}})
    assert e.value.status==403
    res=await r.handle({"command":"resolve_gate","world_id":"live","args":{"gate_id":"g1","action":"approve"}})
    assert res["ok"]
    assert "g1" not in store.get("live").gates  # resolved entfernt

@pytest.mark.anyio
async def test_resolve_mcp_gate_no_kanban_call():
    r,live,_,store=make_router()
    store.get("shadow").gates["mg"]={"gate_id":"mg","severity":"info","source":"mcp"}
    res=await r.handle({"command":"resolve_gate","world_id":"shadow","args":{"gate_id":"mg","action":"approve"}})
    assert res["ok"]
    assert "mg" not in store.get("shadow").gates

@pytest.mark.anyio
async def test_promote_only_shadow_with_gate():
    r,_,_,_=make_router()
    with pytest.raises(CommandError):
        await r.handle({"command":"promote_limb_or_config","world_id":"live","args":{"limb_or_config":"x"},"operator_modal_confirmed":True})
    with pytest.raises(CommandError):
        await r.handle({"command":"promote_limb_or_config","world_id":"shadow","args":{"limb_or_config":"x"}})
    res=await r.handle({"command":"promote_limb_or_config","world_id":"shadow","args":{"limb_or_config":"x","gate_approved":True},"operator_modal_confirmed":True})
    assert res["ok"]
