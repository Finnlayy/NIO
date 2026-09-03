"""Orchestrator-Kern (Phase 1, Protokoll 1.1).

Verantwortung:

1. **Timer vor Anbeginn schaerfen** -- jeder Auftrag bekommt ``timer.armed_at``,
   ``soft_expires_at`` und ``expires_at``, *bevor* der Limb gestartet wird.
2. **Genau ein Limb pro Durchgang** -- kein stilles Retry. Ein Durchgang ist ein
   Agentenaufruf; Iterationen zaehlen pro Job.
3. **Statusbericht erzwingen** -- laeuft der Timer ab, liefert entweder der Limb
   selbst einen Bericht (Soft-Deadline) oder der Orchestrator synthetisiert
   einen vollstaendigen ``status="timeout"``-Datensatz.
4. **Autodidaktischer Modus** -- nach einem Fehlschlag entwirft
   ``orchestrator.planner`` den Auftrag fuer den 2. Durchgang. Erst wenn keine
   Massnahme moeglich oder das Budget (max 2, Dev-Modus 1) erschoepft ist, gilt
   ein Job als wirklich ``failed``.
5. **Skalierungsgrenzen** -- Agent-Slots (``max_agents``), Limb-Vielfalt pro Job
   (``max_limbs``), parallele Jobs (``max_concurrent_jobs``).

Ablauf eines Durchgangs::

    Intent validieren -> Limb im Register aufloesen -> Policy-Pre-Flight
    -> Timer schaerfen -> Agent-Slot belegen -> Intent in runtime/inbox/<limb>/
    -> Limb als Subprozess (Timeout = deadline_s + grace_s)
    -> Result parsen/validieren (bei Crash/Timeout: synthetisieren)
    -> Verdict durch den Kernel -> archivieren
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.config import NeuConfig
from core.job import (
    FAILURE_BUDGET_EXHAUSTED,
    FAILURE_ESCALATION,
    FAILURE_INTERNAL,
    FAILURE_NO_MEASURE,
    FAILURE_STALE,
    JOB_ESCALATED,
    JOB_FAILED,
    JOB_RESOLVED,
    IterationEntry,
    JobRecord,
    JobStore,
)
from core.kernel import Kernel, Verdict, arm_timer
from core.policy import Policy, PolicyDecision
from core.protocol import (
    ErrorCode,
    Intent,
    Operations,
    ProtocolError,
    Result,
    StatusReport,
    TimerReport,
    format_timestamp,
    new_id,
    utc_now,
    utc_now_iso,
)

from .events import CollectingSink, EventBus, build_event_bus
from .locks import AgentPool, NoSlotAvailable
from .planner import Diagnosis, IterationPlanner
from .transport import FileTransport, read_json, write_json_atomic


@dataclass(frozen=True)
class LimbSpec:
    name: str
    entrypoint: Path
    runtime: str
    version: str
    status: str
    phase: int
    operations: tuple[str, ...]
    writes_files: bool
    description: str

    @property
    def usable(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class Attempt:
    """Ein Durchgang: Auftrag, Ergebnis, Bewertung, Diagnose."""

    iteration: int
    intent: Intent
    result: Result
    verdict: Verdict
    decision: PolicyDecision
    spawned: bool = False
    returncode: int | None = None
    inbox_file: Path | None = None
    archive_dir: Path | None = None
    diagnosis: Diagnosis | None = None

    @property
    def ok(self) -> bool:
        return self.result.ok and self.verdict.accepted

    def summary(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "intent_id": self.intent.intent_id,
            "job_id": self.intent.job_id,
            "operation": self.intent.operation,
            "limb": self.intent.target_limb,
            "status": self.result.status,
            "verdict": self.verdict.decision,
            "reasons": list(self.verdict.reasons),
            "duration_ms": self.result.duration_ms,
            "timer": {
                "deadline_s": self.intent.timer.deadline_s,
                "soft_deadline_s": self.intent.timer.soft_deadline_s,
                "armed_at": self.intent.timer.armed_at,
                "expires_at": self.intent.timer.expires_at,
                "self_reported": self.result.timer.self_reported,
                "overrun_ms": self.result.timer.overrun_ms,
                "remaining_ms": self.result.timer.remaining_ms,
            },
            "status_report": self.result.status_report.to_dict() if self.result.status_report else None,
            "artifacts": [a.to_dict() for a in self.result.artifacts],
            "error": self.result.error,
            "output": self.result.output,
            "diagnosis": self.diagnosis.to_dict() if self.diagnosis else None,
            "archive": str(self.archive_dir) if self.archive_dir else None,
            "policy": self.decision.to_dict(),
        }


@dataclass(frozen=True)
class JobOutcome:
    """Endergebnis eines Jobs ueber alle Durchgaenge."""

    job: JobRecord
    attempts: tuple[Attempt, ...]
    status: str
    failure_kind: str = ""
    measures: int = 0

    @property
    def ok(self) -> bool:
        return self.status == JOB_RESOLVED

    @property
    def iterations(self) -> int:
        return len(self.attempts)

    def summary(self) -> dict[str, Any]:
        return {
            "job_id": self.job.job_id,
            "goal": self.job.goal,
            "status": self.status,
            "failure_kind": self.failure_kind,
            "mode": self.job.mode,
            "iterations": self.iterations,
            "max_iterations": self.job.max_iterations,
            "measures_taken": self.measures,
            "limbs_used": list(self.job.limbs_used),
            "really_failed": self.job.really_failed,
            "outcome": dict(self.job.outcome),
            "attempts": [a.summary() for a in self.attempts],
        }


class LimbRegistry:
    """Liest limbs/registry.json und haelt die Limb-Spezifikationen vor."""

    def __init__(self, config: NeuConfig) -> None:
        self.config = config
        self._raw: dict[str, Any] = {}
        self._runtimes: dict[str, Any] = {}
        self._limbs: dict[str, LimbSpec] = {}
        self.reload()

    def reload(self) -> None:
        path = self.config.registry_path
        if not path.is_file():
            raise ProtocolError(ErrorCode.TARGET_NOT_FOUND, f"Limb-Register fehlt: {path}")
        self._raw = read_json(path)
        self._runtimes = dict(self._raw.get("runtimes", {}))
        limbs = dict(self._raw.get("limbs", {}))
        self._limbs = {}
        for name, body in limbs.items():
            entrypoint = self.config.repo_root / str(body.get("entrypoint", ""))
            self._limbs[name] = LimbSpec(
                name=name,
                entrypoint=entrypoint,
                runtime=str(body.get("runtime", "python3")),
                version=str(body.get("version", "0.0.0")),
                status=str(body.get("status", "planned")),
                phase=int(body.get("phase", 0)),
                operations=tuple(str(op) for op in body.get("operations", ())),
                writes_files=bool(body.get("writes_files", False)),
                description=str(body.get("description", "")),
            )

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._limbs))

    def get(self, name: str) -> LimbSpec | None:
        return self._limbs.get(name)

    def active(self) -> tuple[LimbSpec, ...]:
        return tuple(spec for spec in self._limbs.values() if spec.usable and spec.entrypoint.is_file())

    def argv(self, spec: LimbSpec, *, intent_file: Path, iteration: int) -> list[str]:
        """Baut die Kommandozeile fuer einen Limb. Platzhalter: {python} {entrypoint}
        {intent_file} {iteration} {repo_root}."""
        template = self._runtimes.get(spec.runtime, {}).get("argv") or [
            "{python}", "{entrypoint}", "--intent", "{intent_file}", "--iteration", "{iteration}", "--profile", "{mode}",
        ]
        substitution = {
            "python": sys.executable,
            "entrypoint": str(spec.entrypoint),
            "intent_file": str(intent_file),
            "iteration": str(iteration),
            "attempt": str(iteration),  # Alias fuer aeltere Register-Eintraege
            "repo_root": str(self.config.repo_root),
            "mode": self.config.mode,
        }
        return [str(part).format(**substitution) for part in template]

    def as_dict(self) -> dict[str, Any]:
        return {
            "registry_version": self._raw.get("version"),
            "default_limb": self._raw.get("default_limb"),
            "limbs": {
                name: {
                    "entrypoint": self.config.relative(spec.entrypoint),
                    "runtime": spec.runtime,
                    "version": spec.version,
                    "status": spec.status,
                    "phase": spec.phase,
                    "operations": list(spec.operations),
                    "writes_files": spec.writes_files,
                    "entrypoint_exists": spec.entrypoint.is_file(),
                    "description": spec.description,
                }
                for name, spec in sorted(self._limbs.items())
            },
        }


class Orchestrator:
    """Verwaltet den Nachrichtenfluss zwischen Core, Dateisystem und Limbs."""

    def __init__(
        self,
        config: NeuConfig | None = None,
        *,
        kernel: Kernel | None = None,
        transport: FileTransport | None = None,
        bus: EventBus | None = None,
        registry: LimbRegistry | None = None,
        jobs: JobStore | None = None,
        planner: IterationPlanner | None = None,
        agents: AgentPool | None = None,
        collector: CollectingSink | None = None,
        quiet: bool = False,
    ) -> None:
        self.config = config or NeuConfig.load()
        self.config.ensure_dirs()
        self.operations = Operations.load(self.config.protocol_dir / "operations.json")
        self.kernel = kernel or Kernel(self.config, self.operations)
        self.policy: Policy = self.kernel.policy
        self.transport = transport or FileTransport(self.config)
        self.jobs = jobs or JobStore(self.config)
        self.registry = registry or LimbRegistry(self.config)
        self.planner = planner or IterationPlanner(self.kernel, self.config, self.registry)
        self.agents = agents or AgentPool(self.config)
        self.collector = collector
        self.bus = bus or build_event_bus(quiet=quiet, collector=collector)

    # =====================================================================
    # Job-Ebene: Ziel -> Durchgaenge -> Terminierung
    # =====================================================================
    def run_job(
        self,
        *,
        goal: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        limb: str = "echo",
        max_iterations: int | None = None,
        deadline_s: float | None = None,
        soft_deadline_s: float | None = None,
        grace_s: float | None = None,
        on_expiry: str = "iterate",
        on_failure: str = "autodidactic",
        title: str = "",
        objective: str = "",
        acceptance: Sequence[str] = (),
        verification: Mapping[str, Any] | None = None,
        constraints: Mapping[str, Any] | None = None,
        elevation: Mapping[str, Any] | None = None,
        context_summary: str = "",
        auto_iterate: bool = True,
    ) -> JobOutcome:
        """Fuehrt einen Job vollstaendig aus -- inklusive autodidaktischem 2. Durchgang."""
        reclaimed = self.reclaim_orphans()
        if reclaimed:
            self._emit("jobs.reclaimed", {"job_ids": [r.job_id for r in reclaimed]})
        active = self.jobs.active_count()
        if active >= self.config.limits.max_concurrent_jobs:
            raise ProtocolError(
                ErrorCode.POLICY_DENIED,
                f"Bereits {active} aktive Jobs; Profil '{self.config.mode}' erlaubt "
                f"max_concurrent_jobs={self.config.limits.max_concurrent_jobs}.",
            )

        job = self.jobs.create(goal, max_iterations=max_iterations, deadline_s=deadline_s)
        self._emit("job.created", {"goal": goal, "max_iterations": job.max_iterations, "mode": job.mode}, job_id=job.job_id, limb=limb)

        intent = self.kernel.build_intent(
            operation=operation,
            params=params,
            limb=limb,
            job_id=job.job_id,
            goal=goal,
            iteration=1,
            max_iterations=job.max_iterations,
            on_failure=on_failure,
            on_expiry=on_expiry,
            deadline_s=deadline_s if deadline_s is not None else job.deadline_s,
            soft_deadline_s=soft_deadline_s,
            grace_s=grace_s,
            title=title,
            objective=objective,
            acceptance=acceptance,
            verification=verification,
            constraints=constraints,
            elevation=elevation,
            context_summary=context_summary,
        )
        return self._execute_job(job.job_id, intent, auto_iterate=auto_iterate)

    def continue_job(self, job_id: str, intent: Intent, *, auto_iterate: bool = True) -> JobOutcome:
        """Setzt einen bestehenden Job mit einem vom Core entworfenen Intent fort."""
        return self._execute_job(job_id, intent, auto_iterate=auto_iterate)

    def reclaim_orphans(self) -> list[JobRecord]:
        """Aktive Jobs ohne lebenden Agent-Slot sind Waisen (abgestuerzter Lauf).

        Sie werden eskaliert statt die Pipeline zu blockieren -- im Dev-Modus mit
        ``max_concurrent_jobs=1`` waere sonst jeder Absturz ein Stillstand.
        """
        live = {slot.job_id for slot in self.agents.busy() if not self.agents.is_stale(slot)}
        orphans: list[JobRecord] = []
        for record in self.jobs.list(limit=1000, active_only=True):
            if record.job_id in live:
                continue
            if not self.jobs.is_stale(record):
                continue
            orphans.append(
                self.jobs.finish(
                    record.job_id,
                    JOB_ESCALATED,
                    failure_kind=FAILURE_STALE,
                    outcome={
                        "reason": "Job war aktiv, hielt aber keinen Agent-Slot mehr und wurde "
                        f"seit {record.updated_at} nicht aktualisiert.",
                        "iterations": record.iteration,
                    },
                )
            )
        return orphans

    def _execute_job(self, job_id: str, intent: Intent, *, auto_iterate: bool) -> JobOutcome:
        try:
            return self._execute_job_loop(job_id, intent, auto_iterate=auto_iterate)
        except Exception as exc:  # noqa: BLE001 - kein Job darf als Waise zurueckbleiben
            record = self.jobs.get(job_id)
            if record is not None and record.is_active:
                self.jobs.finish(
                    job_id,
                    JOB_ESCALATED,
                    failure_kind=FAILURE_INTERNAL,
                    outcome={"reason": f"{type(exc).__name__}: {exc}", "iterations": record.iteration},
                )
            self._emit("job.aborted", {"error": f"{type(exc).__name__}: {exc}"}, job_id=job_id)
            raise

    def _execute_job_loop(self, job_id: str, intent: Intent, *, auto_iterate: bool) -> JobOutcome:
        attempts: list[Attempt] = []
        current = intent
        job = self.jobs.require(job_id)

        while True:
            job = self.jobs.begin_iteration(job_id, operation=current.operation, limb=current.target_limb)
            self._emit(
                "job.iteration.started",
                {"iteration": job.iteration, "max_iterations": job.max_iterations, "operation": current.operation, "limb": current.target_limb},
                current,
                job_id=job_id,
            )

            attempt = self.dispatch(current, job=job)
            attempts.append(attempt)

            job = self.jobs.record_iteration(
                job_id,
                IterationEntry(
                    iteration=attempt.iteration,
                    intent_id=attempt.intent.intent_id,
                    operation=attempt.intent.operation,
                    limb=attempt.intent.target_limb,
                    status=attempt.result.status,
                    verdict=attempt.verdict.decision,
                    error_code=attempt.result.error_code,
                    duration_ms=attempt.result.duration_ms,
                    timer_expired=attempt.verdict.timer_expired,
                    self_reported=attempt.result.timer.self_reported,
                    archive=self.config.relative(attempt.archive_dir) if attempt.archive_dir else "",
                    measure="",
                ),
            )

            if attempt.ok:
                job = self.jobs.finish(
                    job_id,
                    JOB_RESOLVED,
                    outcome={
                        "intent_id": attempt.intent.intent_id,
                        "iteration": attempt.iteration,
                        "artifacts": [a.to_dict() for a in attempt.result.artifacts],
                        "duration_ms": sum(a.result.duration_ms for a in attempts),
                    },
                )
                self._emit("job.finished", {"status": JOB_RESOLVED, "iterations": len(attempts)}, attempt.intent, job_id=job_id)
                return JobOutcome(job=job, attempts=tuple(attempts), status=JOB_RESOLVED, measures=job.measures_taken)

            diagnosis = self.planner.diagnose(attempt.intent, attempt.result, attempt.verdict)
            measure_available = self.planner.measure_available(diagnosis)
            has_budget, budget_reason = self.planner.budget_available(attempt.intent)
            can_plan, reason = self.planner.can_plan(attempt.intent, attempt.result, attempt.verdict, diagnosis=diagnosis)
            self._emit(
                "job.diagnosed",
                {
                    "diagnosis": diagnosis.to_dict(),
                    "measure_available": measure_available,
                    "budget_available": has_budget,
                    "budget_reason": budget_reason,
                    "can_iterate": can_plan,
                    "reason": reason,
                },
                attempt.intent,
                job_id=job_id,
            )

            if can_plan and auto_iterate and attempt.intent.job.on_failure == "autodidactic":
                # Massnahme ergriffen -> der Job ist per Definition NICHT failed.
                job = self.jobs.register_measure(job_id, diagnosis.measure)
                self._emit("job.measure", {"measure": diagnosis.measure[:600], "count": job.measures_taken}, attempt.intent, job_id=job_id)
                current = self.planner.compose(attempt.intent, attempt.result, attempt.verdict, diagnosis=diagnosis)
                self._emit(
                    "job.iteration.planned",
                    {"next_intent_id": current.intent_id, "iteration": current.iteration, "operation": current.operation},
                    current,
                    job_id=job_id,
                )
                continue

            if diagnosis.escalate:
                status, kind = JOB_ESCALATED, FAILURE_ESCALATION
                outcome = {"reason": diagnosis.escalation_reason or reason, "diagnosis": diagnosis.to_dict()}
            elif can_plan and not auto_iterate:
                status, kind = JOB_ESCALATED, FAILURE_ESCALATION
                outcome = {"reason": "auto_iterate=false: Massnahme identifiziert, aber nicht ausgefuehrt.", "measure": diagnosis.measure}
            else:
                status, kind = self.jobs.decide_after_failure(job_id, measure_available=measure_available, iteration=attempt.iteration)
                outcome = {
                    "reason": reason,
                    "measure_available": measure_available,
                    "budget_available": has_budget,
                    "identified_measure": diagnosis.measure,
                    "diagnosis": diagnosis.to_dict(),
                    "measures_taken": job.measures_taken,
                }

            job = self.jobs.finish(job_id, status, failure_kind=kind, outcome=outcome)
            self._emit(
                "job.finished",
                {"status": status, "failure_kind": kind, "iterations": len(attempts), "measures_taken": job.measures_taken},
                attempt.intent,
                job_id=job_id,
            )
            return JobOutcome(job=job, attempts=tuple(attempts), status=status, failure_kind=kind, measures=job.measures_taken)

    # =====================================================================
    # Durchgangs-Ebene: ein Intent -> ein Result
    # =====================================================================
    def dispatch(self, intent: Intent, *, job: JobRecord | None = None) -> Attempt:
        """Ein einzelner Durchgang. Kein Retry -- Retries sind Job-Iterationen."""
        job_record = job or self.jobs.get(intent.job_id)
        if job_record is None:
            job_record = self.jobs.create(
                intent.job.goal or intent.operation,
                max_iterations=intent.job.max_iterations,
                deadline_s=intent.timer.deadline_s,
                job_id=intent.job_id,
            )
            job_record = self.jobs.begin_iteration(job_record.job_id, operation=intent.operation, limb=intent.target_limb)

        self._emit(
            "intent.accepted",
            {
                "operation": intent.operation,
                "limb": intent.target_limb,
                "iteration": intent.iteration,
                "elevation": intent.elevation.level,
                "deadline_s": intent.timer.deadline_s,
            },
            intent,
            job_id=intent.job_id,
        )

        spec = self.registry.get(intent.target_limb)
        if spec is None:
            return self._short_circuit(intent, ErrorCode.TARGET_NOT_FOUND, f"Limb '{intent.target_limb}' ist nicht in limbs/registry.json registriert.", hint=f"Bekannte Limbs: {', '.join(self.registry.names())}")
        if not spec.usable:
            return self._short_circuit(intent, ErrorCode.TARGET_NOT_FOUND, f"Limb '{intent.target_limb}' hat Status '{spec.status}' und darf nicht gestartet werden.", hint="Status in limbs/registry.json auf 'active' setzen, sobald der Limb implementiert ist.")
        if not spec.entrypoint.is_file():
            return self._short_circuit(intent, ErrorCode.TARGET_NOT_FOUND, f"Entrypoint fehlt: {self.config.relative(spec.entrypoint)}", hint="Register und Dateisystem stimmen nicht ueberein.")

        decision = self.policy.check(intent, job=job_record)
        self._emit("policy.decided", decision.to_dict(), intent, job_id=intent.job_id)
        if not decision.allowed:
            return self._short_circuit(intent, decision.code, decision.reason, decision=decision, hint="Intent anpassen (Rechte, Pfade, Operation, Budget).")

        # ---- Timer VOR Anbeginn schaerfen ----
        armed_intent = arm_timer(intent, config=self.config)
        self._emit(
            "timer.armed",
            {
                "armed_at": armed_intent.timer.armed_at,
                "soft_expires_at": armed_intent.timer.soft_expires_at,
                "expires_at": armed_intent.timer.expires_at,
                "deadline_s": armed_intent.timer.deadline_s,
                "soft_deadline_s": armed_intent.timer.soft_deadline_s,
                "grace_s": armed_intent.timer.grace_s,
                "hard_timeout_s": armed_intent.timer.hard_timeout_s(),
            },
            armed_intent,
            job_id=armed_intent.job_id,
        )

        # ---- Agent-Slot (Dev-Modus: genau einer) ----
        try:
            slot = self.agents.acquire(job_id=armed_intent.job_id, ttl_s=armed_intent.timer.hard_timeout_s() + 5.0)
        except NoSlotAvailable as exc:
            return self._short_circuit(
                armed_intent,
                ErrorCode.POLICY_DENIED,
                str(exc),
                hint=f"Profil anheben (orchestrator scale --profile scale --approved-by human) oder warten. Belegt: {json.dumps(exc.busy, ensure_ascii=False)}",
            )
        self._emit("agent.lock.acquired", slot.to_dict(), armed_intent, job_id=armed_intent.job_id)

        try:
            inbox_file = self.transport.submit(armed_intent, iteration=armed_intent.iteration)
            result, spawned, returncode = self._spawn(spec, armed_intent, inbox_file=inbox_file)
        finally:
            self.agents.release(slot)
            self._emit("agent.lock.released", {"index": slot.index}, armed_intent, job_id=armed_intent.job_id)

        self._emit(
            "result.recorded",
            {
                "status": result.status,
                "iteration": result.iteration,
                "duration_ms": result.duration_ms,
                "artifacts": [a.to_dict() for a in result.artifacts],
                "status_report": result.status_report.to_dict() if result.status_report else None,
                "error": result.error,
            },
            armed_intent,
            job_id=armed_intent.job_id,
            limb=spec.name,
        )

        verdict = self.kernel.evaluate(armed_intent, result)
        self._emit("result.verdict", {"decision": verdict.decision, "reasons": list(verdict.reasons), "next_action": verdict.next_action}, armed_intent, job_id=armed_intent.job_id, limb=spec.name)

        archive_dir = self.transport.archive(armed_intent, result, {"verdict": verdict.to_dict(), "iteration": armed_intent.iteration})
        self._emit("transport.archived", {"dir": self.config.relative(archive_dir)}, armed_intent, job_id=armed_intent.job_id, limb=spec.name)

        # Die Inbox-Datei ist zugestellt und archiviert -> weg damit, sonst wuerde
        # `loop --once` denselben Durchgang erneut ausfuehren.
        self.transport.consume(inbox_file)

        diagnosis = None if verdict.accepted else self.planner.diagnose(armed_intent, result, verdict)

        return Attempt(
            iteration=armed_intent.iteration,
            intent=armed_intent,
            result=result,
            verdict=verdict,
            decision=decision,
            spawned=spawned,
            returncode=returncode,
            inbox_file=inbox_file,
            archive_dir=archive_dir,
            diagnosis=diagnosis,
        )

    def dispatch_raw(self, raw: str | bytes | Mapping[str, Any]) -> Attempt:
        if isinstance(raw, Mapping):
            intent = Intent.from_dict(dict(raw), operations=self.operations)
        else:
            intent = Intent.from_json(raw, operations=self.operations)
        return self.dispatch(intent)

    def dispatch_file(self, path: Path | str) -> Attempt:
        file_path = Path(path)
        if not file_path.is_file():
            raise ProtocolError(ErrorCode.PATH_NOT_FOUND, f"Intent-Datei nicht gefunden: {file_path}")
        return self.dispatch_raw(file_path.read_text(encoding="utf-8"))

    def run_inbox_once(self, *, consume: bool = True) -> list[Attempt]:
        """Abarbeitungs-Modus: alle offenen Intents der Inboxen dispatchen."""
        attempts: list[Attempt] = []
        for pending in self.transport.drain_inbox():
            try:
                attempt = self.dispatch_file(pending)
            except ProtocolError as exc:
                self._emit("inbox.rejected", {"file": str(pending), "code": exc.code, "message": exc.message})
                continue
            attempts.append(attempt)
            if consume:
                self.transport.consume(pending)
        self._emit("loop.tick", {"processed": len(attempts)})
        return attempts

    # =====================================================================
    # Intern
    # =====================================================================
    def _spawn(self, spec: LimbSpec, intent: Intent, *, inbox_file: Path) -> tuple[Result, bool, int | None]:
        argv = self.registry.argv(spec, intent_file=inbox_file, iteration=intent.iteration)
        env = {**os.environ, "NEU_ROOT": str(self.config.repo_root), "PYTHONIOENCODING": "utf-8"}
        started_at = utc_now_iso()
        hard_timeout = intent.timer.hard_timeout_s()
        self._emit("limb.spawned", {"argv": argv, "hard_timeout_s": hard_timeout}, intent, job_id=intent.job_id, limb=spec.name)

        try:
            completed = subprocess.run(
                argv,
                cwd=str(self.config.repo_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=hard_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _decode(exc.stdout)
            stderr = _decode(exc.stderr)
            result = self._timeout_result(intent, started_at, stdout=stdout, stderr=stderr, hard_kill=True)
            self._emit("timer.expired", {"hard_kill": True, "after_s": hard_timeout}, intent, job_id=intent.job_id, limb=spec.name)
            return result, True, None
        except (OSError, ValueError) as exc:
            result = self._synthetic(
                intent,
                "failed",
                ErrorCode.LIMB_CRASH,
                f"Limb konnte nicht gestartet werden: {exc}",
                hint="Entrypoint und Laufzeitumgebung pruefen.",
                started_at=started_at,
            )
            return result, False, None

        parsed = _extract_json_object(completed.stdout)
        if parsed is None:
            overrun = _overrun_ms(intent)
            if overrun > 0:
                # Limb wurde vermutlich von der eigenen Uhr gestoppt, lieferte aber nichts
                self._emit("timer.expired", {"hard_kill": False, "overrun_ms": overrun}, intent, job_id=intent.job_id, limb=spec.name)
                return self._timeout_result(intent, started_at, stdout=completed.stdout, stderr=completed.stderr, hard_kill=False, exit_code=completed.returncode), True, completed.returncode
            result = self._synthetic(
                intent,
                "failed",
                ErrorCode.LIMB_CRASH,
                f"Limb lieferte kein gueltiges Result auf stdout (exit={completed.returncode}).",
                hint="Ein Limb darf auf stdout nur genau ein JSON-Objekt schreiben; Logs gehoeren nach stderr.",
                started_at=started_at,
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
            )
            return result, True, completed.returncode

        try:
            result = Result.from_dict(parsed, intent=intent)
        except ProtocolError as exc:
            return (
                self._synthetic(
                    intent,
                    "rejected",
                    exc.code,
                    f"Result des Limbs verletzt das Protokoll: {exc.message}",
                    hint=f"Pfad {exc.path}",
                    started_at=started_at,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    exit_code=completed.returncode,
                ),
                True,
                completed.returncode,
            )

        if completed.returncode != 0 and result.status == "success":
            result = Result.from_dict(
                {
                    **result.to_dict(),
                    "status": "failed",
                    "error": {
                        "code": ErrorCode.LIMB_CRASH,
                        "message": f"Limb meldete Erfolg, beendete sich aber mit Exit-Code {completed.returncode}.",
                        "hint": "stderr pruefen.",
                    },
                    "diagnostics": {**result.to_dict()["diagnostics"], "exit_code": completed.returncode},
                },
                intent=intent,
            )
        return result, True, completed.returncode

    def _timeout_result(self, intent: Intent, started_at: str, *, stdout: str, stderr: str, hard_kill: bool, exit_code: int | None = None) -> Result:
        """Statusbericht bei Timer-Ablauf -- vom Orchestrator erzwungen."""
        now = utc_now()
        expires = intent.timer.expires_at
        overrun = _overrun_ms(intent, now=now)
        explanation = (
            f"Timer abgelaufen: Budget {intent.timer.deadline_s}s (soft {intent.timer.soft_deadline_s}s) war ausgeschöpft, "
            f"als der Orchestrator den Durchgang {'hart abbrach' if hard_kill else 'als ueberzogen erkannte'}. "
            f"Der Limb hat in diesem Durchgang {'keinen' if hard_kill else 'keinen vollstaendigen'} Abschlussbericht geliefert."
        )
        report = StatusReport(
            state="timeout",
            explanation=explanation,
            done=("Timer wurde vor Anbeginn geschaerft und ueberwacht.",),
            remaining=(
                f"Auftrag '{intent.task.title or intent.operation}' ist in einem Durchgang nicht abschliessbar.",
                "Offener Umfang muss im naechsten Durchgang verkleinert werden.",
            ),
            blockers=(
                {
                    "code": ErrorCode.TIMEOUT,
                    "message": f"Zeitbudget {intent.timer.deadline_s}s ueberschritten (Ueberzug {overrun} ms).",
                    "hint": "deadline_s anheben oder Auftrag in kleinere, pruefbare Schritte teilen.",
                },
            ),
            suggested_next="Zweiter Durchgang mit verkleinertem Umfang und angepasstem Timer.",
        )
        payload = {
            "protocol": "neu/result",
            "version": "1.1",
            "result_id": new_id("res"),
            "intent_id": intent.intent_id,
            "trace_id": intent.trace_id,
            "job_id": intent.job_id,
            "iteration": intent.iteration,
            "status": "timeout",
            "operation": intent.operation,
            "limb": {"name": intent.target_limb, "version": "0.0.0", "pid": 0},
            "started_at": started_at,
            "finished_at": format_timestamp(now),
            "duration_ms": max(0, int((now - _parse_or_now(intent.timer.armed_at)).total_seconds() * 1000)),
            "output": {"synthesized_by": "orchestrator", "hard_kill": hard_kill},
            "artifacts": [],
            "status_report": report.to_dict(),
            "timer": {
                "armed_at": intent.timer.armed_at,
                "expires_at": expires,
                "reported_at": format_timestamp(now),
                "remaining_ms": -overrun,
                "overrun_ms": overrun,
                "self_reported": False,
            },
            "diagnostics": {"stdout": stdout[-65536:], "stderr": stderr[-65536:], "exit_code": exit_code},
            "error": {
                "code": ErrorCode.TIMEOUT,
                "message": explanation,
                "hint": "Autodidaktischer Modus entwirft den zweiten Durchgang.",
            },
            "self_report": {"confidence": 0.0, "notes": "Vom Orchestrator erzwungener Statusbericht nach Timer-Ablauf."},
        }
        return Result.from_dict(payload, intent=intent)

    def _short_circuit(self, intent: Intent, code: str, message: str, *, hint: str = "", decision: PolicyDecision | None = None) -> Attempt:
        """Erzeugt ein abgelehntes Result, ohne einen Limb zu starten."""
        result = self._synthetic(intent, "rejected", code, message, hint=hint)
        policy_decision = decision or PolicyDecision(allowed=False, code=code, reason=message)
        verdict = self.kernel.evaluate(intent, result)
        self._emit("intent.rejected", {"code": code, "message": message, "verdict": verdict.decision}, intent, job_id=intent.job_id, limb=intent.target_limb)
        archive_dir = self.transport.archive(intent, result, {"verdict": verdict.to_dict(), "rejected_before_spawn": True})
        diagnosis = self.planner.diagnose(intent, result, verdict)
        return Attempt(
            iteration=intent.iteration,
            intent=intent,
            result=result,
            verdict=verdict,
            decision=policy_decision,
            spawned=False,
            archive_dir=archive_dir,
            diagnosis=diagnosis,
        )

    def _synthetic(
        self,
        intent: Intent,
        status: str,
        code: str,
        message: str,
        *,
        hint: str = "",
        started_at: str | None = None,
        stdout: str = "",
        stderr: str = "",
        exit_code: int | None = None,
        report: StatusReport | None = None,
    ) -> Result:
        """Vom Orchestrator erzeugtes Result -- immer protokollkonform."""
        now = utc_now_iso()
        payload: dict[str, Any] = {
            "protocol": "neu/result",
            "version": "1.1",
            "result_id": new_id("res"),
            "intent_id": intent.intent_id,
            "trace_id": intent.trace_id,
            "job_id": intent.job_id,
            "iteration": intent.iteration,
            "status": status,
            "operation": intent.operation,
            "limb": {"name": intent.target_limb, "version": "0.0.0", "pid": 0},
            "started_at": started_at or now,
            "finished_at": now,
            "duration_ms": 0,
            "output": {"synthesized_by": "orchestrator"},
            "artifacts": [],
            "timer": {
                "armed_at": intent.timer.armed_at,
                "expires_at": intent.timer.expires_at,
                "reported_at": now,
                "remaining_ms": int((intent.timer.remaining_s() or 0.0) * 1000) if intent.timer.armed else 0,
                "overrun_ms": 0,
                "self_reported": False,
            },
            "diagnostics": {"stdout": stdout[-65536:], "stderr": stderr[-65536:], "exit_code": exit_code},
            "error": {"code": code, "message": message[:16000], "hint": hint[:4000]},
            "self_report": {"confidence": 0.0, "notes": "Vom Orchestrator synthetisiert (kein Limb-Erfolg)."},
        }
        if report is not None:
            payload["status_report"] = report.to_dict()
        if status == "partial" and report is None:
            payload["status_report"] = StatusReport(state="partial", explanation=message[:4000], remaining=("Teilauftrag offen.",)).to_dict()
        return Result.from_dict(payload, intent=intent)

    def _emit(self, kind: str, payload: Mapping[str, Any] | None = None, intent: Intent | None = None, *, job_id: str = "", limb: str = "") -> None:
        self.bus.emit(
            kind,
            payload or {},
            job_id=job_id or (intent.job_id if intent else ""),
            trace_id=intent.trace_id if intent else "",
            intent_id=intent.intent_id if intent else "",
            limb=limb or (intent.target_limb if intent else ""),
        )


def _decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _parse_or_now(value: str | None):
    from core.protocol import parse_timestamp

    if not value:
        return utc_now()
    try:
        return parse_timestamp(value, "$.timer.armed_at")
    except ProtocolError:
        return utc_now()


def _overrun_ms(intent: Intent, *, now=None) -> int:
    """Millisekunden ueber der harten Deadline (0 = noch im Budget)."""
    if not intent.timer.expires_at:
        return 0
    moment = now or utc_now()
    deadline = _parse_or_now(intent.timer.expires_at)
    delta = (moment - deadline).total_seconds() * 1000
    return int(max(0, delta))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Findet das Result-JSON-Objekt im stdout eines Limbs.

    Toleriert versehentliche Zusaetze, nimmt aber immer das *letzte* vollstaendige
    Objekt mit ``protocol == "neu/result"`` -- das ist per Vertrag das Result.
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(obj, dict):
            candidates.append(obj)
        index = start + max(1, end)
    for candidate in reversed(candidates):
        if candidate.get("protocol") == "neu/result":
            return candidate
    return candidates[-1] if candidates else None
