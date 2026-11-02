"""Lauf-Modell fuer externe Agenten (Harness-Paket 2.1).

Ein Limb-Prozess bearbeitet genau einen Intent und soll kurz bleiben. Externe
Agenten laufen aber Minuten bis Stunden. Deshalb zerfaellt ein Lauf in kurze
Operationen, und der Zustand liegt auf der Platte:

    <limb>.start    legt den Lauf an und startet den Agenten
    <limb>.status   fragt den Stand ab und setzt Timeout und Budget durch
    <limb>.stop     beendet den Lauf, klappt auch ohne Freigabe
    <limb>.collect  holt Ergebnisse eines beendeten Laufs ab

Der Zustand steht unter ``runtime/agents/<run_id>/``:

    state.json      aktueller Stand, atomar geschrieben
    events.jsonl    Ereignisse, nur anhaengend
    result.json     Ergebnis aus ``collect``

Geheimnisse nennt der Limb in ``secrets()``. Alles, was auf die Platte oder in ein
Result geht, laeuft vorher durch ``redact``. Ergebnisse externer Agenten sind Daten:
Sie tragen ``untrusted: true`` und werden nie zu Prompts oder Freigaben.

Dieser Limb-Typ fragt nur ab, wenn er gerufen wird. Einen Waechter im Hintergrund
gibt es nicht, ``status`` muss also regelmaessig laufen (zum Beispiel per Trigger).
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # direkter Skriptaufruf durch den Orchestrator
    from base import LimbBase, LimbContext, LimbError  # type: ignore[import-not-found]
else:  # Import als Paket (Tests, Tooling)
    from limbs.base import LimbBase, LimbContext, LimbError

from core.protocol import ErrorCode, utc_now_iso

RUNNING = "running"
WAITING = "waiting"
SUCCEEDED = "succeeded"
FAILED = "failed"
STOPPED = "stopped"
TIMED_OUT = "timeout"
BUDGET_STOPPED = "budget_stopped"
TERMINAL_STATES = (SUCCEEDED, FAILED, STOPPED, TIMED_OUT, BUDGET_STOPPED)

MIN_POLL_S = 10.0
MAX_BACKOFF_S = 300.0
DEFAULT_MAX_RUNTIME_S = 3600.0
REDACTED = "[REDACTED]"

_RUN_ID = re.compile(r"^run_[0-9a-f]{20}$")


class ServiceDown(Exception):
    """Der Agent ist nicht erreichbar oder antwortet mit einem Fehler."""


def redact(value: Any, secrets: Iterable[str]) -> Any:
    """Ersetzt Geheimnisse rekursiv; greift auch in Schluesseln und Listen."""
    active = [secret for secret in secrets if secret]
    if isinstance(value, str):
        for secret in active:
            value = value.replace(secret, REDACTED)
        return value
    if isinstance(value, Mapping):
        return {redact(str(key), active): redact(item, active) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, active) for item in value]
    return value


def backoff_s(previous_s: float, *, floor_s: float = MIN_POLL_S) -> float:
    """Exponentiell mit Jitter, gedeckelt, nie unter dem Mindestabstand."""
    return min(MAX_BACKOFF_S, max(floor_s, previous_s) * 2) * random.uniform(1.0, 1.25)


@dataclass(frozen=True)
class Poll:
    """Was ein Agent bei einer Abfrage meldet."""

    state: str
    detail: Mapping[str, Any] | None = None


class RunStore:
    """Ablage der Laeufe unter ``runtime/agents/``."""

    def __init__(self, root: Path, secrets: Callable[[], Iterable[str]]) -> None:
        self.root = root
        self._secrets = secrets

    def path(self, run_id: str) -> Path:
        if not _RUN_ID.match(run_id):
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"Ungueltige run_id: {run_id!r}", hint="run_id aus <limb>.start verwenden.")
        return self.root / run_id

    def create(self, agent: str, **fields: Any) -> dict[str, Any]:
        run_id = f"run_{uuid.uuid4().hex[:20]}"
        now = time.time()
        run = {
            "run_id": run_id,
            "agent": agent,
            "state": RUNNING,
            "created_at": utc_now_iso(),
            "started_s": now,
            "next_poll_s": now,
            "backoff_s": 0.0,
            "failures": 0,
            **fields,
        }
        self.path(run_id).mkdir(parents=True, exist_ok=False)
        self.save(run)
        return run

    def load(self, run_id: str, agent: str) -> dict[str, Any]:
        path = self.path(run_id) / "state.json"
        if not path.is_file():
            raise LimbError(ErrorCode.TARGET_NOT_FOUND, f"Lauf {run_id} ist unbekannt.")
        run: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if run.get("agent") != agent:
            raise LimbError(ErrorCode.TARGET_NOT_FOUND, f"Lauf {run_id} gehoert nicht zu '{agent}'.")
        return run

    def save(self, run: Mapping[str, Any]) -> None:
        directory = self.path(str(run["run_id"]))
        target = directory / "state.json"
        temporary = directory / ".state.json.tmp"
        temporary.write_text(json.dumps(redact(run, self._secrets()), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)

    def event(self, run_id: str, kind: str, **payload: Any) -> None:
        line = json.dumps(redact({"at": utc_now_iso(), "kind": kind, **payload}, self._secrets()), ensure_ascii=False)
        with (self.path(run_id) / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def write_result(self, run_id: str, payload: Mapping[str, Any]) -> Path:
        path = self.path(run_id) / "result.json"
        path.write_text(json.dumps(redact(payload, self._secrets()), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


class AgentLimb(LimbBase):
    """Basis fuer Limbs, die einen externen Agenten fahren. Unterklassen liefern die Hooks."""

    max_runtime_s = DEFAULT_MAX_RUNTIME_S

    # ------------------------------------------------- von Unterklassen zu liefern
    def secrets(self) -> Iterable[str]:
        return ()

    def launch(self, params: Mapping[str, Any], ctx: LimbContext, run: dict[str, Any]) -> None:
        raise NotImplementedError

    def prepare(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        """Prueft den Auftrag, bevor ein Lauf entsteht; Rueckgabe landet im Lauf."""
        return {}

    def poll(self, run: dict[str, Any], ctx: LimbContext) -> Poll:
        raise NotImplementedError

    def halt(self, run: dict[str, Any], ctx: LimbContext) -> None:
        raise NotImplementedError

    def gather(self, run: dict[str, Any], ctx: LimbContext) -> dict[str, Any]:
        raise NotImplementedError

    def over_budget(self, run: dict[str, Any], poll: Poll, ctx: LimbContext) -> str:
        """Grund, wenn das Budget ueberschritten ist, sonst leer."""
        return ""

    # ----------------------------------------------------------------- Ablage
    @property
    def runs(self) -> RunStore:
        return RunStore(Path(self.config.runtime_dir) / "agents", self.secrets)

    def agent_handlers(self) -> dict[str, Callable[[Mapping[str, Any], LimbContext], Mapping[str, Any]]]:
        return {
            f"{self.name}.start": self._start,
            f"{self.name}.status": self._status,
            f"{self.name}.stop": self._stop,
            f"{self.name}.collect": self._collect,
        }

    def _load(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return self.runs.load(str(params.get("run_id", "")), self.name)

    def view(self, run: Mapping[str, Any]) -> dict[str, Any]:
        """Ausgabe fuer Aufrufer. Agentinhalte sind Daten."""
        view = {key: run[key] for key in ("run_id", "state", "created_at") if key in run}
        for key in ("confirmation", "error", "degraded"):
            if run.get(key):
                view[key] = run[key]
        if "stop_confirmed" in run:
            view["stop_confirmed"] = run["stop_confirmed"]
        view["terminal"] = run["state"] in TERMINAL_STATES
        view["next_poll_after_s"] = max(0.0, round(float(run.get("next_poll_s", 0.0)) - time.time(), 1))
        view["untrusted"] = True
        return view

    # ---------------------------------------------------------------- Handler
    def _stop_requested(self) -> bool:
        return (Path(self.config.runtime_dir) / "STOP").exists()

    def _start(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        if self._stop_requested():
            raise LimbError(ErrorCode.STOPPED, "Not-Aus aktiv (runtime/STOP).")

        fields = self.prepare(params, ctx)
        run = self.runs.create(self.name, **fields)
        self.runs.event(run["run_id"], "run.created")
        try:
            self.launch(params, ctx, run)
        except ServiceDown as exc:
            # Bewusst kein neuer Versuch: Ein Start kann trotz Fehler angekommen sein.
            self._finish(run, FAILED, error=f"Start fehlgeschlagen: {exc}")
            raise LimbError(ErrorCode.IO, f"Start fehlgeschlagen: {exc}", hint="Erst pruefen, ob der Agent doch laeuft, dann neu starten.") from exc
        self.runs.save(run)
        self.runs.event(run["run_id"], "run.started")
        return self.view(run)

    def _status(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        run = self._load(params)
        now = time.time()
        if self._stop_requested() and run["state"] not in TERMINAL_STATES:
            self._halt_and_finish(run, ctx, STOPPED, "Not-Aus aktiv (runtime/STOP).")
            return self.view(run)

        if run["state"] in TERMINAL_STATES or now < float(run["next_poll_s"]):
            return self.view(run)

        over_time = now - float(run["started_s"]) > float(run.get("max_runtime_s", self.max_runtime_s))
        try:
            poll = self.poll(run, ctx)
            reason = self.over_budget(run, poll, ctx)
        except ServiceDown as exc:
            run["failures"] = int(run["failures"]) + 1
            run["degraded"] = True
            run["backoff_s"] = backoff_s(float(run["backoff_s"]))
            run["next_poll_s"] = now + run["backoff_s"]
            self.runs.event(run["run_id"], "run.service_down", failures=run["failures"], reason=str(exc))
            if over_time:
                self._halt_and_finish(run, ctx, TIMED_OUT, "Laufzeit ueberschritten, Agent nicht erreichbar.")
            self.runs.save(run)
            return self.view(run)

        run.update(backoff_s=0.0, degraded=False, next_poll_s=now + MIN_POLL_S)
        run.pop("confirmation", None)
        if poll.state in TERMINAL_STATES:
            self._finish(run, poll.state, error=str((poll.detail or {}).get("error", "")))
        elif reason:
            self._halt_and_finish(run, ctx, BUDGET_STOPPED, reason)
        elif over_time:
            self._halt_and_finish(run, ctx, TIMED_OUT, "Laufzeit ueberschritten.")
        else:
            run["state"] = poll.state
            if poll.state == WAITING:
                # Rueckfragen entscheidet ein Mensch. Dieser Limb bestaetigt nie etwas.
                run["confirmation"] = dict(poll.detail or {})
                self.runs.event(run["run_id"], "run.waiting", detail=run["confirmation"])
            self.runs.save(run)
        return self.view(run)

    def _stop(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        run = self._load(params)
        if run["state"] not in TERMINAL_STATES:
            self._halt_and_finish(run, ctx, STOPPED, "Vom Aufrufer gestoppt.")
        return self.view(run)

    def _collect(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        run = self._load(params)
        if run["state"] not in TERMINAL_STATES:
            raise LimbError(ErrorCode.POLICY_DENIED, f"Lauf {run['run_id']} ist noch nicht beendet ({run['state']}).", hint="Erst status abfragen oder stop aufrufen.")
        try:
            payload = self.gather(run, ctx)
        except ServiceDown as exc:
            raise LimbError(ErrorCode.IO, f"Ergebnis nicht abholbar: {exc}", hint="Spaeter erneut versuchen, der Lauf bleibt erhalten.") from exc
        path = self.runs.write_result(run["run_id"], {"run_id": run["run_id"], "untrusted": True, **payload})
        if path.is_relative_to(self.config.repo_root):  # --runtime-dir darf ausserhalb liegen, Artefaktpfade nicht
            ctx.record(path, "create")
        self.runs.event(run["run_id"], "run.collected")

        self._log_system_run(run, payload)

        return {**redact(payload, self.secrets()), **self.view(run), "result_path": ctx.rel(path)}

    def _log_system_run(self, run: dict[str, Any], payload: dict[str, Any]) -> None:
        import re
        from core.protocol import utc_now_iso

        def _strip_control(v: Any) -> Any:
            if isinstance(v, str):
                return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', v)
            if isinstance(v, dict):
                return {str(k): _strip_control(val) for k, val in v.items()}
            if isinstance(v, list):
                return [_strip_control(i) for i in v]
            return v

        now = time.time()
        started = float(run.get("started_s", now))
        ended = float(run.get("ended_s", now))

        cost = payload.get("cost")
        artifacts = payload.get("artifacts", [])

        log_payload = {
            "run_id": run.get("run_id", ""),
            "agent": run.get("agent", self.name),
            "start": str(run.get("created_at", utc_now_iso())),
            "end": utc_now_iso(),
            "final_state": run.get("state", "unknown"),
            "runtime_s": round(ended - started, 3),
        }
        if "error" in run:
            log_payload["error"] = run["error"]
        if cost is not None:
            log_payload["cost"] = cost
        if isinstance(artifacts, list) and len(artifacts) > 0:
            log_payload["artifacts"] = len(artifacts)

        clean_payload = _strip_control(log_payload)
        safe_payload = redact(clean_payload, self.secrets())

        record = {
            "seq": 0,
            "timestamp": utc_now_iso(),
            "kind": "agent.run.summary",
            "job_id": str(run.get("run_id", "")),
            "trace_id": "",
            "intent_id": "",
            "limb": self.name,
            "clock_s": None,
            "payload": safe_payload
        }

        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            system_log = Path(self.config.runtime_dir) / "system.log"
            with system_log.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ Ablauf
    def _finish(self, run: dict[str, Any], state: str, *, error: str = "") -> None:
        run["state"] = state
        if error:
            run["error"] = error
        run.pop("confirmation", None)
        if "ended_s" not in run:
            run["ended_s"] = time.time()
        self.runs.save(run)
        self.runs.event(run["run_id"], "run.finished", state=state, error=error)

    def _halt_and_finish(self, run: dict[str, Any], ctx: LimbContext, state: str, reason: str) -> None:
        try:
            self.halt(run, ctx)
            run["stop_confirmed"] = True
        except (ServiceDown, LimbError) as exc:
            run["stop_confirmed"] = False
            self.runs.event(run["run_id"], "run.stop_failed", reason=str(exc))
            reason = f"{reason} Stopp nicht bestaetigt, der Agent kann weiterlaufen."
        self._finish(run, state, error=reason)
