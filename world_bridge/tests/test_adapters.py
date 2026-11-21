import pytest
from world_bridge.adapters import WorldAdapter
from world_bridge.events import CityEvent

class FakeClient:
    def __init__(self, workers=None, tasks=None, approvals=None):
        self.workers = workers or []
        self.tasks = tasks or []
        self.approvals = approvals or []
        self.created = []
    async def get_workers(self): return self.workers
    async def get_tasks(self, board_id=None):
        return [t for t in self.tasks if not board_id or t.get("board_id")==board_id]
    async def get_approvals(self): return self.approvals
    async def create_task(self, body): self.created.append(body); return {"id":"t-new",**body}
    async def transition_task(self, tid, target, reason=""): return {"id":tid,"status":target}
    async def resolve_approval(self, gid, action): return {"id":gid,"action":action}

def make_adapter(world="live", client=None):
    return WorldAdapter(world, "b1", "/tmp/nonexistent-repo", client or FakeClient())

@pytest.mark.anyio
async def test_snapshot_shape():
    c = FakeClient(workers=[{"uid":"coder","status":"busy","skills":["code"]}],
                   tasks=[{"id":"t1","status":"in_progress","assigned_worker_uid":"coder","board_id":"b1","title":"X","required_skills":["forge"]}],
                   approvals=[{"id":"g1","severity":"critical","board_id":"b1"}])
    a = make_adapter(client=c)
    snap = await a.snapshot()
    assert set(snap) == {"agents","districts","gates","orb","commit_stand"}
    assert snap["orb"]["state"] == "alert"  # open gate
    assert any(g["gate_id"]=="g1" for g in snap["gates"])
    assert any(d["district_type"]=="gate_outpost" for d in snap["districts"])

@pytest.mark.anyio
async def test_first_poll_is_snapshot():
    a = make_adapter(client=FakeClient(workers=[{"uid":"c","status":"idle"}]))
    evs = await a.poll_events()
    assert len(evs)==1 and evs[0].type=="world_snapshot" and evs[0].seq==1

@pytest.mark.anyio
async def test_diff_emits_upsert_remove():
    c = FakeClient(workers=[{"uid":"c","status":"idle"}])
    a = make_adapter(client=c)
    await a.poll_events()  # snapshot
    c.workers=[{"uid":"c","status":"busy"},{"uid":"d","status":"idle"}]
    evs = await a.poll_events()
    types = [e.type for e in evs]
    assert "agent_upsert" in types
    c.workers=[{"uid":"d","status":"idle"}]
    evs = await a.poll_events()
    assert any(e.type=="agent_remove" and e.payload["agent_id"]=="worker:c" for e in evs)

@pytest.mark.anyio
async def test_world_isolation_board_filter():
    c = FakeClient(tasks=[{"id":"t1","status":"in_progress","assigned_worker_uid":"c","board_id":"OTHER"}])
    a = make_adapter(client=c)  # board b1
    snap = await a.snapshot()
    assert all(ag.get("task_id")!="t1" for ag in snap["agents"])

def test_bad_world_rejected():
    with pytest.raises(ValueError):
        WorldAdapter("bogus","b","/tmp",FakeClient())
