"""divergence_diff live-vs-shadow + Commit-Stand je Welt (U21)."""
from __future__ import annotations
from . import mapping as M
from .adapters import WorldAdapter
from .events import CityEvent


async def compute_divergence(live: WorldAdapter, shadow: WorldAdapter) -> CityEvent:
    ls = await live.snapshot()
    ss = await shadow.snapshot()
    return M.map_divergence(ls, ss, ls.get("commit_stand", ""), ss.get("commit_stand", ""))
