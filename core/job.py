"""Job-Lebenszyklus und Iterationszaehlung (Protokoll 1.1).

Grundregel des Users, hier maschinell durchgesetzt:

    Ein Job ist **wirklich failed**, wenn nach einem Versagen *keine*
    Massnahme mehr ergriffen wird, um das Problem zu loesen.
    Geht das System nach einem Fehlschlag in den autodidaktischen Modus
    (2. Durchgang mit neu entworfenem Auftrag), ist der Job **nicht** failed,
    sondern ``iterating``.

Iterationen zaehlen pro **Job** (``job_id``), nicht pro Agenten- oder
Limb-Aufruf. Maximum: ``core.config.ABSOLUTE_MAX_ITERATIONS`` (= 2), im
Dev-Modus 1.

Zustaende::

    open -> running -> resolved                 (Ziel erreicht)
                    -> iterating -> resolved    (Autodidaktik: 2. Durchgang)
                                 -> failed      (keine Massnahme mehr / Budget leer)
                                 -> escalated   (Mensch noetig)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import ABSOLUTE_MAX_ITERATIONS, NeuConfig
from .protocol import format_timestamp, new_id, parse_timestamp, utc_now

JOB_OPEN = "open"
JOB_RUNNING = "running"
JOB_ITERATING = "iterating"
JOB_RESOLVED = "resolved"
JOB_ESCALATED = "escalated"
JOB_FAILED = "failed"

ACTIVE_STATES = (JOB_OPEN, JOB_RUNNING, JOB_ITERATING)
TERMINAL_STATES = (JOB_RESOLVED, JOB_ESCALATED, JOB_FAILED)

#: Warum ein Job endgueltig gescheitert ist.
FAILURE_NO_MEASURE = "no_measure_available"
FAILURE_STALE = "stale_reclaimed"
FAILURE_INTERNAL = "internal_error"
FAILURE_BUDGET_EXHAUSTED = "budget_exhausted"
FAILURE_ESCALATION = "escalation_required"
FAILURE_ABORTED = "aborted_by_policy"


@dataclass(frozen=True)
class IterationEntry:
    """Ein Durchgang eines Jobs -- der Pruefstein fuer die Autodidaktik."""

    iteration: int
    intent_id: str
    operation: str
    limb: str
    status: str
    verdict: str
    error_code: str = ""
    duration_ms: int = 0
    timer_expired: bool = False
    self_reported: bool = False
    archive: str = ""
    measure: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "intent_id": self.intent_id,
            "operation": self.operation,
            "limb": self.limb,
            "status": self.status,
            "verdict": self.verdict,
            "error_code": self.error_code,
            "duration_ms": self.duration_ms,
            "timer_expired": self.timer_expired,
            "self_reported": self.self_reported,
            "archive": self.archive,
            "measure": self.measure,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IterationEntry":
        return cls(
            iteration=int(data.get("iteration", 1)),
            intent_id=str(data.get("intent_id", "")),
            operation=str(data.get("operation", "")),
            limb=str(data.get("limb", "")),
            status=str(data.get("status", "")),
            verdict=str(data.get("verdict", "")),
            error_code=str(data.get("error_code", "")),
            duration_ms=int(data.get("duration_ms", 0)),
            timer_expired=bool(data.get("timer_expired", False)),
            self_reported=bool(data.get("self_reported", False)),
            archive=str(data.get("archive", "")),
            measure=str(data.get("measure", "")),
        )


@dataclass(frozen=True)
class JobRecord:
    """Persistenter Zustand eines Jobs."""

    job_id: str
    goal: str
    status: str = JOB_OPEN
    created_at: str = ""
    updated_at: str = ""
    iteration: int = 0
    max_iterations: int = 1
    mode: str = "dev"
    deadline_s: float = 60.0
    limbs_used: tuple[str, ...] = ()
    operations_used: tuple[str, ...] = ()
    measures_taken: int = 0
    history: tuple[IterationEntry, ...] = ()
    failure_kind: str = ""
    outcome: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------ Eigenschaften
    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATES

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    @property
    def really_failed(self) -> bool:
        """True nur, wenn nach dem Versagen *keine* Massnahme moeglich war.

        User-Regel: Ein Job, nach dessen Versagen das System in den
        autodidaktischen Modus geht (oder zumindest eine Massnahme identifiziert
        und am Budget scheitert), ist nicht "wirklich failed".
        """
        return self.status == JOB_FAILED and self.failure_kind == FAILURE_NO_MEASURE

    @property
    def iterations_left(self) -> int:
        return max(0, self.max_iterations - max(self.iteration, 0))

    def next_iteration(self) -> int:
        return max(1, self.iteration + (0 if self.iteration == 0 else 1))

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "goal": self.goal,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "mode": self.mode,
            "deadline_s": self.deadline_s,
            "limbs_used": list(self.limbs_used),
            "operations_used": list(self.operations_used),
            "measures_taken": self.measures_taken,
            "failure_kind": self.failure_kind,
            "outcome": dict(self.outcome),
            "history": [entry.to_dict() for entry in self.history],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "JobRecord":
        return cls(
            job_id=str(data.get("job_id", "")),
            goal=str(data.get("goal", "")),
            status=str(data.get("status", JOB_OPEN)),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            iteration=int(data.get("iteration", 0)),
            max_iterations=int(data.get("max_iterations", 1)),
            mode=str(data.get("mode", "dev")),
            deadline_s=float(data.get("deadline_s", 60.0)),
            limbs_used=tuple(str(x) for x in data.get("limbs_used", ())),
            operations_used=tuple(str(x) for x in data.get("operations_used", ())),
            measures_taken=int(data.get("measures_taken", 0)),
            failure_kind=str(data.get("failure_kind", "")),
            outcome=dict(data.get("outcome", {})),
            history=tuple(IterationEntry.from_dict(h) for h in data.get("history", ())),
        )


class JobStore:
    """Legt Jobs unter ``runtime/jobs/`` ab (JSON + JSONL-Historie)."""

    def __init__(self, config: NeuConfig | None = None) -> None:
        self.config = config or NeuConfig.load()
        self.config.ensure_dirs()

    # ------------------------------------------------------------------ Pfade
    def path(self, job_id: str) -> Path:
        return self.config.jobs_dir / f"{job_id}.json"

    def history_path(self, job_id: str) -> Path:
        return self.config.jobs_dir / f"{job_id}.history.jsonl"

    # ---------------------------------------------------------------- Anlegen
    def create(self, goal: str, *, max_iterations: int | None = None, deadline_s: float | None = None, job_id: str | None = None) -> JobRecord:
        cap = self.config.limits.max_iterations
        requested = int(max_iterations if max_iterations is not None else cap)
        effective = max(1, min(requested, cap, ABSOLUTE_MAX_ITERATIONS))
        now = format_timestamp(utc_now())
        record = JobRecord(
            job_id=job_id or new_id("job"),
            goal=goal.strip()[:4000],
            status=JOB_OPEN,
            created_at=now,
            updated_at=now,
            iteration=0,
            max_iterations=effective,
            mode=self.config.mode,
            deadline_s=float(deadline_s if deadline_s is not None else self.config.timer.deadline_s),
        )
        self.save(record)
        self._append_history(record.job_id, {"event": "job.created", "at": now, **record.to_dict()})
        return record

    def get(self, job_id: str) -> JobRecord | None:
        path = self.path(job_id)
        if not path.is_file():
            return None
        return JobRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def require(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(f"Job '{job_id}' existiert nicht (runtime/jobs/).")
        return record

    def save(self, record: JobRecord) -> JobRecord:
        stamped = replace(record, updated_at=format_timestamp(utc_now()))
        path = self.path(stamped.job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(stamped.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return stamped

    def list(self, *, limit: int = 25, active_only: bool = False) -> list[JobRecord]:
        if not self.config.jobs_dir.is_dir():
            return []
        records: list[JobRecord] = []
        for path in sorted(self.config.jobs_dir.glob("job_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                record = JobRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
            if active_only and not record.is_active:
                continue
            records.append(record)
            if len(records) >= limit:
                break
        return records

    def stale_after_s(self, record: JobRecord) -> float:
        """Ab wann ein aktiver Job als verwaist gilt (Prozessabsturz).

        Knapp bemessen: Ein Job, der laenger als sein Timer plus Puffer nicht
        aktualisiert wurde, blockiert im Dev-Modus sonst die ganze Pipeline.
        """
        return max(30.0, record.deadline_s + 25.0)

    def is_stale(self, record: JobRecord, *, now: datetime | None = None) -> bool:
        if not record.is_active or not record.updated_at:
            return False
        try:
            updated = parse_timestamp(record.updated_at, "$.updated_at")
        except Exception:  # noqa: BLE001 - unlesbarer Zeitstempel gilt als verwaist
            return True
        moment = now or utc_now()
        return (moment - updated).total_seconds() > self.stale_after_s(record)

    def active_jobs(self) -> list[JobRecord]:
        """Aktive Jobs ohne verwaiste (abgestuerzte) Eintraege."""
        return [record for record in self.list(limit=1000, active_only=True) if not self.is_stale(record)]

    def stale_jobs(self) -> list[JobRecord]:
        return [record for record in self.list(limit=1000, active_only=True) if self.is_stale(record)]

    def active_count(self) -> int:
        return len(self.active_jobs())

    def reclaim_stale(self) -> list[JobRecord]:
        """Verwaiste Jobs eskalieren statt sie ewig als 'aktiv' zu zaehlen."""
        reclaimed: list[JobRecord] = []
        for record in self.stale_jobs():
            updated = self.finish(
                record.job_id,
                JOB_ESCALATED,
                failure_kind=FAILURE_STALE,
                outcome={
                    "reason": "Job blieb ohne Abschluss im Zustand "
                    f"'{record.status}' (letzte Aktualisierung {record.updated_at}). "
                    "Vermutlich abgestuerzter Orchestrator-Prozess.",
                    "iterations": record.iteration,
                },
            )
            self._append_history(record.job_id, {"event": "job.reclaimed", "at": updated.updated_at})
            reclaimed.append(updated)
        return reclaimed

    # ------------------------------------------------------------- Fortschritt
    def begin_iteration(self, job_id: str, *, operation: str, limb: str) -> JobRecord:
        """Markiert den Start eines Durchgangs (Iteration zaehlt hier hoch)."""
        record = self.require(job_id)
        iteration = record.iteration + 1
        limbs = tuple(dict.fromkeys((*record.limbs_used, limb)))
        operations = tuple(dict.fromkeys((*record.operations_used, operation)))
        updated = replace(
            record,
            iteration=iteration,
            status=JOB_ITERATING if iteration > 1 else JOB_RUNNING,
            limbs_used=limbs,
            operations_used=operations,
        )
        saved = self.save(updated)
        self._append_history(job_id, {"event": "iteration.started", "iteration": iteration, "operation": operation, "limb": limb, "at": saved.updated_at})
        return saved

    def record_iteration(self, job_id: str, entry: IterationEntry) -> JobRecord:
        record = self.require(job_id)
        updated = replace(record, history=(*record.history, entry))
        saved = self.save(updated)
        self._append_history(job_id, {"event": "iteration.finished", **entry.to_dict(), "at": saved.updated_at})
        return saved

    def register_measure(self, job_id: str, measure: str) -> JobRecord:
        """Zaehlt eine ergriffene Massnahme -- der Job gilt damit nicht als failed."""
        record = self.require(job_id)
        updated = replace(record, measures_taken=record.measures_taken + 1, status=JOB_ITERATING)
        saved = self.save(updated)
        self._append_history(job_id, {"event": "measure.registered", "measure": measure, "count": saved.measures_taken, "at": saved.updated_at})
        return saved

    def finish(self, job_id: str, status: str, *, failure_kind: str = "", outcome: Mapping[str, Any] | None = None) -> JobRecord:
        if status not in TERMINAL_STATES:
            raise ValueError(f"finish() erwartet einen Terminalzustand, erhalten: {status!r}")
        record = self.require(job_id)
        updated = replace(record, status=status, failure_kind=failure_kind, outcome=dict(outcome or {}))
        saved = self.save(updated)
        self._append_history(job_id, {"event": "job.finished", "status": status, "failure_kind": failure_kind, "at": saved.updated_at})
        return saved

    def decide_after_failure(self, job_id: str, *, measure_available: bool, iteration: int) -> tuple[str, str]:
        """Kernregel: failed nur ohne Massnahme. Liefert (status, failure_kind).

        ``measure_available``  es existiert eine Loesungsidee (unabhaengig vom Budget)
        ``budget_left``        reicht das Iterations-Budget noch fuer einen Durchgang
        """
        record = self.require(job_id)
        budget_left = record.max_iterations - iteration
        if measure_available and budget_left > 0:
            return JOB_ITERATING, ""
        if measure_available:
            # Massnahme bekannt, aber kein Budget -> terminal, jedoch NICHT hilflos.
            return JOB_FAILED, FAILURE_BUDGET_EXHAUSTED
        return JOB_FAILED, FAILURE_NO_MEASURE

    # ------------------------------------------------------------------ Intern
    def _append_history(self, job_id: str, entry: Mapping[str, Any]) -> None:
        path = self.history_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(entry), ensure_ascii=False) + "\n")

    def read_history(self, job_id: str) -> list[dict[str, Any]]:
        path = self.history_path(job_id)
        if not path.is_file():
            return []
        entries: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


def summarize(record: JobRecord) -> str:
    """Einzeiler fuer CLI/Logs."""
    last = record.history[-1] if record.history else None
    tail = f" | letzter Durchgang: {last.status}/{last.verdict}" if last else ""
    return (
        f"{record.job_id} [{record.status}] '{record.goal[:60]}' "
        f"iter={record.iteration}/{record.max_iterations} massnahmen={record.measures_taken}"
        f"{f' failure={record.failure_kind}' if record.failure_kind else ''}{tail}"
    )
