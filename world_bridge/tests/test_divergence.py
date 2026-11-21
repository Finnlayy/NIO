import pytest
from world_bridge.adapters import WorldAdapter
from world_bridge.divergence import compute_divergence
from world_bridge.tests.test_adapters import FakeClient

@pytest.mark.anyio
async def test_divergence_event():
    live = WorldAdapter("live","b1","/tmp",FakeClient(workers=[{"uid":"c","status":"idle"}]))
    shadow = WorldAdapter("shadow","b2","/tmp",FakeClient(workers=[{"uid":"c","status":"busy"}]))
    ev = await compute_divergence(live, shadow)
    assert ev.type=="divergence_diff"
    assert ev.payload["entities"][0]["kind"]=="state_diff"
    assert "commit_stand_live" in ev.payload and "commit_stand_shadow" in ev.payload
