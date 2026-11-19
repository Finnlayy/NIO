"""Tests der Policy-Anbindung (NIO Phase 3): Brücke, RiskGuard-Dispatch, Manifest-Anwendung.

pytest-Stil wie beauftragt. ``unittest discover`` sammelt diese Datei nicht ein;
ausführen mit ``/usr/bin/python3 -m pytest Architect/tests/test_policy_bridge.py``.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.learning.risk_guards import RiskGuardEngine  # noqa: E402
from core.policy_bridge import (  # noqa: E402
    CODE_GATE_ERROR,
    CODE_NO_GATE,
    CODE_UNKNOWN_OPERATION,
    CODE_WAITING_APPROVAL,
    OP_APPLY_MANIFEST,
    OP_CREATE_BACKUP,
    OP_DISPATCH_PLAN,
    OP_RISK_CHECK,
    OP_ROLLBACK,
    OP_VALIDATE_AFTER_APPLY,
    POLICY_TOOL_TIERS,
    TIER_0_AUTO,
    TIER_2_APPROVAL,
    ApprovalRequired,
    PolicyBlocked,
    PolicyBridge,
    PolicyVerdict,
    plan_digest,
)
from core.self_modification_safety import SelfModificationSafety  # noqa: E402

SAFE_PLAN = {
    "plan_id": "plan_safe",
    "risk_parameters": {
        "leverage": 3.0,
        "slippage_bps": 8.0,
        "power_factor": 0.95,
        "vault_ratio": 0.2,
        "in_forbidden_zone": False,
        "feed_live": True,
    },
    "schedule": {"triggers": [{"kind": "interval", "every_s": 30}]},
    "approved_by": "system",
    "file_targets": ["Architect/gui/widgets/command_bar.py"],
    "confidence_score": 0.85,
}


class RecordingGate:
    """Fake-Gate nach dem Vertrag der Composition-Root: zeichnet Aufrufe auf, liefert festes Urteil."""

    def __init__(self, verdict=None, error=None):
        self.verdict = verdict or PolicyVerdict(allowed=True, code="OK", ticket_id="t-1")
        self.error = error
        self.calls = []

    def __call__(self, operation, arguments, approval_ticket_id):
        self.calls.append((operation, dict(arguments), approval_ticket_id))
        if self.error is not None:
            raise self.error
        return self.verdict


# --- Tier-Registry ----------------------------------------------------------


def test_risky_operations_require_approval_tier():
    assert POLICY_TOOL_TIERS[OP_DISPATCH_PLAN] == TIER_2_APPROVAL
    assert POLICY_TOOL_TIERS[OP_APPLY_MANIFEST] == TIER_2_APPROVAL


@pytest.mark.parametrize("op", [OP_RISK_CHECK, OP_CREATE_BACKUP, OP_ROLLBACK, OP_VALIDATE_AFTER_APPLY])
def test_protective_operations_stay_free(op):
    assert POLICY_TOOL_TIERS[op] == TIER_0_AUTO


# --- PolicyBridge -----------------------------------------------------------


def test_protective_operation_skips_gate_entirely():
    gate = RecordingGate()
    assert PolicyBridge(gate).require(OP_ROLLBACK, {"file": "x"}) is None
    assert gate.calls == []


def test_protective_operation_works_without_gate():
    assert PolicyBridge(None).require(OP_CREATE_BACKUP, {}) is None


def test_risky_operation_without_gate_is_blocked():
    with pytest.raises(PolicyBlocked) as exc:
        PolicyBridge(None).require(OP_APPLY_MANIFEST, {})
    assert exc.value.code == CODE_NO_GATE


def test_gate_exception_is_fail_closed():
    with pytest.raises(PolicyBlocked) as exc:
        PolicyBridge(RecordingGate(error=RuntimeError("redis down"))).require(OP_DISPATCH_PLAN, {})
    assert exc.value.code == CODE_GATE_ERROR


def test_waiting_verdict_raises_approval_required_with_ticket():
    gate = RecordingGate(PolicyVerdict(allowed=False, code=CODE_WAITING_APPROVAL, reason="Freigabe", ticket_id="tk-9"))
    with pytest.raises(ApprovalRequired) as exc:
        PolicyBridge(gate).require(OP_DISPATCH_PLAN, {"plan_id": "p"})
    assert exc.value.ticket_id == "tk-9"
    assert exc.value.code == CODE_WAITING_APPROVAL


def test_denial_passes_engine_code_through():
    gate = RecordingGate(PolicyVerdict(allowed=False, code="KILL_SWITCH_ACTIVE", reason="Kill-Switch aktiv"))
    with pytest.raises(PolicyBlocked) as exc:
        PolicyBridge(gate).require(OP_APPLY_MANIFEST, {})
    assert exc.value.code == "KILL_SWITCH_ACTIVE"
    assert not isinstance(exc.value, ApprovalRequired)


def test_allowed_with_ticket_returns_ticket_and_forwards_it():
    gate = RecordingGate(PolicyVerdict(allowed=True, code="OK", ticket_id="tk-7"))
    ticket = PolicyBridge(gate).require(OP_APPLY_MANIFEST, {"manifest_path": "m"}, approval_ticket_id="tk-7")
    assert ticket == "tk-7"
    assert gate.calls == [(OP_APPLY_MANIFEST, {"manifest_path": "m"}, "tk-7")]


def test_unknown_operation_is_blocked_not_defaulted():
    gate = RecordingGate()
    with pytest.raises(PolicyBlocked) as exc:
        PolicyBridge(gate).require("learning.unregistered", {})
    assert exc.value.code == CODE_UNKNOWN_OPERATION
    assert gate.calls == []


def test_plan_digest_is_order_independent_and_content_sensitive():
    assert plan_digest({"plan_id": "p", "leverage": 3}) == plan_digest({"leverage": 3, "plan_id": "p"})
    assert plan_digest({"plan_id": "p", "leverage": 3}) != plan_digest({"plan_id": "p", "leverage": 4})


# --- RiskGuardEngine.authorize_dispatch -------------------------------------


def test_no_gate_blocks_dispatch_of_safe_plan():
    engine = RiskGuardEngine(action_bridge=PolicyBridge(None))
    with pytest.raises(PolicyBlocked) as exc:
        engine.authorize_dispatch(SAFE_PLAN)
    assert exc.value.code == CODE_NO_GATE


def test_safe_plan_waits_for_approval_ticket():
    gate = RecordingGate(PolicyVerdict(allowed=False, code=CODE_WAITING_APPROVAL, ticket_id="tk-plan"))
    engine = RiskGuardEngine(action_bridge=PolicyBridge(gate))
    with pytest.raises(ApprovalRequired) as exc:
        engine.authorize_dispatch(SAFE_PLAN)
    assert exc.value.ticket_id == "tk-plan"
    operation, arguments, ticket = gate.calls[0]
    assert operation == OP_DISPATCH_PLAN
    assert arguments == {"plan_id": "plan_safe", "plan_digest": plan_digest(SAFE_PLAN)}
    assert ticket is None


def test_approved_ticket_allows_dispatch_and_reports_it():
    gate = RecordingGate(PolicyVerdict(allowed=True, code="OK", ticket_id="tk-plan"))
    engine = RiskGuardEngine(action_bridge=PolicyBridge(gate))
    result = engine.authorize_dispatch(SAFE_PLAN, approval_ticket_id="tk-plan")
    assert result["passed"] is True
    assert result["dispatch_ticket_id"] == "tk-plan"
    assert gate.calls[0][2] == "tk-plan"


def test_failed_guard_never_creates_ticket():
    gate = RecordingGate()
    engine = RiskGuardEngine(action_bridge=PolicyBridge(gate))
    bad = dict(SAFE_PLAN, risk_parameters=dict(SAFE_PLAN["risk_parameters"], leverage=9.0))
    result = engine.authorize_dispatch(bad)
    assert result["passed"] is False
    assert "dispatch_ticket_id" not in result
    assert gate.calls == [], "Ein fehlgeschlagener Risk-Check darf kein Ticket anfordern"


def test_ticket_is_bound_to_plan_content():
    gate = RecordingGate(PolicyVerdict(allowed=False, code=CODE_WAITING_APPROVAL, ticket_id="tk"))
    engine = RiskGuardEngine(action_bridge=PolicyBridge(gate))
    with pytest.raises(ApprovalRequired):
        engine.authorize_dispatch(SAFE_PLAN)
    with pytest.raises(ApprovalRequired):
        engine.authorize_dispatch(dict(SAFE_PLAN, confidence_score=0.86))
    assert gate.calls[0][1]["plan_digest"] != gate.calls[1][1]["plan_digest"]


def test_check_itself_stays_free_without_gate():
    engine = RiskGuardEngine(action_bridge=PolicyBridge(None))
    assert engine.check(SAFE_PLAN)["passed"] is True


# --- SelfModificationSafety.apply_modification ------------------------------


@pytest.fixture
def mod_env(tmp_path, monkeypatch):
    target = tmp_path / "target.txt"
    target.write_text("original", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "manifest_version": "1.0",
            "author": "test",
            "timestamp": "2026-11-19T00:00:00Z",
            "changes": [],
            "checksum": "",
            "approval_level": "system",
        }),
        encoding="utf-8",
    )
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    monkeypatch.setattr("core.manifest_validation.validate_manifest_update", lambda *_a, **_k: (True, "ok"))

    def make(bridge):
        safety = SelfModificationSafety(workspace_root=str(tmp_path / "workspace"), action_bridge=bridge)
        safety.backup_dir = backup_dir
        return safety

    return {"target": target, "manifest": manifest, "backup_dir": backup_dir, "make": make}


def test_apply_without_gate_is_blocked_and_changes_nothing(mod_env):
    safety = mod_env["make"](PolicyBridge(None))
    with pytest.raises(PolicyBlocked) as exc:
        safety.apply_modification(str(mod_env["manifest"]))
    assert exc.value.code == CODE_NO_GATE
    assert list(mod_env["backup_dir"].iterdir()) == []


def test_apply_waiting_for_approval_raises_with_ticket(mod_env):
    gate = RecordingGate(PolicyVerdict(allowed=False, code=CODE_WAITING_APPROVAL, ticket_id="tk-mod"))
    safety = mod_env["make"](PolicyBridge(gate))
    with pytest.raises(ApprovalRequired) as exc:
        safety.apply_modification(str(mod_env["manifest"]))
    assert exc.value.ticket_id == "tk-mod"
    operation, arguments, _ = gate.calls[0]
    assert operation == OP_APPLY_MANIFEST
    assert len(arguments["manifest_sha256"]) == 64
    assert list(mod_env["backup_dir"].iterdir()) == []


def test_invalid_manifest_never_reaches_gate(mod_env, monkeypatch):
    monkeypatch.setattr("core.manifest_validation.validate_manifest_update", lambda *_a, **_k: (False, "kaputt"))
    gate = RecordingGate()
    safety = mod_env["make"](PolicyBridge(gate))
    assert safety.apply_modification(str(mod_env["manifest"])) == (False, "kaputt")
    assert gate.calls == []


def test_approved_apply_runs_with_ticket_forwarded(mod_env):
    gate = RecordingGate(PolicyVerdict(allowed=True, code="OK", ticket_id="tk-mod"))
    safety = mod_env["make"](PolicyBridge(gate))
    ok, _message = safety.apply_modification(str(mod_env["manifest"]), approval_ticket_id="tk-mod")
    assert ok is True
    assert gate.calls[0][2] == "tk-mod"


def test_protective_backup_and_rollback_stay_free_without_gate(mod_env):
    safety = mod_env["make"](PolicyBridge(None))
    target = mod_env["target"]
    backup = safety.create_backup(target)
    assert backup is not None
    target.write_text("changed", encoding="utf-8")
    assert safety.rollback(target, backup_file=backup) is True
    assert target.read_text(encoding="utf-8") == "original"
