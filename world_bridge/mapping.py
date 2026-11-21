"""State-Mapping-Transformer NIO-Entity -> Stadt-Event (T5, Plan Tabelle 3).

Reine Funktionen, keine Seiteneffekte, gut testbar. 7 Entity-Arten:
Worker, Task(in_progress), parked limb, Approval-Ticket, Limb-Domaene,
Orb-Zustand, Live/Shadow-Delta.
"""
from __future__ import annotations
from typing import Any
from .events import CityEvent

# Limb-Domaene -> district_type (Plan: trading/forge=bootstrap, library=vault, tavern)
_DOMAIN_DISTRICT = {
    "bootstrap": "bootstrap", "forge": "forge", "trading": "trading",
    "library": "library", "vault": "vault", "tavern": "tavern",
}
_WORKER_STATE = {"idle": "idle", "busy": "working", "disabled": "error"}


def _district_for_skills(skills: list[str] | tuple[str, ...] | None) -> str:
    for s in skills or ():
        if s in _DOMAIN_DISTRICT:
            return _DOMAIN_DISTRICT[s]
    return "bootstrap"


def map_worker(worker: dict[str, Any], world_id: str) -> CityEvent:
    uid = worker.get("uid") or worker.get("id") or "unknown"
    state = _WORKER_STATE.get(str(worker.get("status", "idle")), "idle")
    return CityEvent("agent_upsert", world_id, {
        "agent_id": f"worker:{uid}", "state": state, "worker_uid": uid,
        "kind": "worker", "skills": list(worker.get("skills") or []),
        "target_district": _district_for_skills(worker.get("skills")),
    })


def map_task(task: dict[str, Any], world_id: str) -> CityEvent | None:
    if task.get("status") != "in_progress":
        return None
    worker = task.get("assigned_worker_uid")
    if not worker:
        return None
    return CityEvent("agent_upsert", world_id, {
        "agent_id": f"worker:{worker}", "state": "moving", "worker_uid": worker,
        "kind": "worker", "task_id": task.get("id"),
        "task_summary": (task.get("title") or "")[:120],
        "target_district": _district_for_skills(task.get("required_skills")),
    })


def map_parked_limb(limb: dict[str, Any], world_id: str) -> CityEvent:
    name = limb.get("name") or limb.get("id") or "limb"
    return CityEvent("agent_upsert", world_id, {
        "agent_id": f"limb:{name}", "state": "parked", "kind": "parked_limb",
        "target_district": "tavern_limbs",
    })


def map_approval(ticket: dict[str, Any], world_id: str) -> CityEvent:
    gid = ticket.get("id") or ticket.get("gate_id") or "gate"
    sev = ticket.get("severity") or "warning"
    if sev not in ("info", "warning", "critical"):
        sev = "warning"
    tool = ticket.get("tool") or ""
    reason = ticket.get("reason") or ""
    prompt = ticket.get("prompt") or (f"{tool}: {reason}".strip(": ") if tool or reason else "")
    return CityEvent("gate_alert", world_id, {
        "gate_id": str(gid), "severity": sev, "prompt": prompt,
        "diff": ticket.get("diff"), "board_id": ticket.get("board_id") or ticket.get("session_id"),
        "source": "kanban",
    })


def map_limb_domain(domain: str, world_id: str, district_id: str | None = None) -> CityEvent:
    dtype = _DOMAIN_DISTRICT.get(domain, "bootstrap")
    return CityEvent("district_upsert", world_id, {
        "district_id": district_id or f"district:{domain}", "district_type": dtype,
    })


def map_orb(orchestrator_status: dict[str, Any], world_id: str) -> CityEvent:
    jobs = int(orchestrator_status.get("active_jobs") or 0)
    gates = int(orchestrator_status.get("open_gates") or 0)
    listening = bool(orchestrator_status.get("listening"))
    if gates > 0:
        state = "alert"
    elif jobs > 0:
        state = "dispatching"
    elif listening:
        state = "listening"
    else:
        state = "idle"
    return CityEvent("orb_update", world_id, {"state": state})


def map_divergence(live_snap: dict[str, Any], shadow_snap: dict[str, Any],
                   commit_live: str, commit_shadow: str) -> CityEvent:
    """Vergleicht Welt-Snapshots ueber gleiche Entity-IDs -> divergence_diff.

    Wird je Welt emittiert (live und shadow erhalten dasselbe Delta-Event).
    """
    def index(snap: dict[str, Any]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for a in snap.get("agents", []):
            out[a.get("agent_id", "")] = a
        return out
    li, si = index(live_snap), index(shadow_snap)
    entities = []
    for key in sorted(set(li) | set(si)):
        l, s = li.get(key), si.get(key)
        if l is None:
            entities.append({"agent_id": key, "kind": "shadow_only"})
        elif s is None:
            entities.append({"agent_id": key, "kind": "live_only"})
        elif l.get("state") != s.get("state"):
            entities.append({"agent_id": key, "kind": "state_diff",
                             "live": l.get("state"), "shadow": s.get("state")})
    return CityEvent("divergence_diff", "live", {
        "entities": entities,
        "commit_stand_live": commit_live, "commit_stand_shadow": commit_shadow,
    })
