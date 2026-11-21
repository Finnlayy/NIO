from world_bridge.batch import WorldBatcher, MIN_INTERVAL_MS
from world_bridge.events import CityEvent

def mk(t, p, seq=1): return CityEvent(t, "live", p, seq)

def test_rate_limit_defers():
    b = WorldBatcher()
    b.add(mk("orb_update", {"state": "idle"}))
    assert b.drain(0) != []          # erster Flush
    b.add(mk("orb_update", {"state": "listening"}))
    assert b.drain(10) == []         # < 66ms -> defer
    assert b.drain(70) != []         # faellig

def test_priority_bypasses_rate():
    b = WorldBatcher()
    b.add(mk("orb_update", {"state": "idle"}))
    b.drain(0)
    b.add(mk("gate_alert", {"gate_id": "g", "severity": "critical"}))
    out = b.drain(1)                 # priority sofort
    assert out and out[0].type == "gate_alert"

def test_coalesce_agent_upsert():
    b = WorldBatcher()
    b.add(mk("agent_upsert", {"agent_id": "a", "state": "idle"}))
    b.add(mk("agent_upsert", {"agent_id": "a", "state": "working"}))
    out = b.drain(0)
    assert len(out) == 1 and out[0].payload["state"] == "working"

def test_priority_first_order():
    b = WorldBatcher()
    b.add(mk("agent_upsert", {"agent_id": "a", "state": "idle"}))
    b.add(mk("gate_alert", {"gate_id": "g", "severity": "info"}))
    out = b.drain(0)
    assert out[0].type == "gate_alert"
