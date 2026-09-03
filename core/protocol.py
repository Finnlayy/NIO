"""NEU-Kommunikationsprotokoll v1.1 -- ausfuehrbare Referenzimplementierung.

Dieses Modul ist die *massgebliche* Implementierung des Protokolls. Die
JSON-Schema-Dateien unter ``protocol/`` spiegeln denselben Stand und dienen
externen Werkzeugen (Editoren, CI, zukuenftige TS-Limbs).

Zwei Envelopes:

``neu/intent``  Core -> Orchestrator -> Limb   (Auftrag, strikt isoliert)
``neu/result``  Limb -> Orchestrator -> Core   (Ergebnis, immer genau eines)

**Neu in 1.1 (Timer- und Iterations-Semantik):**

* ``intent.job``    -- Job-Identitaet. Iterationen zaehlen pro **Job**, nicht
  pro Agentenaufruf. Ein Job bleibt ueber alle Durchgaenge dieselbe Spur.
* ``intent.timer``  -- wird vom Orchestrator **vor Anbeginn** der Ausfuehrung
  scharf geschaltet (``armed_at``/``expires_at``/``soft_expires_at``). Der Limb
  kennt damit seine absolute Deadline und muss bei Ablauf einen klaren
  Statusbericht liefern.
* ``result.status`` -- zusaetzlicher Status ``timeout``.
* ``result.status_report`` -- Pflicht bei ``timeout``/``partial``: erklaert,
  was fertig ist, was fehlt und warum es in diesem Durchgang nicht ging.
* ``retry_policy`` entfaellt: Es gibt kein stilles Retry mehr. Ein Fehlschlag
  fuehrt in den autodidaktischen Modus (neuer Durchgang mit neu entworfenem
  Auftrag) oder -- wenn keine Massnahme mehr moeglich ist -- in ``failed``.

Designregeln:
* Ein Intent traegt *alle* Informationen, die der Limb braucht. Der Limb hat
  keinen Zugriff auf Chat-Historie, Gedankengaenge oder andere Intents.
* Unbekannte Schluessel auf Envelope-Ebene sind Fehler (Drift-Frueherkennung).
  Frei erweitert werden duerfen nur ``task.params``, ``context.extra`` und
  ``result.output``.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .config import ABSOLUTE_MAX_ITERATIONS, HARD_DEADLINE_S

PROTOCOL_INTENT = "neu/intent"
PROTOCOL_RESULT = "neu/result"
PROTOCOL_MAJOR = 1
PROTOCOL_MINOR = 1
PROTOCOL_VERSION = f"{PROTOCOL_MAJOR}.{PROTOCOL_MINOR}"

_ID_RE = re.compile(r"^(int|res|trc|job)_[A-Za-z0-9_-]{6,64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LIMB_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_LIMB_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
_OPERATION_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_REL_PATH_RE = re.compile(r"^(?!/)[^\x00]*$")

VALID_SOURCE_ROLES = ("core", "orchestrator", "limb", "human")
VALID_ELEVATION_LEVELS = ("none", "workspace", "repo_write")
VALID_RESULT_STATUSES = ("success", "failed", "rejected", "partial", "timeout")
VALID_VERIFICATION_TYPES = ("none", "file_exists", "hash", "unittest", "pytest", "shell")
VALID_ARTIFACT_ACTIONS = ("created", "modified", "deleted", "read", "unchanged")
VALID_ON_FAILURE = ("autodidactic", "return_to_core", "abort")
VALID_ON_EXPIRY = ("iterate", "escalate", "abort")
VALID_REPORT_STATES = ("completed", "partial", "blocked", "timeout")


class ErrorCode:
    """Fehlerklassifikation -- Kern, Orchestrator und Limb sprechen dieselben Codes."""

    SCHEMA_INVALID = "E_SCHEMA_INVALID"
    UNSUPPORTED_OP = "E_UNSUPPORTED_OP"
    SANDBOX_ESCAPE = "E_SANDBOX_ESCAPE"
    POLICY_DENIED = "E_POLICY_DENIED"
    TARGET_NOT_FOUND = "E_TARGET_NOT_FOUND"
    PATH_NOT_FOUND = "E_PATH_NOT_FOUND"
    ALREADY_EXISTS = "E_ALREADY_EXISTS"
    PATCH_NO_MATCH = "E_PATCH_NO_MATCH"
    TIMEOUT = "E_TIMEOUT"
    DEADLINE_EXCEEDED = "E_DEADLINE_EXCEEDED"
    BUDGET_EXHAUSTED = "E_BUDGET_EXHAUSTED"
    SHELL_BLOCKED = "E_SHELL_BLOCKED"
    IO = "E_IO"
    LIMB_CRASH = "E_LIMB_CRASH"
    INTERNAL = "E_INTERNAL"

    ALL = (
        SCHEMA_INVALID,
        UNSUPPORTED_OP,
        SANDBOX_ESCAPE,
        POLICY_DENIED,
        TARGET_NOT_FOUND,
        PATH_NOT_FOUND,
        ALREADY_EXISTS,
        PATCH_NO_MATCH,
        TIMEOUT,
        DEADLINE_EXCEEDED,
        BUDGET_EXHAUSTED,
        SHELL_BLOCKED,
        IO,
        LIMB_CRASH,
        INTERNAL,
    )


class ProtocolError(ValueError):
    """Struktur- oder Inhaltsfehler eines Envelopes."""

    def __init__(self, code: str, message: str, path: str = "$") -> None:
        self.code = code
        self.message = message
        self.path = path
        super().__init__(f"[{code}] {path}: {message}")

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "path": self.path}


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """ISO-8601-Zeitstempel in UTC mit Millisekunden, z. B. 2026-09-03T12:00:00.123Z."""
    return utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def format_timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str, *, when: datetime | None = None, rng: Callable[[], int] | None = None) -> str:
    """Erzeugt ``int_20260903T120000Z_a1b2c3``-artige, sortierbare IDs."""
    if prefix not in {"int", "res", "trc", "job"}:
        raise ProtocolError(ErrorCode.INTERNAL, f"unbekannter ID-Praefix '{prefix}'")
    moment = when or utc_now()
    stamp = moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = format((rng() if rng else uuid.uuid4().int) % 0xFFFFFF, "06x")
    return f"{prefix}_{stamp}_{suffix}"


def parse_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, "Zeitstempel muss ein String sein", path)
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"kein ISO-8601-Zeitstempel: {value!r}", path) from exc
    if parsed.tzinfo is None:
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, "Zeitstempel muss eine Zeitzone tragen (UTC/Z)", path)
    return parsed.astimezone(timezone.utc)


def _optional_timestamp(value: Any, path: str) -> str | None:
    if value in (None, ""):
        return None
    return format_timestamp(parse_timestamp(value, path))


def sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Primitive Validierer
# --------------------------------------------------------------------------- #
def _req(data: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in data:
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"Pflichtfeld '{key}' fehlt", f"{path}.{key}")
    return data[key]


def _opt(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    value = data.get(key, default)
    return default if value is None else value


def _as_str(value: Any, path: str, *, min_len: int = 1, max_len: int = 8192, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"erwartet String, gefunden {type(value).__name__}", path)
    if not (min_len <= len(value) <= max_len):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"Laenge {len(value)} ausserhalb [{min_len},{max_len}]", path)
    if pattern is not None and not pattern.match(value):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"Format verletzt Muster {pattern.pattern!r}: {value!r}", path)
    return value


def _as_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"erwartet bool, gefunden {type(value).__name__}", path)
    return value


def _as_number(value: Any, path: str, *, minimum: float, maximum: float, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, "erwartet Zahl", path)
    if integer and not isinstance(value, int):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, "erwartet Ganzzahl", path)
    if not (minimum <= value <= maximum):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"Wert {value} ausserhalb [{minimum},{maximum}]", path)
    return value


def _as_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"erwartet Objekt, gefunden {type(value).__name__}", path)
    return dict(value)


def _as_str_list(value: Any, path: str, *, max_items: int = 64, max_len: int = 2048) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, "erwartet Liste von Strings", path)
    if len(value) > max_items:
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"mehr als {max_items} Eintraege", path)
    return tuple(_as_str(item, f"{path}[{i}]", max_len=max_len) for i, item in enumerate(value))


def _as_enum(value: Any, path: str, allowed: Sequence[str]) -> str:
    text = _as_str(value, path, max_len=64)
    if text not in allowed:
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"'{text}' nicht in {list(allowed)}", path)
    return text


def _as_rel_path(value: Any, path: str) -> str:
    text = _as_str(value, path, max_len=1024)
    if not _REL_PATH_RE.match(text):
        raise ProtocolError(ErrorCode.SANDBOX_ESCAPE, "absolute Pfade sind verboten (nur relativ zum Sandbox-Root)", path)
    return text.strip()


def _reject_unknown(data: Mapping[str, Any], allowed: Sequence[str], path: str) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"unbekannte Schluessel {unknown} (Protokoll {PROTOCOL_VERSION} ist strikt)",
            path,
        )


def _check_version(value: Any, path: str) -> None:
    text = _as_str(value, path, max_len=16, pattern=re.compile(r"^\d+\.\d+$"))
    major, minor = (int(part) for part in text.split("."))
    if major != PROTOCOL_MAJOR:
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"Inkompatible Protokoll-Major-Version {major} (erwartet {PROTOCOL_MAJOR})", path)
    if minor > PROTOCOL_MINOR:
        raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"Protokoll {text} ist neuer als vom Core unterstuetzt ({PROTOCOL_VERSION})", path)


# --------------------------------------------------------------------------- #
# Operations-Register
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class OperationSpec:
    name: str
    phase: int
    risk: str
    requires_elevation: str
    params: dict[str, Any]
    implemented_by: tuple[str, ...]
    path_params: tuple[str, ...] = ()
    description: str = ""

    @property
    def family(self) -> str:
        return self.name.split(".", 1)[0]

    @property
    def writes(self) -> bool:
        return self.risk in {"write", "high", "destructive"}


class Operations:
    """Liest ``protocol/operations.json`` -- das normative Operations-Register."""

    def __init__(self, specs: Mapping[str, OperationSpec]) -> None:
        self._specs = dict(specs)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Operations":
        registry = Path(path) if path else Path(__file__).resolve().parent.parent / "protocol" / "operations.json"
        if not registry.is_file():
            raise ProtocolError(ErrorCode.INTERNAL, f"Operations-Register nicht gefunden: {registry}")
        raw = json.loads(registry.read_text(encoding="utf-8"))
        entries = _as_dict(_req(raw, "operations", "$"), "$.operations")
        specs: dict[str, OperationSpec] = {}
        for name, body in entries.items():
            body = _as_dict(body, f"$.operations.{name}")
            specs[name] = OperationSpec(
                name=name,
                phase=int(body.get("phase", 1)),
                risk=_as_str(body.get("risk", "unknown"), f"$.operations.{name}.risk", max_len=32),
                requires_elevation=_as_str(body.get("requires_elevation", "none"), f"$.operations.{name}.requires_elevation", max_len=32),
                params=_as_dict(body.get("params", {}), f"$.operations.{name}.params"),
                implemented_by=tuple(str(x) for x in body.get("implemented_by", ())),
                path_params=tuple(str(x) for x in body.get("path_params", ())),
                description=str(body.get("description", "")),
            )
        return cls(specs)

    def known(self, name: str) -> bool:
        return name in self._specs

    def spec(self, name: str) -> OperationSpec:
        if name not in self._specs:
            raise ProtocolError(ErrorCode.UNSUPPORTED_OP, f"Operation '{name}' ist nicht im Register", "$.task.operation")
        return self._specs[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def as_dict(self) -> dict[str, Any]:
        return {
            name: {
                "phase": spec.phase,
                "risk": spec.risk,
                "requires_elevation": spec.requires_elevation,
                "implemented_by": list(spec.implemented_by),
                "path_params": list(spec.path_params),
                "description": spec.description,
                "params": spec.params,
            }
            for name, spec in sorted(self._specs.items())
        }


# --------------------------------------------------------------------------- #
# Intent-Bausteine
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Constraints:
    sandbox_root: str = "workspace"
    allow_shell: bool = False
    allow_network: bool = False
    max_output_bytes: int = 1_048_576
    dry_run: bool = False
    backup: bool = True

    ALLOWED_KEYS = ("sandbox_root", "allow_shell", "allow_network", "max_output_bytes", "dry_run", "backup")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandbox_root": self.sandbox_root,
            "allow_shell": self.allow_shell,
            "allow_network": self.allow_network,
            "max_output_bytes": self.max_output_bytes,
            "dry_run": self.dry_run,
            "backup": self.backup,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, path: str = "$.constraints") -> "Constraints":
        if data is None:
            return cls()
        body = _as_dict(data, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        return cls(
            sandbox_root=_as_rel_path(_opt(body, "sandbox_root", "workspace"), f"{path}.sandbox_root"),
            allow_shell=_as_bool(_opt(body, "allow_shell", False), f"{path}.allow_shell"),
            allow_network=_as_bool(_opt(body, "allow_network", False), f"{path}.allow_network"),
            max_output_bytes=int(
                _as_number(
                    _opt(body, "max_output_bytes", 1_048_576),
                    f"{path}.max_output_bytes",
                    minimum=1,
                    maximum=67_108_864,
                    integer=True,
                )
            ),
            dry_run=_as_bool(_opt(body, "dry_run", False), f"{path}.dry_run"),
            backup=_as_bool(_opt(body, "backup", True), f"{path}.backup"),
        )


@dataclass(frozen=True)
class Elevation:
    """Rechteanhebung fuer Selbstmodifikation (Ouroboros-Phasen)."""

    level: str = "none"
    reason: str = ""
    approved_by: str = ""
    requested_paths: tuple[str, ...] = ()

    ALLOWED_KEYS = ("level", "reason", "approved_by", "requested_paths")
    MIN_REASON_LEN = 20

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "requested_paths": list(self.requested_paths),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, path: str = "$.elevation") -> "Elevation":
        if data is None:
            return cls()
        body = _as_dict(data, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        level = _as_enum(_opt(body, "level", "none"), f"{path}.level", VALID_ELEVATION_LEVELS)
        reason = _as_str(_opt(body, "reason", ""), f"{path}.reason", min_len=0, max_len=2048)
        approved_by = _as_str(_opt(body, "approved_by", ""), f"{path}.approved_by", min_len=0, max_len=64)
        requested = _as_str_list(_opt(body, "requested_paths", ()), f"{path}.requested_paths")

        if level != "none":
            if len(reason.strip()) < cls.MIN_REASON_LEN:
                raise ProtocolError(
                    ErrorCode.SCHEMA_INVALID,
                    f"Elevation '{level}' braucht eine Begruendung (>= {cls.MIN_REASON_LEN} Zeichen)",
                    f"{path}.reason",
                )
            if approved_by not in {"core", "human"}:
                raise ProtocolError(
                    ErrorCode.SCHEMA_INVALID,
                    "elevation.approved_by muss 'core' oder 'human' sein",
                    f"{path}.approved_by",
                )
            for item in requested:
                _as_rel_path(item, f"{path}.requested_paths")
        return cls(level=level, reason=reason, approved_by=approved_by, requested_paths=requested)


@dataclass(frozen=True)
class Verification:
    """Wie der Core den Erfolg maschinell nachpruefen kann."""

    type: str = "none"
    command: str = ""
    expect: dict[str, Any] = field(default_factory=dict)

    ALLOWED_KEYS = ("type", "command", "expect")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "command": self.command, "expect": dict(self.expect)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, path: str = "$.task.verification") -> "Verification | None":
        if data is None:
            return None
        body = _as_dict(data, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        vtype = _as_enum(_opt(body, "type", "none"), f"{path}.type", VALID_VERIFICATION_TYPES)
        command = _as_str(_opt(body, "command", ""), f"{path}.command", min_len=0, max_len=4096)
        if vtype in {"pytest", "unittest", "shell"} and not command.strip():
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"verification.type '{vtype}' braucht ein Kommando", f"{path}.command")
        return cls(type=vtype, command=command, expect=_as_dict(_opt(body, "expect", {}), f"{path}.expect"))


@dataclass(frozen=True)
class Task:
    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    objective: str = ""
    acceptance: tuple[str, ...] = ()
    verification: Verification | None = None

    ALLOWED_KEYS = ("operation", "params", "title", "objective", "acceptance", "verification")

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "operation": self.operation,
            "params": dict(self.params),
            "title": self.title,
            "objective": self.objective,
            "acceptance": list(self.acceptance),
        }
        if self.verification is not None:
            body["verification"] = self.verification.to_dict()
        return body

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, operations: Operations | None = None, path: str = "$.task") -> "Task":
        body = _as_dict(data, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        operation = _as_str(_req(body, "operation", path), f"{path}.operation", max_len=64, pattern=_OPERATION_RE)
        if operations is not None and not operations.known(operation):
            raise ProtocolError(ErrorCode.UNSUPPORTED_OP, f"Operation '{operation}' ist nicht im Register", f"{path}.operation")
        params = _as_dict(_opt(body, "params", {}), f"{path}.params")
        return cls(
            operation=operation,
            params=params,
            title=_as_str(_opt(body, "title", ""), f"{path}.title", min_len=0, max_len=256),
            objective=_as_str(_opt(body, "objective", ""), f"{path}.objective", min_len=0, max_len=8192),
            acceptance=_as_str_list(_opt(body, "acceptance", ()), f"{path}.acceptance"),
            verification=Verification.from_dict(body.get("verification"), f"{path}.verification"),
        )


@dataclass(frozen=True)
class Job:
    """Job-Identitaet ueber alle Durchgaenge. Iterationen zaehlen pro Job."""

    job_id: str
    goal: str = ""
    iteration: int = 1
    max_iterations: int = 1
    on_failure: str = "autodidactic"

    ALLOWED_KEYS = ("job_id", "goal", "iteration", "max_iterations", "on_failure")

    @property
    def iterations_left(self) -> int:
        return max(0, self.max_iterations - self.iteration)

    @property
    def may_iterate(self) -> bool:
        return self.iteration < self.max_iterations

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "goal": self.goal,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "on_failure": self.on_failure,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, path: str = "$.job") -> "Job":
        body = _as_dict(data if data is not None else {}, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        job_id = _as_str(_req(body, "job_id", path), f"{path}.job_id", max_len=80, pattern=_ID_RE)
        max_iterations = int(
            _as_number(_opt(body, "max_iterations", 1), f"{path}.max_iterations", minimum=1, maximum=ABSOLUTE_MAX_ITERATIONS, integer=True)
        )
        iteration = int(_as_number(_opt(body, "iteration", 1), f"{path}.iteration", minimum=1, maximum=ABSOLUTE_MAX_ITERATIONS, integer=True))
        if iteration > max_iterations:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"iteration {iteration} ist groesser als max_iterations {max_iterations}",
                f"{path}.iteration",
            )
        return cls(
            job_id=job_id,
            goal=_as_str(_opt(body, "goal", ""), f"{path}.goal", min_len=0, max_len=4096),
            iteration=iteration,
            max_iterations=max_iterations,
            on_failure=_as_enum(_opt(body, "on_failure", "autodidactic"), f"{path}.on_failure", VALID_ON_FAILURE),
        )


@dataclass(frozen=True)
class Timer:
    """Timer, der **vor Anbeginn** der Ausfuehrung vom Orchestrator geschaerft wird.

    ``deadline_s``       hartes Budget dieses Durchgangs (Orchestrator killt danach)
    ``soft_deadline_s``  weiche Marke: hier muss der Limb einen Statusbericht liefern
    ``grace_s``          Nachfrist zwischen Soft-Report und hartem Kill
    """

    deadline_s: float = 60.0
    soft_deadline_s: float = 45.0
    grace_s: float = 5.0
    on_expiry: str = "iterate"
    armed_at: str | None = None
    soft_expires_at: str | None = None
    expires_at: str | None = None

    ALLOWED_KEYS = ("deadline_s", "soft_deadline_s", "grace_s", "on_expiry", "armed_at", "soft_expires_at", "expires_at")

    @property
    def armed(self) -> bool:
        return bool(self.armed_at and self.expires_at)

    def arm(self, *, now: datetime | None = None) -> "Timer":
        """Schaerft den Timer. Wird vom Orchestrator vor dem Start des Limbs aufgerufen."""
        moment = now or utc_now()
        return replace(
            self,
            armed_at=format_timestamp(moment),
            soft_expires_at=format_timestamp(moment + timedelta(seconds=self.soft_deadline_s)),
            expires_at=format_timestamp(moment + timedelta(seconds=self.deadline_s)),
        )

    def remaining_s(self, *, now: datetime | None = None) -> float | None:
        if not self.expires_at:
            return None
        moment = now or utc_now()
        return (parse_timestamp(self.expires_at, "$.timer.expires_at") - moment).total_seconds()

    def soft_remaining_s(self, *, now: datetime | None = None) -> float | None:
        if not self.soft_expires_at:
            return None
        moment = now or utc_now()
        return (parse_timestamp(self.soft_expires_at, "$.timer.soft_expires_at") - moment).total_seconds()

    def hard_timeout_s(self) -> float:
        """Wann der Orchestrator den Subprozess spaetestens abbricht."""
        return min(HARD_DEADLINE_S, self.deadline_s + self.grace_s)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deadline_s": self.deadline_s,
            "soft_deadline_s": self.soft_deadline_s,
            "grace_s": self.grace_s,
            "on_expiry": self.on_expiry,
            "armed_at": self.armed_at,
            "soft_expires_at": self.soft_expires_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, path: str = "$.timer") -> "Timer":
        body = _as_dict(data if data is not None else {}, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        deadline = float(_as_number(_opt(body, "deadline_s", 60.0), f"{path}.deadline_s", minimum=0.1, maximum=HARD_DEADLINE_S))
        soft = float(_as_number(_opt(body, "soft_deadline_s", min(45.0, deadline)), f"{path}.soft_deadline_s", minimum=0.1, maximum=HARD_DEADLINE_S))
        if soft > deadline:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"soft_deadline_s ({soft}) darf nicht ueber deadline_s ({deadline}) liegen", f"{path}.soft_deadline_s")
        grace = float(_as_number(_opt(body, "grace_s", 5.0), f"{path}.grace_s", minimum=0.0, maximum=120.0))
        return cls(
            deadline_s=deadline,
            soft_deadline_s=soft,
            grace_s=grace,
            on_expiry=_as_enum(_opt(body, "on_expiry", "iterate"), f"{path}.on_expiry", VALID_ON_EXPIRY),
            armed_at=_optional_timestamp(body.get("armed_at"), f"{path}.armed_at"),
            soft_expires_at=_optional_timestamp(body.get("soft_expires_at"), f"{path}.soft_expires_at"),
            expires_at=_optional_timestamp(body.get("expires_at"), f"{path}.expires_at"),
        )


@dataclass(frozen=True)
class Intent:
    """Auftrag des KI-Kerns an einen Limb (ein Durchgang eines Jobs)."""

    intent_id: str
    operation: str  # Duplikat von task.operation fuer schnelle Filter -- bewusst redundant
    task: Task
    target_limb: str
    created_at: str
    job: Job
    timer: Timer
    trace_id: str = ""
    parent_intent_id: str | None = None
    idempotency_key: str = ""
    source_role: str = "core"
    source_node: str = "core.kernel"
    target_version: str = ""
    constraints: Constraints = field(default_factory=Constraints)
    elevation: Elevation = field(default_factory=Elevation)
    context_summary: str = ""
    context_artifacts: tuple[dict[str, Any], ...] = ()
    context_extra: dict[str, Any] = field(default_factory=dict)

    ALLOWED_KEYS = (
        "protocol",
        "version",
        "intent_id",
        "trace_id",
        "parent_intent_id",
        "idempotency_key",
        "created_at",
        "source",
        "target",
        "job",
        "timer",
        "task",
        "constraints",
        "elevation",
        "context",
    )

    @property
    def job_id(self) -> str:
        return self.job.job_id

    @property
    def iteration(self) -> int:
        return self.job.iteration

    @property
    def is_correction(self) -> bool:
        return self.parent_intent_id is not None or self.job.iteration > 1

    # ---------------------------------------------------------- Serialisierung
    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_INTENT,
            "version": PROTOCOL_VERSION,
            "intent_id": self.intent_id,
            "trace_id": self.trace_id or self.job.job_id,
            "parent_intent_id": self.parent_intent_id,
            "idempotency_key": self.idempotency_key or self.intent_id,
            "created_at": self.created_at,
            "source": {"role": self.source_role, "node_id": self.source_node},
            "target": {"limb": self.target_limb, "version": self.target_version or None},
            "job": self.job.to_dict(),
            "timer": self.timer.to_dict(),
            "task": self.task.to_dict(),
            "constraints": self.constraints.to_dict(),
            "elevation": self.elevation.to_dict(),
            "context": {
                "summary": self.context_summary,
                "artifacts": [dict(a) for a in self.context_artifacts],
                "extra": dict(self.context_extra),
            },
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, operations: Operations | None = None) -> "Intent":
        body = _as_dict(data, "$")
        _reject_unknown(body, cls.ALLOWED_KEYS, "$")

        if _as_str(_req(body, "protocol", "$"), "$.protocol", max_len=32) != PROTOCOL_INTENT:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"protocol muss '{PROTOCOL_INTENT}' sein", "$.protocol")
        _check_version(_req(body, "version", "$"), "$.version")

        intent_id = _as_str(_req(body, "intent_id", "$"), "$.intent_id", max_len=80, pattern=_ID_RE)
        parent = body.get("parent_intent_id")
        parent_intent_id = None if parent is None else _as_str(parent, "$.parent_intent_id", max_len=80, pattern=_ID_RE)
        created = parse_timestamp(_req(body, "created_at", "$"), "$.created_at")

        job = Job.from_dict(_req(body, "job", "$"))
        trace_id = _as_str(_opt(body, "trace_id", job.job_id), "$.trace_id", max_len=80, pattern=_ID_RE)
        timer = Timer.from_dict(body.get("timer"))

        source = _as_dict(_req(body, "source", "$"), "$.source")
        _reject_unknown(source, ("role", "node_id"), "$.source")
        source_role = _as_enum(_req(source, "role", "$.source"), "$.source.role", VALID_SOURCE_ROLES)
        source_node = _as_str(_req(source, "node_id", "$.source"), "$.source.node_id", max_len=128)

        target = _as_dict(_req(body, "target", "$"), "$.target")
        _reject_unknown(target, ("limb", "version"), "$.target")
        target_limb = _as_str(_req(target, "limb", "$.target"), "$.target.limb", max_len=32, pattern=_LIMB_RE)
        target_version_raw = target.get("version")
        target_version = "" if target_version_raw in (None, "") else _as_str(target_version_raw, "$.target.version", max_len=32, pattern=_LIMB_VERSION_RE)

        task = Task.from_dict(_req(body, "task", "$"), operations=operations)
        constraints = Constraints.from_dict(body.get("constraints"))
        elevation = Elevation.from_dict(body.get("elevation"))

        context = _as_dict(_opt(body, "context", {}), "$.context")
        _reject_unknown(context, ("summary", "artifacts", "extra"), "$.context")
        artifacts_raw = context.get("artifacts", [])
        if not isinstance(artifacts_raw, (list, tuple)):
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "context.artifacts muss eine Liste sein", "$.context.artifacts")
        artifacts: list[dict[str, Any]] = []
        for index, item in enumerate(artifacts_raw):
            entry = _as_dict(item, f"$.context.artifacts[{index}]")
            _reject_unknown(entry, ("path", "sha256", "role"), f"$.context.artifacts[{index}]")
            entry_path = _as_rel_path(_req(entry, "path", "$"), f"$.context.artifacts[{index}].path")
            digest = entry.get("sha256")
            if digest is not None:
                _as_str(digest, f"$.context.artifacts[{index}].sha256", min_len=64, max_len=64, pattern=_SHA256_RE)
            artifacts.append(
                {
                    "path": entry_path,
                    "sha256": digest,
                    "role": _as_str(_opt(entry, "role", "input"), f"$.context.artifacts[{index}].role", max_len=32),
                }
            )

        idempotency_key = _as_str(_opt(body, "idempotency_key", intent_id), "$.idempotency_key", max_len=128)

        return cls(
            intent_id=intent_id,
            operation=task.operation,
            task=task,
            target_limb=target_limb,
            created_at=format_timestamp(created),
            job=job,
            timer=timer,
            trace_id=trace_id,
            parent_intent_id=parent_intent_id,
            idempotency_key=idempotency_key,
            source_role=source_role,
            source_node=source_node,
            target_version=target_version,
            constraints=constraints,
            elevation=elevation,
            context_summary=_as_str(_opt(context, "summary", ""), "$.context.summary", min_len=0, max_len=16384),
            context_artifacts=tuple(artifacts),
            context_extra=_as_dict(_opt(context, "extra", {}), "$.context.extra"),
        )

    @classmethod
    def from_json(cls, text: str | bytes, *, operations: Operations | None = None) -> "Intent":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"kein gueltiges JSON: {exc}") from exc
        return cls.from_dict(data, operations=operations)

    @classmethod
    def from_file(cls, path: Path | str, *, operations: Operations | None = None) -> "Intent":
        file_path = Path(path)
        if not file_path.is_file():
            raise ProtocolError(ErrorCode.PATH_NOT_FOUND, f"Intent-Datei fehlt: {file_path}")
        return cls.from_json(file_path.read_text(encoding="utf-8"), operations=operations)


# --------------------------------------------------------------------------- #
# Result-Bausteine
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Artifact:
    path: str
    action: str
    bytes: int = 0
    sha256: str = ""
    backup_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"path": self.path, "action": self.action, "bytes": self.bytes}
        if self.sha256:
            body["sha256"] = self.sha256
        if self.backup_path:
            body["backup_path"] = self.backup_path
        return body

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "$.artifacts[]") -> "Artifact":
        body = _as_dict(data, path)
        _reject_unknown(body, ("path", "action", "bytes", "sha256", "backup_path"), path)
        digest = body.get("sha256", "")
        if digest:
            _as_str(digest, f"{path}.sha256", min_len=64, max_len=64, pattern=_SHA256_RE)
        backup = body.get("backup_path")
        return cls(
            path=_as_rel_path(_req(body, "path", path), f"{path}.path"),
            action=_as_enum(_req(body, "action", path), f"{path}.action", VALID_ARTIFACT_ACTIONS),
            bytes=int(_as_number(_opt(body, "bytes", 0), f"{path}.bytes", minimum=0, maximum=1_073_741_824, integer=True)),
            sha256=str(digest or ""),
            backup_path=_as_rel_path(backup, f"{path}.backup_path") if backup else "",
        )


@dataclass(frozen=True)
class StatusReport:
    """Klartext-Bericht des Limbs -- Pflicht bei ``timeout`` und ``partial``.

    Beantwortet exakt die Frage des Kerns: *Ist die Aufgabe abgeschlossen, und
    wenn nicht, warum ist sie in diesem Durchgang nicht abschliessbar?*
    """

    state: str
    explanation: str = ""
    done: tuple[str, ...] = ()
    remaining: tuple[str, ...] = ()
    blockers: tuple[dict[str, str], ...] = ()
    suggested_next: str = ""

    ALLOWED_KEYS = ("state", "explanation", "done", "remaining", "blockers", "suggested_next")

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "explanation": self.explanation,
            "done": list(self.done),
            "remaining": list(self.remaining),
            "blockers": [dict(b) for b in self.blockers],
            "suggested_next": self.suggested_next,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, path: str = "$.status_report") -> "StatusReport | None":
        if data is None:
            return None
        body = _as_dict(data, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        state = _as_enum(_req(body, "state", path), f"{path}.state", VALID_REPORT_STATES)
        explanation = _as_str(_opt(body, "explanation", ""), f"{path}.explanation", min_len=0, max_len=8192)
        blockers_raw = body.get("blockers", [])
        if not isinstance(blockers_raw, (list, tuple)):
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "blockers muss eine Liste sein", f"{path}.blockers")
        blockers: list[dict[str, str]] = []
        for index, item in enumerate(blockers_raw):
            entry = _as_dict(item, f"{path}.blockers[{index}]")
            _reject_unknown(entry, ("code", "message", "hint"), f"{path}.blockers[{index}]")
            blockers.append(
                {
                    "code": _as_str(_opt(entry, "code", ErrorCode.INTERNAL), f"{path}.blockers[{index}].code", max_len=64),
                    "message": _as_str(_opt(entry, "message", ""), f"{path}.blockers[{index}].message", min_len=0, max_len=4096),
                    "hint": _as_str(_opt(entry, "hint", ""), f"{path}.blockers[{index}].hint", min_len=0, max_len=2048),
                }
            )
        if state in {"timeout", "blocked"} and not explanation.strip():
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"status_report.state '{state}' erfordert eine Erklaerung (explanation)",
                f"{path}.explanation",
            )
        return cls(
            state=state,
            explanation=explanation,
            done=_as_str_list(_opt(body, "done", ()), f"{path}.done", max_items=64),
            remaining=_as_str_list(_opt(body, "remaining", ()), f"{path}.remaining", max_items=64),
            blockers=tuple(blockers),
            suggested_next=_as_str(_opt(body, "suggested_next", ""), f"{path}.suggested_next", min_len=0, max_len=4096),
        )


@dataclass(frozen=True)
class TimerReport:
    """Timer-Nachweis im Result: wann geschaerft, wann berichtet, Ueberzug."""

    armed_at: str | None = None
    expires_at: str | None = None
    reported_at: str = ""
    remaining_ms: int = 0
    overrun_ms: int = 0
    self_reported: bool = False

    ALLOWED_KEYS = ("armed_at", "expires_at", "reported_at", "remaining_ms", "overrun_ms", "self_reported")

    def to_dict(self) -> dict[str, Any]:
        return {
            "armed_at": self.armed_at,
            "expires_at": self.expires_at,
            "reported_at": self.reported_at,
            "remaining_ms": self.remaining_ms,
            "overrun_ms": self.overrun_ms,
            "self_reported": self.self_reported,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None, path: str = "$.timer") -> "TimerReport":
        body = _as_dict(data if data is not None else {}, path)
        _reject_unknown(body, cls.ALLOWED_KEYS, path)
        return cls(
            armed_at=_optional_timestamp(body.get("armed_at"), f"{path}.armed_at"),
            expires_at=_optional_timestamp(body.get("expires_at"), f"{path}.expires_at"),
            reported_at=_as_str(_opt(body, "reported_at", ""), f"{path}.reported_at", min_len=0, max_len=40),
            remaining_ms=int(_as_number(_opt(body, "remaining_ms", 0), f"{path}.remaining_ms", minimum=-86_400_000, maximum=86_400_000, integer=True)),
            overrun_ms=int(_as_number(_opt(body, "overrun_ms", 0), f"{path}.overrun_ms", minimum=0, maximum=86_400_000, integer=True)),
            self_reported=_as_bool(_opt(body, "self_reported", False), f"{path}.self_reported"),
        )


@dataclass(frozen=True)
class Result:
    """Antwort eines Limbs -- exakt ein Objekt pro Durchgang."""

    result_id: str
    intent_id: str
    trace_id: str
    status: str
    operation: str
    limb_name: str
    started_at: str
    finished_at: str
    job_id: str = ""
    iteration: int = 1
    duration_ms: int = 0
    limb_version: str = "0.0.0"
    limb_pid: int = 0
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[Artifact, ...] = ()
    status_report: StatusReport | None = None
    timer: TimerReport = field(default_factory=TimerReport)
    diagnostics_stdout: str = ""
    diagnostics_stderr: str = ""
    diagnostics_exit_code: int | None = None
    error: dict[str, Any] | None = None
    confidence: float = 1.0
    notes: str = ""

    ALLOWED_KEYS = (
        "protocol",
        "version",
        "result_id",
        "intent_id",
        "trace_id",
        "job_id",
        "iteration",
        "status",
        "operation",
        "limb",
        "started_at",
        "finished_at",
        "duration_ms",
        "output",
        "artifacts",
        "status_report",
        "timer",
        "diagnostics",
        "error",
        "self_report",
    )

    @property
    def ok(self) -> bool:
        return self.status == "success"

    @property
    def needs_iteration(self) -> bool:
        """True, wenn ein weiterer Durchgang sinnvoll ist (Fehler oder Zeitablauf)."""
        return self.status in {"failed", "timeout", "partial"}

    @property
    def error_code(self) -> str:
        return str((self.error or {}).get("code", ""))

    def to_dict(self) -> dict[str, Any]:
        error = None
        if self.error is not None:
            error = {
                "code": self.error.get("code", ErrorCode.INTERNAL),
                "message": self.error.get("message", ""),
                "hint": self.error.get("hint", ""),
            }
        return {
            "protocol": PROTOCOL_RESULT,
            "version": PROTOCOL_VERSION,
            "result_id": self.result_id,
            "intent_id": self.intent_id,
            "trace_id": self.trace_id,
            "job_id": self.job_id,
            "iteration": self.iteration,
            "status": self.status,
            "operation": self.operation,
            "limb": {"name": self.limb_name, "version": self.limb_version, "pid": self.limb_pid},
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "output": dict(self.output),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "status_report": self.status_report.to_dict() if self.status_report else None,
            "timer": self.timer.to_dict(),
            "diagnostics": {
                "stdout": self.diagnostics_stdout,
                "stderr": self.diagnostics_stderr,
                "exit_code": self.diagnostics_exit_code,
            },
            "error": error,
            "self_report": {"confidence": self.confidence, "notes": self.notes},
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, intent: Intent | None = None) -> "Result":
        body = _as_dict(data, "$")
        _reject_unknown(body, cls.ALLOWED_KEYS, "$")

        if _as_str(_req(body, "protocol", "$"), "$.protocol", max_len=32) != PROTOCOL_RESULT:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"protocol muss '{PROTOCOL_RESULT}' sein", "$.protocol")
        _check_version(_req(body, "version", "$"), "$.version")

        result_id = _as_str(_req(body, "result_id", "$"), "$.result_id", max_len=80, pattern=_ID_RE)
        intent_id = _as_str(_req(body, "intent_id", "$"), "$.intent_id", max_len=80, pattern=_ID_RE)
        status = _as_enum(_req(body, "status", "$"), "$.status", VALID_RESULT_STATUSES)
        iteration = int(_as_number(_opt(body, "iteration", 1), "$.iteration", minimum=1, maximum=ABSOLUTE_MAX_ITERATIONS, integer=True))
        operation = _as_str(_req(body, "operation", "$"), "$.operation", max_len=64)
        started = parse_timestamp(_req(body, "started_at", "$"), "$.started_at")
        finished = parse_timestamp(_req(body, "finished_at", "$"), "$.finished_at")
        if finished < started:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "finished_at liegt vor started_at", "$.finished_at")

        limb = _as_dict(_req(body, "limb", "$"), "$.limb")
        _reject_unknown(limb, ("name", "version", "pid"), "$.limb")
        limb_name = _as_str(_req(limb, "name", "$.limb"), "$.limb.name", max_len=32, pattern=_LIMB_RE)
        limb_version = _as_str(_opt(limb, "version", "0.0.0"), "$.limb.version", max_len=32, pattern=_LIMB_VERSION_RE)
        limb_pid = int(_as_number(_opt(limb, "pid", 0), "$.limb.pid", minimum=0, maximum=2**31, integer=True))

        artifacts_raw = body.get("artifacts", [])
        if not isinstance(artifacts_raw, (list, tuple)):
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "artifacts muss eine Liste sein", "$.artifacts")
        artifacts = tuple(Artifact.from_dict(item, f"$.artifacts[{i}]") for i, item in enumerate(artifacts_raw))

        status_report = StatusReport.from_dict(body.get("status_report"))
        timer_report = TimerReport.from_dict(body.get("timer"))

        diagnostics = _as_dict(_opt(body, "diagnostics", {}), "$.diagnostics")
        _reject_unknown(diagnostics, ("stdout", "stderr", "exit_code"), "$.diagnostics")
        exit_code = diagnostics.get("exit_code")
        if exit_code is not None:
            exit_code = int(_as_number(exit_code, "$.diagnostics.exit_code", minimum=-1000, maximum=1000, integer=True))

        error = body.get("error")
        error_dict: dict[str, Any] | None = None
        if error is not None:
            err = _as_dict(error, "$.error")
            _reject_unknown(err, ("code", "message", "hint"), "$.error")
            code = _as_str(_req(err, "code", "$.error"), "$.error.code", max_len=64)
            if code not in ErrorCode.ALL:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"unbekannter Fehlercode '{code}'", "$.error.code")
            error_dict = {
                "code": code,
                "message": _as_str(_opt(err, "message", ""), "$.error.message", min_len=0, max_len=16384),
                "hint": _as_str(_opt(err, "hint", ""), "$.error.hint", min_len=0, max_len=4096),
            }

        if status in {"failed", "rejected"} and error_dict is None:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"status '{status}' erfordert ein error-Objekt", "$.error")
        if status == "success" and error_dict is not None:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "status 'success' darf kein error-Objekt tragen", "$.error")
        if status == "timeout":
            if status_report is None:
                raise ProtocolError(
                    ErrorCode.SCHEMA_INVALID,
                    "status 'timeout' erfordert einen status_report (Klarheit ueber Stand und Blocker)",
                    "$.status_report",
                )
            if status_report.state not in {"timeout", "blocked", "partial"}:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"status_report.state '{status_report.state}' passt nicht zu status 'timeout'", "$.status_report.state")
        if status == "partial" and status_report is None:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "status 'partial' erfordert einen status_report", "$.status_report")
        if status == "success" and status_report is not None and status_report.state != "completed":
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, "status 'success' verlangt status_report.state='completed'", "$.status_report.state")

        self_report = _as_dict(_opt(body, "self_report", {}), "$.self_report")
        _reject_unknown(self_report, ("confidence", "notes"), "$.self_report")

        job_id = _as_str(_opt(body, "job_id", ""), "$.job_id", min_len=0, max_len=80)
        if job_id:
            _as_str(job_id, "$.job_id", max_len=80, pattern=_ID_RE)
        trace_id = _as_str(_opt(body, "trace_id", job_id or intent_id), "$.trace_id", max_len=80, pattern=_ID_RE)

        if intent is not None:
            if intent_id != intent.intent_id:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"intent_id {intent_id} passt nicht zu {intent.intent_id}", "$.intent_id")
            if trace_id != intent.trace_id:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, "trace_id stimmt nicht mit dem Intent ueberein", "$.trace_id")
            if job_id and job_id != intent.job_id:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, "job_id stimmt nicht mit dem Intent ueberein", "$.job_id")
            if iteration != intent.iteration:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"iteration {iteration} weicht vom Intent ({intent.iteration}) ab", "$.iteration")
            if operation != intent.operation:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"operation '{operation}' weicht vom Intent ('{intent.operation}') ab", "$.operation")
            if limb_name != intent.target_limb:
                raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"limb '{limb_name}' ist nicht der Adressat '{intent.target_limb}'", "$.limb.name")

        return cls(
            result_id=result_id,
            intent_id=intent_id,
            trace_id=trace_id,
            job_id=job_id or (intent.job_id if intent else ""),
            status=status,
            operation=operation,
            limb_name=limb_name,
            iteration=iteration,
            started_at=format_timestamp(started),
            finished_at=format_timestamp(finished),
            duration_ms=int(_as_number(_opt(body, "duration_ms", 0), "$.duration_ms", minimum=0, maximum=86_400_000, integer=True)),
            limb_version=limb_version,
            limb_pid=limb_pid,
            output=_as_dict(_opt(body, "output", {}), "$.output"),
            artifacts=artifacts,
            status_report=status_report,
            timer=timer_report,
            diagnostics_stdout=_as_str(_opt(diagnostics, "stdout", ""), "$.diagnostics.stdout", min_len=0, max_len=1_048_576),
            diagnostics_stderr=_as_str(_opt(diagnostics, "stderr", ""), "$.diagnostics.stderr", min_len=0, max_len=1_048_576),
            diagnostics_exit_code=exit_code,
            error=error_dict,
            confidence=float(_as_number(_opt(self_report, "confidence", 1.0), "$.self_report.confidence", minimum=0.0, maximum=1.0)),
            notes=_as_str(_opt(self_report, "notes", ""), "$.self_report.notes", min_len=0, max_len=8192),
        )

    @classmethod
    def from_json(cls, text: str | bytes, *, intent: Intent | None = None) -> "Result":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProtocolError(ErrorCode.SCHEMA_INVALID, f"kein gueltiges JSON: {exc}") from exc
        return cls.from_dict(data, intent=intent)

    @classmethod
    def from_file(cls, path: Path | str, *, intent: Intent | None = None) -> "Result":
        file_path = Path(path)
        if not file_path.is_file():
            raise ProtocolError(ErrorCode.PATH_NOT_FOUND, f"Result-Datei fehlt: {file_path}")
        return cls.from_json(file_path.read_text(encoding="utf-8"), intent=intent)
