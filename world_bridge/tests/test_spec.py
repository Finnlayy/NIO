from world_bridge.spec import load_spec, validate_spec
from world_bridge.events import EVENT_TYPES, CityEvent, SeqGen
import pytest

def test_spec_valid():
    assert validate_spec(load_spec()) == []

def test_all_event_types_in_spec():
    ev = load_spec()["ws"]["events"]
    assert set(EVENT_TYPES) <= set(ev)

def test_event_rejects_bad_world():
    with pytest.raises(ValueError):
        CityEvent("orb_update", "bogus", {"state": "idle"})

def test_event_rejects_bad_type():
    with pytest.raises(ValueError):
        CityEvent("nope", "live", {})

def test_priority_gate_alert():
    assert CityEvent("gate_alert", "live", {"gate_id": "g", "severity": "info"}).priority
    assert not CityEvent("orb_update", "live", {"state": "idle"}).priority

def test_seq_monotonic():
    s = SeqGen()
    assert [s.next() for _ in range(3)] == [1, 2, 3]
    assert s.current == 3
