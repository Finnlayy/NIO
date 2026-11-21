from world_bridge import mapping as M

def test_worker_states():
    assert M.map_worker({"uid": "coder", "status": "busy", "skills": ["code"]}, "live").payload["state"] == "working"
    assert M.map_worker({"uid": "x", "status": "idle"}, "live").payload["state"] == "idle"
    assert M.map_worker({"uid": "x", "status": "disabled"}, "shadow").payload["state"] == "error"

def test_worker_world_id():
    assert M.map_worker({"uid": "x"}, "shadow").world_id == "shadow"

def test_task_in_progress_only():
    assert M.map_task({"status": "blocked", "assigned_worker_uid": "c"}, "live") is None
    assert M.map_task({"status": "in_progress"}, "live") is None
    ev = M.map_task({"status": "in_progress", "assigned_worker_uid": "c", "id": "t1",
                     "title": "Do", "required_skills": ["forge"]}, "live")
    assert ev.payload["state"] == "moving"
    assert ev.payload["target_district"] == "forge"
    assert ev.payload["task_id"] == "t1"

def test_parked_limb():
    ev = M.map_parked_limb({"name": "echo"}, "live")
    assert ev.payload["state"] == "parked"
    assert ev.payload["target_district"] == "tavern_limbs"

def test_approval_severity_default():
    ev = M.map_approval({"id": "g1", "severity": "bogus"}, "live")
    assert ev.type == "gate_alert" and ev.payload["severity"] == "warning"
    assert ev.priority

def test_limb_domain():
    assert M.map_limb_domain("library", "live").payload["district_type"] == "library"
    assert M.map_limb_domain("trading", "live").payload["district_type"] == "trading"
    assert M.map_limb_domain("unknown", "live").payload["district_type"] == "bootstrap"

def test_orb_states():
    assert M.map_orb({"open_gates": 1}, "live").payload["state"] == "alert"
    assert M.map_orb({"active_jobs": 2}, "live").payload["state"] == "dispatching"
    assert M.map_orb({"listening": True}, "live").payload["state"] == "listening"
    assert M.map_orb({}, "live").payload["state"] == "idle"

def test_divergence():
    live = {"agents": [{"agent_id": "a", "state": "idle"}, {"agent_id": "b", "state": "working"}]}
    shadow = {"agents": [{"agent_id": "a", "state": "working"}, {"agent_id": "c", "state": "idle"}]}
    ev = M.map_divergence(live, shadow, "abc", "def")
    kinds = {e["agent_id"]: e["kind"] for e in ev.payload["entities"]}
    assert kinds == {"a": "state_diff", "b": "live_only", "c": "shadow_only"}
    assert ev.payload["commit_stand_live"] == "abc"
