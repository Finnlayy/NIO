"""P4 E2E (U20+U21): Gate-Klick -> resolve_gate; Wetter/Twin-View getrennt;
offline nur Orb idle (D2); divergence_diff + Commit-Stand je Welt."""
import pytest
from world_bridge.bridge import Bridge
from world_bridge.adapters import WorldAdapter
from world_bridge.router import CommandError
from world_bridge.divergence import compute_divergence
from world_bridge.tests.test_adapters import FakeClient


def make_bridge(gates=None):
    live = WorldAdapter("live", "b1", "/tmp", FakeClient(approvals=gates or []))
    shadow = WorldAdapter("shadow", "b2", "/tmp", FakeClient())
    return Bridge({"live": live, "shadow": shadow}, token="t"), live, shadow


def test_raise_gate_priority():
    b, _, _ = make_bridge()
    ev = b.mcp.call_tool("world_raise_gate", {"world_id": "live", "gate_id": "g", "severity": "critical", "prompt": "p"})
    assert ev["type"] == "gate_alert" and ev["priority"] is True


@pytest.mark.anyio
async def test_gate_klick_resolve_gate():
    b, _, _ = make_bridge(gates=[{"id": "g1", "severity": "warning", "board_id": "b1"}])
    res = await b.router.handle({"command": "resolve_gate", "world_id": "live",
                                 "args": {"gate_id": "g1", "action": "approve"}})
    assert res["ok"] and res["action"] == "approve"


@pytest.mark.anyio
async def test_resolve_gate_cross_world_rejected():
    b, _, _ = make_bridge(gates=[{"id": "g1", "severity": "info", "board_id": "b1"}])
    with pytest.raises(CommandError) as e:
        await b.router.handle({"command": "resolve_gate", "world_id": "shadow",
                               "args": {"gate_id": "g1", "action": "approve"}})
    assert e.value.status == 403


def test_offline_only_orb_idle_D2():
    b, _, _ = make_bridge()
    # D2: kein Mock/Fallback — ohne Backend-Events ist Orb idle
    assert b.store.get("live").orb == "idle"
    assert b.store.get("shadow").orb == "idle"


def test_wetter_twinview_getrennt():
    # Wetter folgt world_id (live=Sonne, shadow=Regen); Twin-View activeWorld separat.
    b, _, _ = make_bridge()
    b.mcp.call_tool("world_set_orb_state", {"world_id": "live", "state": "idle"})
    b.mcp.call_tool("world_set_orb_state", {"world_id": "shadow", "state": "alert"})
    assert b.store.get("live").orb == "idle"
    assert b.store.get("shadow").orb == "alert"  # strikt getrennt


@pytest.mark.anyio
async def test_divergence_diff_commit_stand():
    live = WorldAdapter("live", "b1", "/tmp", FakeClient(workers=[{"uid": "c", "status": "idle"}]))
    shadow = WorldAdapter("shadow", "b2", "/tmp", FakeClient(workers=[{"uid": "c", "status": "busy"}]))
    ev = await compute_divergence(live, shadow)
    assert ev.type == "divergence_diff"
    assert "commit_stand_live" in ev.payload and "commit_stand_shadow" in ev.payload
    assert ev.payload["entities"][0]["kind"] == "state_diff"
