"""NEU-Kern (Core): Protokoll, Konfiguration, Policy, Kernel.

Schichtenmodell (Importrichtung ist strikt von unten nach oben):

    core/           Protokoll, Konfiguration, Policy, Kernel  (keine NEU-Importe)
    orchestrator/   Transport, Event-Bus, Runner, CLI         (importiert core)
    limbs/          Limb-Basis + konkrete Limbs               (importiert core)
"""

from __future__ import annotations

from .config import NeuConfig
from .kernel import ACCEPT, NEEDS_CORRECTION, REJECT, Kernel, Verdict
from .policy import Policy, PolicyDecision
from .protocol import (
    PROTOCOL_INTENT,
    PROTOCOL_RESULT,
    PROTOCOL_VERSION,
    Artifact,
    Constraints,
    ErrorCode,
    Elevation,
    Intent,
    Operations,
    ProtocolError,
    Result,
    Task,
    Verification,
    new_id,
    sha256_file,
    sha256_text,
    utc_now_iso,
)

__all__ = [
    "ACCEPT",
    "Artifact",
    "Constraints",
    "ErrorCode",
    "Elevation",
    "Intent",
    "Kernel",
    "NEEDS_CORRECTION",
    "NeuConfig",
    "Operations",
    "PROTOCOL_INTENT",
    "PROTOCOL_RESULT",
    "PROTOCOL_VERSION",
    "Policy",
    "PolicyDecision",
    "ProtocolError",
    "REJECT",
    "Result",
    "Task",
    "Verification",
    "Verdict",
    "new_id",
    "sha256_file",
    "sha256_text",
    "utc_now_iso",
]
