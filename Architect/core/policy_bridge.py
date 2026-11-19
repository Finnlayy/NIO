"""Policy-Brücke Architect → Pre-Execution-Policy (NIO Phase 3).

Riskante Lern- und Selbständerungs-Operationen (Plan-Dispatch, Manifest-Anwendung)
laufen nur mit einem Freigabe-Ticket der PreExecutionPolicyEngine. Schutzaktionen
(Risk-Check, Backup, Rollback, Validierung nach Anwendung) bleiben frei, damit
sich ein fehlerhafter Zustand immer zurücksetzen lässt.

Kopplung: keine Imports aus ``apollo`` oder ``apollo.ciel``. Das Gate wird als
synchrones Callable injiziert (:data:`ActionGate`). Die Übersetzung von der
asynchronen Engine in dieses Callable liegt in der Composition-Root, nicht hier.

Fail-closed: ist kein Gate gesetzt oder wirft es, wird eine riskante Operation
abgelehnt. Nur Operationen mit Tier ``TIER_0_AUTO`` laufen ohne Gate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

TIER_0_AUTO: Final[str] = "TIER_0_AUTO"
TIER_2_APPROVAL: Final[str] = "TIER_2_APPROVAL"

#: Riskant: Plan-Dispatch aus dem Lernsystem.
OP_DISPATCH_PLAN: Final[str] = "learning.dispatch_plan"
#: Riskant: Anwendung eines Änderungs-Manifests auf Dateien.
OP_APPLY_MANIFEST: Final[str] = "self_modification.apply_manifest"
#: Schutz: Risk-Check ist reine Bewertung ohne Seiteneffekt.
OP_RISK_CHECK: Final[str] = "learning.risk_check"
#: Schutz: Backup vor Änderung.
OP_CREATE_BACKUP: Final[str] = "self_modification.create_backup"
#: Schutz: Zurücksetzen auf Backup.
OP_ROLLBACK: Final[str] = "self_modification.rollback"
#: Schutz: Prüfung nach Anwendung.
OP_VALIDATE_AFTER_APPLY: Final[str] = "self_modification.validate_after_apply"

#: Tier-Registry für ``PreExecutionPolicyEngine(tool_tiers=...)``. Werte sind die
#: StrEnum-Werte der Engine, damit kein Import aus ``apollo`` nötig ist.
POLICY_TOOL_TIERS: Final[dict[str, str]] = {
    OP_DISPATCH_PLAN: TIER_2_APPROVAL,
    OP_APPLY_MANIFEST: TIER_2_APPROVAL,
    OP_RISK_CHECK: TIER_0_AUTO,
    OP_CREATE_BACKUP: TIER_0_AUTO,
    OP_ROLLBACK: TIER_0_AUTO,
    OP_VALIDATE_AFTER_APPLY: TIER_0_AUTO,
}

#: Ergebniscodes der Brücke (Teilmenge der Codes der Engine plus Brücken-Fehler).
CODE_OK: Final[str] = "OK"
CODE_WAITING_APPROVAL: Final[str] = "WAITING_APPROVAL"
CODE_NO_GATE: Final[str] = "NO_GATE"
CODE_GATE_ERROR: Final[str] = "GATE_ERROR"
CODE_UNKNOWN_OPERATION: Final[str] = "UNKNOWN_OPERATION"


@dataclass(frozen=True)
class PolicyVerdict:
    """Antwort des injizierten Gates auf eine Operation."""

    allowed: bool
    code: str
    reason: str = ""
    ticket_id: str | None = None


#: ``gate(operation, arguments, approval_ticket_id) -> PolicyVerdict`` (synchron).
ActionGate = Callable[[str, Mapping[str, Any], str | None], PolicyVerdict]


class PolicyBlocked(RuntimeError):
    """Operation abgelehnt; ``code`` und ``reason`` stammen aus dem Gate oder der Brücke."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


class ApprovalRequired(PolicyBlocked):
    """Operation wartet auf Operator-Freigabe; ``ticket_id`` ist für den Retry nötig."""

    def __init__(self, ticket_id: str | None, reason: str) -> None:
        super().__init__(CODE_WAITING_APPROVAL, reason)
        self.ticket_id = ticket_id


class PolicyBridge:
    """Prüft riskante Operationen über ein injiziertes Gate; Schutzaktionen sind frei."""

    def __init__(self, gate: ActionGate | None = None) -> None:
        self._gate = gate

    def require(
        self,
        operation: str,
        arguments: Mapping[str, Any],
        approval_ticket_id: str | None = None,
    ) -> str | None:
        """Gibt die verbrauchte Ticket-ID zurück (oder ``None`` bei freien Operationen).

        Wirft :class:`ApprovalRequired`, wenn ein neues Ticket angelegt wurde oder
        auf Freigabe gewartet wird, und :class:`PolicyBlocked` bei jeder Ablehnung.
        """
        if operation not in POLICY_TOOL_TIERS:
            raise PolicyBlocked(CODE_UNKNOWN_OPERATION, f"Operation {operation!r} ist nicht registriert")
        if POLICY_TOOL_TIERS[operation] == TIER_0_AUTO:
            return None
        if self._gate is None:
            raise PolicyBlocked(CODE_NO_GATE, f"Kein Policy-Gate für riskante Operation {operation!r}")
        try:
            verdict = self._gate(operation, dict(arguments), approval_ticket_id)
        except Exception as exc:  # fail-closed: jeder Gate-Fehler blockiert
            raise PolicyBlocked(CODE_GATE_ERROR, f"Policy-Gate fehlgeschlagen: {exc}") from exc
        if verdict.allowed:
            return verdict.ticket_id or approval_ticket_id
        if verdict.code == CODE_WAITING_APPROVAL:
            raise ApprovalRequired(verdict.ticket_id, verdict.reason)
        raise PolicyBlocked(verdict.code, verdict.reason)


def plan_digest(plan: Any) -> str:
    """SHA-256 des kanonischen Plan-Inhalts; bindet ein Ticket an genau diesen Plan."""
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_digest(path: str | Path) -> str:
    """SHA-256 einer Datei; leerer String, wenn die Datei fehlt."""
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


__all__ = [
    "CODE_GATE_ERROR",
    "CODE_NO_GATE",
    "CODE_OK",
    "CODE_UNKNOWN_OPERATION",
    "CODE_WAITING_APPROVAL",
    "OP_APPLY_MANIFEST",
    "OP_CREATE_BACKUP",
    "OP_DISPATCH_PLAN",
    "OP_RISK_CHECK",
    "OP_ROLLBACK",
    "OP_VALIDATE_AFTER_APPLY",
    "POLICY_TOOL_TIERS",
    "TIER_0_AUTO",
    "TIER_2_APPROVAL",
    "ActionGate",
    "ApprovalRequired",
    "PolicyBlocked",
    "PolicyBridge",
    "PolicyVerdict",
    "file_digest",
    "plan_digest",
]
