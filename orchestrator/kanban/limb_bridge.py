from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.policy import Policy
from core.protocol import Intent, Operations, utc_now_iso
from orchestrator.runner import Orchestrator

def run_limb_request(
    request_file: Path,
    operations: Operations,
    policy: Policy,
    orchestrator: Orchestrator,
    task_id: str,
    active_soul_md: str
) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        if request_file.stat().st_size > 64 * 1024:
            return False, "limb request too large (max 64 KiB)", None
    except OSError:
        return False, "limb request forged or unreadable", None

    try:
        data = json.loads(request_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False, "limb request must be a JSON object", None
    except (OSError, json.JSONDecodeError):
        return False, "limb request forged or unreadable", None

    op = data.get("operation")
    if not op or not isinstance(op, str):
        return False, "missing operation", None

    params = data.get("params", {})
    if not isinstance(params, dict):
        return False, "params must be a JSON object", None

    from orchestrator.kanban.soul import parse_soul
    soul = parse_soul(active_soul_md)
    if soul.frontmatter.get("runtime", "").lower() != "limb":
        return False, "worker soul does not have runtime: limb", None

    if soul.frontmatter.get("limb_operation", "").strip() != op:
        return False, "operation mismatch denied", None

    try:
        spec = operations.spec(op)
    except Exception:
        return False, f"unknown operation {op}", None

    if spec.risk not in ("none", "read", "write"):
        return False, f"high risk denied: {spec.risk}", None

    if len(spec.implemented_by) != 1:
        return False, "operation must be implemented by exactly one limb", None

    intent_data = {
        "protocol": "neu/intent",
        "created_at": utc_now_iso(),
        "version": "1.2",
        "intent_id": f"int_{task_id[-12:].zfill(6)}",
        "source": {"role": "core", "node_id": "kanban"},
        "target": {"limb": spec.implemented_by[0]},
        "job": {"job_id": "job_" + task_id[-12:].zfill(6)},
        "timer": {"mode": "deadline", "deadline_s": 100, "soft_deadline_s": 90},
        "task": {
            "operation": op,
            "params": params
        }
    }

    try:
        intent = Intent.from_dict(intent_data, operations=operations)
    except Exception as e:
        return False, f"invalid intent: {e}", None

    # dispatch blocks and internally runs policy.check
    attempt = orchestrator.dispatch(intent)

    status = attempt.result.status
    payload = attempt.result.to_dict()
    payload["untrusted"] = True

    if status == "success":
        return True, "success", payload
    else:
        return False, status, payload
