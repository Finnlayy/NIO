"""Batch/Throttle <=15 Hz je Welt + Priority-Lane gate_alert (T7, Nexus-Learnings:
batch_window + lane_split). Koalesziert agent_upsert pro Agent (neuester gewinnt)."""
from __future__ import annotations
from .events import CityEvent

MIN_INTERVAL_MS = 1000.0 / 15.0  # ~66.7 ms


class WorldBatcher:
    def __init__(self, hz: float = 15.0) -> None:
        self._interval = 1000.0 / hz
        self._queue: list[CityEvent] = []
        self._last_flush = -1e9

    def add(self, ev: CityEvent) -> None:
        self._queue.append(ev)

    def pending(self) -> int:
        return len(self._queue)

    def drain(self, now_ms: float) -> list[CityEvent]:
        if not self._queue:
            return []
        has_priority = any(e.priority for e in self._queue)
        if not has_priority and (now_ms - self._last_flush) < self._interval:
            return []  # Rate-Limit: noch nicht faellig
        self._last_flush = now_ms
        # Koaleszieren: agent_upsert/district_upsert/orb_update pro Schluessel neuester
        coalesced: dict[tuple, CityEvent] = {}
        order: list[tuple] = []
        passthrough: list[CityEvent] = []
        for ev in self._queue:
            if ev.type == "agent_upsert":
                key = ("agent", ev.payload["agent_id"])
            elif ev.type == "district_upsert":
                key = ("district", ev.payload["district_id"])
            elif ev.type == "orb_update":
                key = ("orb",)
            else:
                passthrough.append(ev)
                continue
            if key not in coalesced:
                order.append(key)
            coalesced[key] = ev
        out = [coalesced[k] for k in order] + passthrough
        # Priority-Lane: gate_alert zuerst
        out.sort(key=lambda e: 0 if e.priority else 1)
        self._queue = []
        return out
