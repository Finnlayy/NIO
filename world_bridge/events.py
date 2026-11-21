"""City-Event-Modell der World-Bridge (T3/T5). D3: world_id immer dabei."""
from __future__ import annotations
import time
from dataclasses import dataclass, field, asdict
from typing import Any

WORLD_IDS = ("live", "shadow")
EVENT_TYPES = (
    "world_snapshot", "orb_update", "district_upsert", "district_remove",
    "agent_upsert", "agent_remove", "gate_alert", "divergence_diff",
)
ORB_STATES = ("idle", "listening", "dispatching", "alert")
AGENT_STATES = ("idle", "working", "moving", "error", "parked")
SEVERITIES = ("info", "warning", "critical")
PRIORITY_EVENTS = frozenset({"gate_alert"})


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class CityEvent:
    type: str
    world_id: str
    payload: dict[str, Any]
    seq: int = 0
    timestamp_ms: int = field(default_factory=now_ms)

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unbekannter Event-Typ: {self.type}")
        if self.world_id not in WORLD_IDS:
            raise ValueError(f"ungueltige world_id: {self.world_id}")

    @property
    def priority(self) -> bool:
        return self.type in PRIORITY_EVENTS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SeqGen:
    """Monotoner Sequenzgenerator je Welt (Snapshot-Resume)."""
    def __init__(self) -> None:
        self._n = 0
    def next(self) -> int:
        self._n += 1
        return self._n
    @property
    def current(self) -> int:
        return self._n
