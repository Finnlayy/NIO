"""Spec-Laden + Validierung (T3/T9 Contract-Test-Grundlage)."""
from __future__ import annotations
import os
from typing import Any
import yaml

SPEC_PATH = os.path.join(os.path.dirname(__file__), "nio_world_api_spec.yaml")


def load_spec(path: str | None = None) -> dict[str, Any]:
    with open(path or SPEC_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_spec(spec: dict[str, Any]) -> list[str]:
    """Strukturelle Validierung; liefert Fehlerliste (leer = gueltig)."""
    errs: list[str] = []
    from .events import EVENT_TYPES, ORB_STATES, WORLD_IDS
    ws = spec.get("ws", {})
    ev = ws.get("events", {})
    for t in EVENT_TYPES:
        if t not in ev:
            errs.append(f"ws.events fehlt: {t}")
    env = ws.get("envelope", {})
    for f in ("type", "world_id", "timestamp_ms", "seq", "payload"):
        if f not in env.get("required", []):
            errs.append(f"envelope.required fehlt: {f}")
    if tuple(env.get("world_id_enum", ())) != WORLD_IDS:
        errs.append("envelope.world_id_enum != (live, shadow)")
    orb = ev.get("orb_update", {}).get("payload", {})
    if tuple(orb.get("state_enum", ())) != ORB_STATES:
        errs.append("orb_update.state_enum falsch")
    if not ev.get("gate_alert", {}).get("priority"):
        errs.append("gate_alert.priority muss true sein")
    cmds = spec.get("rest", {}).get("command", {}).get("commands", {})
    for c in ("dispatch_prompt", "resolve_gate", "promote_limb_or_config"):
        if c not in cmds:
            errs.append(f"rest.command fehlt: {c}")
    tools = spec.get("mcp", {}).get("tools", {})
    for t in ("world_register_district", "world_retire_district", "world_sync_agent",
              "world_set_orb_state", "world_raise_gate"):
        if t not in tools:
            errs.append(f"mcp.tools fehlt: {t}")
    if spec.get("service", {}).get("batch_hz_max", 0) > 15:
        errs.append("batch_hz_max > 15")
    return errs


def validate_event(spec: dict, ev: dict) -> list[str]:
    """Contract-Test: Event-Dict gegen Spec-Envelope + Payload-Required."""
    errs: list[str] = []
    env = spec.get("ws", {}).get("envelope", {})
    for f in env.get("required", []):
        if f not in ev:
            errs.append(f"envelope fehlt: {f}")
    if ev.get("world_id") not in env.get("world_id_enum", []):
        errs.append("world_id ungueltig")
    t = ev.get("type")
    evspec = spec.get("ws", {}).get("events", {}).get(t)
    if evspec is None:
        errs.append(f"unbekannter Typ: {t}")
        return errs
    payload = ev.get("payload", {})
    for f in evspec.get("payload", {}).get("required", []):
        if f not in payload:
            errs.append(f"{t}.payload fehlt: {f}")
    se = evspec.get("payload", {}).get("state_enum")
    if se and payload.get("state") not in se:
        errs.append(f"{t}.state nicht in enum")
    sev = evspec.get("payload", {}).get("severity_enum")
    if sev and payload.get("severity") not in sev:
        errs.append(f"{t}.severity nicht in enum")
    return errs
