import pytest
from fastapi.testclient import TestClient
from world_bridge.bridge import Bridge
from world_bridge.adapters import WorldAdapter
from world_bridge.tests.test_adapters import FakeClient

NIO="/home/finn-powers/Projects/NIO"; NIN="/home/finn-powers/NIN"

def make_bridge(token="secret"):
    live=WorldAdapter("live","b-live",NIO,FakeClient(workers=[{"uid":"c","status":"idle"}]))
    shadow=WorldAdapter("shadow","b-shadow",NIN,FakeClient())
    return Bridge({"live":live,"shadow":shadow}, token=token)

def test_health():
    c=TestClient(make_bridge().create_app())
    assert c.get("/health").json()["ok"]

def test_auth_fail_closed_no_token():
    c=TestClient(make_bridge(token="").create_app())
    r=c.post("/api/world/command",json={"command":"dispatch_prompt","world_id":"live","args":{"required_skills":["code"]}})
    assert r.status_code==503

def test_auth_wrong_token():
    c=TestClient(make_bridge().create_app())
    r=c.post("/api/world/command",json={},headers={"Authorization":"Bearer wrong"})
    assert r.status_code==401

def test_command_dispatch_ok():
    b=make_bridge(); c=TestClient(b.create_app())
    r=c.post("/api/world/command",json={"command":"dispatch_prompt","world_id":"live","args":{"title":"x","description":"d","required_skills":["code"]}},headers={"Authorization":"Bearer secret"})
    assert r.status_code==200 and r.json()["ok"]

def test_command_bad_world_400():
    c=TestClient(make_bridge().create_app())
    r=c.post("/api/world/command",json={"command":"dispatch_prompt","world_id":"bogus","args":{"required_skills":["code"]}},headers={"Authorization":"Bearer secret"})
    assert r.status_code==400

def test_ws_rejects_bad_token():
    c=TestClient(make_bridge().create_app())
    with pytest.raises(Exception):
        with c.websocket_connect("/ws/world?token=wrong") as ws:
            ws.receive_json()

def test_ws_sends_snapshot():
    c=TestClient(make_bridge().create_app())
    with c.websocket_connect("/ws/world?token=secret&world_id=live") as ws:
        msg=ws.receive_json()
        assert msg["type"]=="world_snapshot" and msg["world_id"]=="live"
        assert set(msg["payload"])=={"agents","districts","gates","orb","commit_stand"}

@pytest.mark.anyio
async def test_stream_finite():
    b=make_bridge()
    msgs=[m async for m in b.stream(["live"], iterations=1)]
    assert msgs[0]["type"]=="world_snapshot"
    assert all(m["seq"]>=1 for m in msgs)

@pytest.mark.anyio
async def test_stream_resume_filters_seq():
    b=make_bridge()
    all_msgs=[m async for m in b.stream(["live"], iterations=1)]
    last=all_msgs[0]["seq"]
    resumed=[m async for m in b.stream(["live"], last_event_id=last, iterations=1)]
    assert all(m["seq"]>last for m in resumed)
