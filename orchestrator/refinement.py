"""Refinement-Vault: geparkte Rust-Limbs mit Zustands-FSM (Human-in-the-Loop).

Ablauf (Architekturvorschlag "asynchroner Refinement-Vault"):

1. Eine modifizierte Limb wird **nicht** direkt in die produktive Baseline
   geschrieben, sondern im Vault geparkt: ``parked_pending_user``.
2. Apollo zeigt sie dem Menschen. Freigabe -> ``promoted``; Ablehnung oder
   Fehlerfund -> ``refinement_queued``.
3. Ein Hintergrund-Daemon (``orchestrator/refinement_daemon.py``) holt sich
   den **aeltesten** Eintrag aus ``refinement_queued`` (FIFO), setzt ihn unter
   einer Lease auf ``healing_in_progress``, testet/heilt ihn in einer isolierten
   Sandbox und stellt ihn bei Erfolg als ``ready_for_review`` erneut vor.
4. Scheitert die Heilung wiederholt, greift die Fehlerisolation: Rueckstellung
   in die Queue mit exponentiellem Backoff -- und nach ``max_attempts`` die
   Quarantaene (``quarantined``), nie ein stilles Endlos-Retry.

Layout pro Limb (Artefakt und Metadaten liegen nebeneinander)::

    <vault>/<limb_id>/
        meta.json                 # FSM-Zustand, Historie, Lease, letzter Fehler
        artifact/<dateiname>      # aktueller Patch-Candidate
        versions/v0001/<dateiname>  # unveraenderliche Versions-Schnappschuesse
        versions/v0002/<dateiname>

Die Baseline wird hier **nie** angefasst: ``promote`` kopiert erst nach einer
menschlichen Freigabe (``approve``) an ein ausdruecklich angegebenes Ziel.
Nur Standardbibliothek -- ``apscheduler`` & Co. sind im NEU-Stack bewusst keine
Abhaengigkeit (siehe ``pyproject.toml``); der Scheduler ist ein asyncio-Loop
im Daemon-Modul bzw. ein ``run-once``-Aufruf aus Cron/systemd.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.atomic import atomic_write_bytes
from core.protocol import format_timestamp, parse_timestamp, utc_now

__all__ = [
    "HEALING_IN_PROGRESS",
    "HISTORY_LIMIT",
    "PARKED_PENDING_USER",
    "PROMOTED",
    "QUARANTINED",
    "READY_FOR_REVIEW",
    "REFINEMENT_QUEUED",
    "STATE_TRANSITIONS",
    "TERMINAL_STATES",
    "InvalidTransition",
    "RefinementVault",
    "VaultEntry",
    "VaultError",
    "VaultNotFound",
]

# --------------------------------------------------------------------------- #
# FSM
# --------------------------------------------------------------------------- #
PARKED_PENDING_USER = "parked_pending_user"
REFINEMENT_QUEUED = "refinement_queued"
HEALING_IN_PROGRESS = "healing_in_progress"
READY_FOR_REVIEW = "ready_for_review"
#: Mensch hat freigegeben; das Artefakt darf in die Baseline kopiert werden.
PROMOTED = "promoted"
#: Fehlerisolation: Budget erschoepft oder final abgelehnt. Nur ein Mensch
#: (``requeue``) holt einen Eintrag hier wieder heraus.
QUARANTINED = "quarantined"

#: Erlaubte Uebergaenge. Alles ausserhalb dieser Tabelle ist ein Bug im
#: Aufrufer und wird mit :class:`InvalidTransition` laut abgelehnt -- die FSM
#: raet keine Zustaende.
STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    PARKED_PENDING_USER: frozenset({REFINEMENT_QUEUED, PROMOTED, QUARANTINED}),
    REFINEMENT_QUEUED: frozenset({HEALING_IN_PROGRESS, QUARANTINED}),
    HEALING_IN_PROGRESS: frozenset({READY_FOR_REVIEW, REFINEMENT_QUEUED, QUARANTINED}),
    READY_FOR_REVIEW: frozenset({PROMOTED, REFINEMENT_QUEUED, QUARANTINED}),
    PROMOTED: frozenset(),
    QUARANTINED: frozenset({REFINEMENT_QUEUED}),
}

TERMINAL_STATES = frozenset({PROMOTED, QUARANTINED})

SCHEMA_VERSION = 1
HISTORY_LIMIT = 200
MAX_ERROR_CHARS = 16_000
_LIMB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CLAIM_LOCK_STALE_S = 30.0


class VaultError(RuntimeError):
    """Allgemeiner Vault-Fehler (ungueltige ID, Lease-Konflikt, ...)."""


class VaultNotFound(VaultError):
    """Kein Eintrag unter dieser ``limb_id``."""


class InvalidTransition(VaultError):
    """FSM-Verletzung: Der gewuenschte Uebergang ist nicht erlaubt."""


def check_limb_id(limb_id: str) -> str:
    if not _LIMB_ID_RE.match(limb_id or "") or ".." in limb_id:
        raise VaultError(f"Ungueltige limb_id {limb_id!r} (erlaubt: [A-Za-z0-9._-], 1-64 Zeichen, kein '..').")
    return limb_id


def _now() -> datetime:
    return utc_now()


def _stamp(moment: datetime) -> str:
    return format_timestamp(moment)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Eintrag
# --------------------------------------------------------------------------- #
@dataclass
class VaultEntry:
    """Ein geparkter Limb samt FSM-Zustand (Inhalt von ``meta.json``)."""

    limb_id: str
    name: str
    artifact_filename: str
    sha256: str
    size: int
    state: str = PARKED_PENDING_USER
    version: int = 1
    attempts: int = 0
    max_attempts: int = 5
    heal_steps: int = 0
    test_command: tuple[str, ...] = ()
    source: str = ""
    user_feedback: str = ""
    last_error: dict[str, Any] = field(default_factory=dict)
    last_step: str = ""
    next_attempt_at: str = ""
    lease_worker: str = ""
    lease_expires_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    # -- Ableitungen ------------------------------------------------------ #
    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def lease_expired(self, *, now: datetime | None = None) -> bool:
        if self.state != HEALING_IN_PROGRESS or not self.lease_expires_at:
            return self.state == HEALING_IN_PROGRESS
        return (now or _now()) >= parse_timestamp(self.lease_expires_at, "$.lease_expires_at")

    def due(self, *, now: datetime | None = None) -> bool:
        """In der Queue und Backoff abgelaufen?"""
        if self.state != REFINEMENT_QUEUED:
            return False
        if not self.next_attempt_at:
            return True
        return (now or _now()) >= parse_timestamp(self.next_attempt_at, "$.next_attempt_at")

    # -- Serialisierung ---------------------------------------------------- #
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "limb_id": self.limb_id,
            "name": self.name,
            "artifact": {"filename": self.artifact_filename, "sha256": self.sha256, "size": self.size},
            "state": self.state,
            "version": self.version,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "heal_steps": self.heal_steps,
            "test_command": list(self.test_command),
            "source": self.source,
            "user_feedback": self.user_feedback,
            "last_error": dict(self.last_error),
            "last_step": self.last_step,
            "next_attempt_at": self.next_attempt_at,
            "lease": {"worker": self.lease_worker, "expires_at": self.lease_expires_at},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "history": list(self.history[-HISTORY_LIMIT:]),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VaultEntry:
        body = dict(data)
        if int(body.get("schema_version", 0) or 0) != SCHEMA_VERSION:
            raise VaultError(f"meta.json: schema_version {body.get('schema_version')!r} wird nicht unterstuetzt.")
        raw_artifact = body.get("artifact")
        artifact: Mapping[str, Any] = raw_artifact if isinstance(raw_artifact, Mapping) else {}
        raw_lease = body.get("lease")
        lease: Mapping[str, Any] = raw_lease if isinstance(raw_lease, Mapping) else {}
        state = str(body.get("state", ""))
        if state not in STATE_TRANSITIONS:
            raise VaultError(f"meta.json: unbekannter Zustand {state!r}.")
        return cls(
            limb_id=check_limb_id(str(body.get("limb_id", ""))),
            name=str(body.get("name", "")),
            artifact_filename=str(artifact.get("filename", "")),
            sha256=str(artifact.get("sha256", "")),
            size=int(artifact.get("size", 0) or 0),
            state=state,
            version=max(1, int(body.get("version", 1) or 1)),
            attempts=max(0, int(body.get("attempts", 0) or 0)),
            max_attempts=max(1, int(body.get("max_attempts", 5) or 5)),
            heal_steps=max(0, int(body.get("heal_steps", 0) or 0)),
            test_command=tuple(str(item) for item in body.get("test_command", []) or []),
            source=str(body.get("source", "")),
            user_feedback=str(body.get("user_feedback", "")),
            last_error=dict(body.get("last_error") or {}),
            last_step=str(body.get("last_step", "")),
            next_attempt_at=str(body.get("next_attempt_at", "")),
            lease_worker=str(lease.get("worker", "")),
            lease_expires_at=str(lease.get("expires_at", "")),
            created_at=str(body.get("created_at", "")),
            updated_at=str(body.get("updated_at", "")),
            history=[dict(item) for item in body.get("history", []) or [] if isinstance(item, Mapping)],
        )


# --------------------------------------------------------------------------- #
# Vault
# --------------------------------------------------------------------------- #
class RefinementVault:
    """Dateibasierter Vault. Sicher gegen Parallelzugriff ueber eine Claim-Lockdatei.

    ``bus`` ist optional: ein ``orchestrator.events.EventBus`` (oder jedes
    Objekt mit ``emit(kind, payload, job_id=..., limb=...)``). Apollo liest
    dieselben Uebergaenge zusaetzlich aus ``list()``/``meta.json`` -- der Bus
    ist Benachrichtigung, nicht Wahrheit.
    """

    def __init__(self, root: Path | str, *, bus: Any = None) -> None:
        self.root = Path(root)
        self.bus = bus

    # -- Pfade -------------------------------------------------------------- #
    def entry_dir(self, limb_id: str) -> Path:
        return self.root / check_limb_id(limb_id)

    def meta_path(self, limb_id: str) -> Path:
        return self.entry_dir(limb_id) / "meta.json"

    def artifact_path(self, entry: VaultEntry) -> Path:
        return self.entry_dir(entry.limb_id) / "artifact" / entry.artifact_filename

    def version_path(self, entry: VaultEntry, version: int | None = None) -> Path:
        return self.entry_dir(entry.limb_id) / "versions" / f"v{version or entry.version:04d}" / entry.artifact_filename

    # -- Lesen -------------------------------------------------------------- #
    def get(self, limb_id: str) -> VaultEntry:
        path = self.meta_path(limb_id)
        if not path.is_file():
            raise VaultNotFound(f"Kein Vault-Eintrag fuer {limb_id!r} unter {self.root}.")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise VaultError(f"meta.json von {limb_id!r} ist nicht lesbar: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise VaultError(f"meta.json von {limb_id!r} ist kein JSON-Objekt.")
        return VaultEntry.from_dict(raw)

    def list_entries(self, *, state: str | None = None) -> list[VaultEntry]:
        """Alle Eintraege, aelteste zuerst (FIFO -- der Daemon arbeitet fair ab)."""
        entries: list[VaultEntry] = []
        if self.root.is_dir():
            for child in sorted(self.root.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                with contextlib.suppress(VaultError):
                    entries.append(self.get(child.name))
        entries.sort(key=lambda entry: (entry.created_at, entry.limb_id))
        return [entry for entry in entries if state is None or entry.state == state]

    def queued(self, *, now: datetime | None = None) -> list[VaultEntry]:
        """Faellige Queue-Eintraege (Backoff beachtet), aelteste zuerst."""
        return [entry for entry in self.list_entries(state=REFINEMENT_QUEUED) if entry.due(now=now)]

    # -- Schreiben (intern) -------------------------------------------------- #
    def _save(self, entry: VaultEntry, *, event: str, detail: Mapping[str, Any] | None = None) -> VaultEntry:
        entry.updated_at = _stamp(_now())
        entry.history.append({"at": entry.updated_at, "event": event, **dict(detail or {})})
        entry.history = entry.history[-HISTORY_LIMIT:]
        payload = (json.dumps(entry.to_dict(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        atomic_write_bytes(self.meta_path(entry.limb_id), payload, fsync=True)
        self._emit(f"refinement.{event}", entry, detail)
        return entry

    def _emit(self, kind: str, entry: VaultEntry, detail: Mapping[str, Any] | None = None) -> None:
        if self.bus is None:
            return
        with contextlib.suppress(Exception):  # Benachrichtigung darf nie den Zustand kippen
            self.bus.emit(
                kind,
                {"limb_id": entry.limb_id, "state": entry.state, "version": entry.version, "attempts": entry.attempts, **dict(detail or {})},
                job_id=f"refinement:{entry.limb_id}",
                limb=entry.limb_id,
            )

    def _transition(self, entry: VaultEntry, target: str, *, event: str, detail: Mapping[str, Any] | None = None) -> VaultEntry:
        allowed = STATE_TRANSITIONS[entry.state]
        if target not in allowed:
            raise InvalidTransition(
                f"{entry.limb_id}: {entry.state} -> {target} ist nicht erlaubt "
                f"(erlaubt: {', '.join(sorted(allowed)) or 'keine, terminal'})."
            )
        entry.state = target
        return self._save(entry, event=event, detail=detail)

    @contextlib.contextmanager
    def _claim_lock(self) -> Iterator[None]:
        """Vault-weite Sperre fuer Claim/Lease-Uebergaenge (O_EXCL-Lockdatei).

        Haelt nur den kurzen Metadaten-Uebergang, nie den Heilungslauf selbst --
        ein langsamer ``cargo test`` blockiert damit weder Apollo noch das Parken.
        Verwaiste Sperren (Prozess tot) werden nach ``_CLAIM_LOCK_STALE_S`` gebrochen.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / ".claim.lock"
        deadline = time.monotonic() + 10.0
        handle: int | None = None
        while handle is None:
            try:
                handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                with contextlib.suppress(OSError):
                    if time.time() - lock.stat().st_mtime > _CLAIM_LOCK_STALE_S:
                        lock.unlink(missing_ok=True)
                        continue
                if time.monotonic() > deadline:
                    raise VaultError("Refinement-Vault ist gesperrt (.claim.lock) -- laeuft ein zweiter Daemon?") from None
                time.sleep(0.05)
        try:
            os.write(handle, f"{os.getpid()}\n".encode())
            yield
        finally:
            os.close(handle)
            lock.unlink(missing_ok=True)

    def _install_artifact(self, entry: VaultEntry, source: Path) -> None:
        """Kopiert ``source`` als aktuellen Candidate + Versions-Schnappschuss."""
        artifact = self.artifact_path(entry)
        versioned = self.version_path(entry)
        for target in (versioned, artifact):
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
            shutil.copyfile(source, tmp)
            os.replace(tmp, target)
        entry.sha256 = _sha256(artifact)
        entry.size = artifact.stat().st_size

    # -- Lebenszyklus: Mensch / Apollo -------------------------------------- #
    def park(
        self,
        source_path: Path | str,
        *,
        limb_id: str,
        name: str = "",
        test_command: Any = (),
        source: str = "",
        max_attempts: int = 5,
    ) -> VaultEntry:
        """Parkt ein Artefakt im Staging: ``parked_pending_user`` (Version 1).

        Kopiert -- bewegt nie: Die Quelle (z. B. ein Build-Verzeichnis) bleibt
        bestehen, der Vault besitzt ab hier seine eigene, gehashte Kopie.
        """
        source_file = Path(source_path)
        if not source_file.is_file():
            raise VaultError(f"Zu parkendes Artefakt existiert nicht: {source_file}")
        check_limb_id(limb_id)
        if self.meta_path(limb_id).is_file():
            raise VaultError(f"{limb_id!r} ist bereits im Vault geparkt -- erst freigeben, ablehnen oder requeue nutzen.")
        now = _stamp(_now())
        entry = VaultEntry(
            limb_id=limb_id,
            name=name or limb_id,
            artifact_filename=source_file.name,
            sha256="",
            size=0,
            max_attempts=max(1, int(max_attempts)),
            test_command=tuple(str(item) for item in test_command),
            source=source,
            created_at=now,
        )
        self._install_artifact(entry, source_file)
        return self._save(entry, event="parked", detail={"sha256": entry.sha256, "version": entry.version})

    def reject(self, limb_id: str, *, feedback: str = "", final: bool = False) -> VaultEntry:
        """Mensch lehnt ab: zurueck in die Heilungs-Queue (oder final in Quarantaene)."""
        entry = self.get(limb_id)
        if feedback:
            entry.user_feedback = feedback[:4000]
        if final:
            return self._transition(entry, QUARANTINED, event="rejected_final", detail={"feedback": entry.user_feedback})
        entry.next_attempt_at = ""  # menschliche Ablehnung ist sofort faellig
        return self._transition(entry, REFINEMENT_QUEUED, event="rejected", detail={"feedback": entry.user_feedback})

    def approve(self, limb_id: str, *, promote_to: Path | str | None = None, approved_by: str = "human") -> VaultEntry:
        """Mensch gibt frei: ``promoted`` -- optional Kopie in die Baseline.

        Ohne ``promote_to`` wird nur der Zustand gesetzt (Apollo kopiert selbst);
        mit Ziel wird das Artefakt dorthin kopiert und der Hash erneut geprueft.
        Die Freigabe ist der **einzige** Weg aus dem Vault in die Baseline.
        """
        if approved_by != "human":
            raise VaultError("Nur ein Mensch darf einen Limb freigeben (approved_by='human') -- Human-in-the-Loop.")
        entry = self.get(limb_id)
        promoted_path = ""
        if promote_to is not None:
            artifact = self.artifact_path(entry)
            if _sha256(artifact) != entry.sha256:
                raise VaultError(f"{limb_id}: Artefakt-Hash weicht von meta.json ab -- nicht freigeben, erst pruefen.")
            target = Path(promote_to)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
            shutil.copyfile(artifact, tmp)
            os.replace(tmp, target)
            promoted_path = str(target)
        return self._transition(entry, PROMOTED, event="approved", detail={"promoted_to": promoted_path})

    def requeue(self, limb_id: str, *, reset_attempts: bool = True) -> VaultEntry:
        """Mensch holt einen Eintrag aus der Quarantaene zurueck in die Queue."""
        entry = self.get(limb_id)
        if reset_attempts:
            entry.attempts = 0
        entry.next_attempt_at = ""
        entry.last_error = {}
        return self._transition(entry, REFINEMENT_QUEUED, event="requeued")

    # -- Lebenszyklus: Daemon ------------------------------------------------- #
    def claim_next(self, *, worker_id: str, lease_s: float = 900.0, now: datetime | None = None) -> VaultEntry | None:
        """Holt den aeltesten faelligen Eintrag und setzt die Lease (FIFO).

        Gibt ``None`` statt zu warten, wenn nichts faellig ist -- der Scheduler
        entscheidet, wann der naechste Lauf stattfindet.
        """
        moment = now or _now()
        with self._claim_lock():
            self._recover_stale_leases_locked(now=moment)
            for entry in self.queued(now=moment):
                entry.lease_worker = worker_id
                entry.lease_expires_at = _stamp(moment + timedelta(seconds=max(10.0, lease_s)))
                return self._transition(entry, HEALING_IN_PROGRESS, event="claimed", detail={"worker": worker_id})
        return None

    def replace_candidate(self, limb_id: str, new_artifact: Path | str, *, worker_id: str) -> VaultEntry:
        """Neuer Patch-Candidate aus der Sandbox: Version +1, Hash neu.

        Nur der Lease-Inhaber darf ersetzen -- ein verspaeteter Worker aus einem
        abgelaufenen Lauf kann einen neueren Candidate nicht ueberschreiben.
        """
        entry = self._require_lease(limb_id, worker_id)
        candidate = Path(new_artifact)
        if not candidate.is_file():
            raise VaultError(f"Patch-Candidate existiert nicht: {candidate}")
        entry.version += 1
        self._install_artifact(entry, candidate)
        entry.heal_steps += 1
        return self._save(entry, event="candidate_replaced", detail={"version": entry.version, "sha256": entry.sha256})

    def complete_healing(self, limb_id: str, *, worker_id: str) -> VaultEntry:
        """Sandbox-Lauf war gruen: ``ready_for_review`` -- der Mensch entscheidet."""
        entry = self._require_lease(limb_id, worker_id)
        entry.lease_worker = ""
        entry.lease_expires_at = ""
        entry.last_error = {}
        entry.next_attempt_at = ""
        return self._transition(entry, READY_FOR_REVIEW, event="ready_for_review", detail={"worker": worker_id})

    def fail_healing(
        self,
        limb_id: str,
        *,
        worker_id: str,
        step: str,
        kind: str,
        message: str,
        detail: str = "",
        retry_base_s: float = 60.0,
        now: datetime | None = None,
    ) -> VaultEntry:
        """Ein Schritt ist gescheitert: Fehler isolieren, Backoff oder Quarantaene.

        ``attempts`` zaehlt Daemon-Laeufe (nicht Einzelschritte). Backoff:
        ``base * 2**attempts``, gedeckelt auf 1 h -- der Vault leert sich
        methodisch, statt in einer heissen Schleife gegen dieselbe Wand zu laufen.
        """
        entry = self._require_lease(limb_id, worker_id)
        moment = now or _now()
        entry.attempts += 1
        entry.last_step = step
        entry.last_error = {
            "step": step,
            "kind": kind,
            "message": message[:2000],
            "detail": detail[-MAX_ERROR_CHARS:],
            "at": _stamp(moment),
            "attempt": entry.attempts,
        }
        entry.lease_worker = ""
        entry.lease_expires_at = ""
        info = {"step": step, "kind": kind, "attempt": entry.attempts, "message": message[:500]}
        if entry.attempts >= entry.max_attempts:
            return self._transition(entry, QUARANTINED, event="quarantined", detail=info)
        delay = min(3600.0, max(0.0, retry_base_s) * (2 ** (entry.attempts - 1)))
        entry.next_attempt_at = _stamp(moment + timedelta(seconds=delay))
        return self._transition(entry, REFINEMENT_QUEUED, event="healing_failed", detail={**info, "retry_in_s": delay})

    def recover_stale_leases(self, *, now: datetime | None = None) -> list[VaultEntry]:
        """Abgestuerzte Worker aufraeumen: abgelaufene Leases zurueckstellen."""
        with self._claim_lock():
            return self._recover_stale_leases_locked(now=now or _now())

    def _recover_stale_leases_locked(self, *, now: datetime) -> list[VaultEntry]:
        recovered: list[VaultEntry] = []
        for entry in self.list_entries(state=HEALING_IN_PROGRESS):
            if not entry.lease_expired(now=now):
                continue
            worker = entry.lease_worker
            # Wie ein Fehlschlag zaehlen: Ein Worker, der wiederholt abstuerzt,
            # darf den Eintrag nicht unendlich zwischen den Zustaenden pendeln lassen.
            entry.attempts += 1
            entry.last_step = "lease"
            entry.last_error = {"step": "lease", "kind": "lease_expired", "message": f"Lease von {worker!r} abgelaufen.", "at": _stamp(now), "attempt": entry.attempts}
            entry.lease_worker = ""
            entry.lease_expires_at = ""
            if entry.attempts >= entry.max_attempts:
                recovered.append(self._transition(entry, QUARANTINED, event="quarantined", detail={"kind": "lease_expired", "worker": worker}))
            else:
                entry.next_attempt_at = _stamp(now + timedelta(seconds=60.0))
                recovered.append(self._transition(entry, REFINEMENT_QUEUED, event="lease_recovered", detail={"worker": worker}))
        return recovered

    def _require_lease(self, limb_id: str, worker_id: str) -> VaultEntry:
        entry = self.get(limb_id)
        if entry.state != HEALING_IN_PROGRESS:
            raise InvalidTransition(f"{limb_id}: erwartet healing_in_progress, gefunden {entry.state}.")
        if entry.lease_worker != worker_id:
            raise VaultError(f"{limb_id}: Lease gehoert {entry.lease_worker!r}, nicht {worker_id!r}.")
        return entry
