"""Welt-Zustand je world_id (live/shadow) — von Adapter-Events UND MCP-Tools
gespeist. D3: getrennte Zustaende, keine Vermischung."""
from __future__ import annotations
from typing import Any
from .events import CityEvent, SeqGen, ORB_STATES


class WorldState:
    def __init__(self, world_id: str) -> None:
        self.world_id = world_id
        self.districts: dict[str, dict] = {}
        self.agents: dict[str, dict] = {}
        self.gates: dict[str, dict] = {}
        self.orb = "idle"
        self.commit_stand = ""
        self.seq = SeqGen()

    def apply(self, ev: CityEvent) -> None:
        p = ev.payload
        t = ev.type
        if t == "agent_upsert":
            self.agents[p["agent_id"]] = p
        elif t == "agent_remove":
            self.agents.pop(p["agent_id"], None)
        elif t == "district_upsert":
            self.districts[p["district_id"]] = p
        elif t == "district_remove":
            self.districts.pop(p["district_id"], None)
        elif t == "gate_alert":
            self.gates[p["gate_id"]] = p
        elif t == "orb_update":
            self.orb = p["state"]
        elif t == "world_snapshot":
            self.agents = {a["agent_id"]: a for a in p.get("agents", [])}
            self.districts = {d["district_id"]: d for d in p.get("districts", [])}
            self.gates = {g["gate_id"]: g for g in p.get("gates", [])}
            self.orb = p.get("orb", {}).get("state", "idle")
            self.commit_stand = p.get("commit_stand", "")

    def _ev(self, type_: str, payload: dict) -> CityEvent:
        return CityEvent(type_, self.world_id, payload, self.seq.next())

    def register_district(self, district_id: str, district_type: str) -> CityEvent:
        return self._ev("district_upsert", {"district_id": district_id, "district_type": district_type})

    def retire_district(self, district_id: str) -> CityEvent:
        return self._ev("district_remove", {"district_id": district_id})

    def set_orb_state(self, state: str) -> CityEvent:
        if state not in ORB_STATES:
            raise ValueError(f"ungueltiger Orb-State: {state}")
        return self._ev("orb_update", {"state": state})

    def raise_gate(self, gate_id: str, severity: str, prompt: str = "") -> CityEvent:
        if severity not in ("info", "warning", "critical"):
            raise ValueError(severity)
        return self._ev("gate_alert", {"gate_id": gate_id, "severity": severity, "prompt": prompt, "source": "mcp"})

    def sync_agent(self, agent_id: str) -> CityEvent:
        a = self.agents.get(agent_id, {"agent_id": agent_id, "state": "idle"})
        return self._ev("agent_upsert", a)


class StateStore:
    def __init__(self) -> None:
        self.worlds = {w: WorldState(w) for w in ("live", "shadow")}

    def get(self, world_id: str) -> WorldState:
        if world_id not in self.worlds:
            raise ValueError(f"unbekannte world_id: {world_id}")
        return self.worlds[world_id]
