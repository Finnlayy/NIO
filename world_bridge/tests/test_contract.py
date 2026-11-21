from world_bridge.spec import load_spec, validate_spec, validate_event
from world_bridge.events import CityEvent
from world_bridge.state import StateStore
from world_bridge import mapping as M

SPEC=load_spec()

def test_spec_valid():
    assert validate_spec(SPEC)==[]

def test_all_event_types_contract():
    samples=[
        M.map_worker({"uid":"c","status":"busy"},"live"),
        M.map_orb({"active_jobs":1},"shadow"),
        M.map_limb_domain("forge","live"),
        M.map_approval({"id":"g","severity":"critical"},"live"),
        M.map_parked_limb({"name":"echo"},"shadow"),
        M.map_divergence({"agents":[]},{"agents":[]},"a","b"),
        CityEvent("district_remove","live",{"district_id":"d"}),
        CityEvent("agent_remove","shadow",{"agent_id":"a"}),
    ]
    for ev in samples:
        assert validate_event(SPEC, ev.to_dict())==[], ev.type

def test_snapshot_contract():
    st=StateStore().get("live")
    snap={"agents":[],"districts":[],"gates":[],"orb":{"state":"idle"},"commit_stand":"abc"}
    ev=CityEvent("world_snapshot","live",snap,1)
    assert validate_event(SPEC, ev.to_dict())==[]

def test_contract_rejects_missing_world_id():
    ev={"type":"orb_update","timestamp_ms":1,"seq":1,"payload":{"state":"idle"}}
    assert validate_event(SPEC, ev)

def test_contract_rejects_bad_state():
    ev=CityEvent("orb_update","live",{"state":"bogus"},1).to_dict()
    assert validate_event(SPEC, ev)

def test_envelope_fields_present():
    ev=CityEvent("gate_alert","live",{"gate_id":"g","severity":"info"},5).to_dict()
    assert {"type","world_id","timestamp_ms","seq","payload"} <= set(ev)
