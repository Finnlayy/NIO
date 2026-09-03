"""Kommandozeilen- und I/O-Schnittstelle des Orchestrators (Phase 1).

Der KI-Kern (und der Mensch) steuert das System ueber diese CLI:

    python3 -m orchestrator spec                 # Protokoll + Operationen + Timer-Semantik
    python3 -m orchestrator status               # Profil, Limits, Queues, Jobs, Agent-Slots
    python3 -m orchestrator job run --goal ... --op sys.echo --params '{"message":"hi"}'
    python3 -m orchestrator job show <job_id>    # Historie inkl. Statusberichten
    python3 -m orchestrator dispatch --intent runtime/inbox/echo/<id>.json
    python3 -m orchestrator intent --op sys.ping --limb echo --print
    python3 -m orchestrator validate --intent <datei>
    python3 -m orchestrator loop --once          # Inbox abarbeiten
    python3 -m orchestrator scale --profile scale --approved-by human

Konvention: **stdout** traegt das Ergebnis (Menschen oder ``--json``),
**stderr** traegt die Events des Event-Bus (JSON-Zeilen). Damit bleibt alles
pipe-faehig: ``python3 -m orchestrator job run ... --json | jq .status``.

Exit-Codes: 0 = Erfolg, 1 = Protokoll-/Validierungsfehler, 2 = Job nicht
aufgeloest (failed/escalated), 3 = Nutzungsfehler.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.config import ABSOLUTE_MAX_ITERATIONS, SCALE_PROFILES, NeuConfig  # noqa: E402
from core.job import JOB_RESOLVED, JobRecord, JobStore, summarize  # noqa: E402
from core.protocol import (  # noqa: E402
    PROTOCOL_INTENT,
    PROTOCOL_RESULT,
    PROTOCOL_VERSION,
    ErrorCode,
    Intent,
    Operations,
    ProtocolError,
    Result,
)

from .runner import Attempt, JobOutcome, Orchestrator  # noqa: E402
from .transport import FileTransport  # noqa: E402

EXIT_OK = 0
EXIT_PROTOCOL = 1
EXIT_JOB_FAILED = 2
EXIT_USAGE = 3


# --------------------------------------------------------------------------- #
# Ausgabe-Helfer
# --------------------------------------------------------------------------- #
def _say(text: str = "") -> None:
    print(text)


def _kv(key: str, value: Any, indent: int = 0) -> None:
    print(f"{' ' * indent}{key:<22} {value}")


def _rule(char: str = "-", width: int = 78) -> None:
    print(char * width)


def _dump(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _config_from_args(args: argparse.Namespace) -> NeuConfig:
    overrides: dict[str, Any] = {}
    if getattr(args, "repo_root", None):
        overrides["repo_root"] = Path(args.repo_root)
    profile = getattr(args, "mode", None)
    if profile:
        if profile not in SCALE_PROFILES:
            raise SystemExit(f"[usage] Unbekanntes Profil '{profile}'. Erlaubt: {', '.join(SCALE_PROFILES)}")
        overrides["mode"] = profile
        overrides["limits"] = dict(SCALE_PROFILES[profile])
    return NeuConfig.load(**overrides)


def _orchestrator(args: argparse.Namespace) -> Orchestrator:
    config = _config_from_args(args)
    return Orchestrator(config, quiet=bool(getattr(args, "quiet", False)))


def _print_attempt(attempt: Attempt, *, json_mode: bool) -> None:
    if json_mode:
        _dump(attempt.summary())
        return
    result = attempt.result
    report = result.status_report
    _rule("=")
    _kv("Durchgang", f"{attempt.iteration}/{attempt.intent.job.max_iterations}  (Job {attempt.intent.job_id})")
    _kv("Intent", attempt.intent.intent_id)
    _kv("Operation", f"{attempt.intent.operation}  ->  Limb '{attempt.intent.target_limb}'")
    _kv("Timer", f"deadline={attempt.intent.timer.deadline_s}s soft={attempt.intent.timer.soft_deadline_s}s "
                 f"armed_at={attempt.intent.timer.armed_at} expires_at={attempt.intent.timer.expires_at}")
    _kv("Ergebnis", f"status={result.status}  dauer={result.duration_ms} ms  exit={result.diagnostics_exit_code}")
    _kv("Timer-Report", f"self_reported={result.timer.self_reported} remaining_ms={result.timer.remaining_ms} overrun_ms={result.timer.overrun_ms}")
    _kv("Verdict", f"{attempt.verdict.decision}  next={attempt.verdict.next_action}")
    if result.error:
        _kv("Fehler", f"{result.error['code']}: {result.error['message'][:200]}")
        if result.error.get("hint"):
            _kv("Hinweis", result.error["hint"][:200], indent=2)
    if report:
        _kv("Statusbericht", f"state={report.state}")
        _kv("Erklaerung", report.explanation[:400], indent=2)
        if report.done:
            _kv("Erledigt", "; ".join(report.done)[:300], indent=2)
        if report.remaining:
            _kv("Offen", "; ".join(report.remaining)[:300], indent=2)
        if report.suggested_next:
            _kv("Vorschlag", report.suggested_next[:300], indent=2)
    if result.artifacts:
        _kv("Artefakte", f"{len(result.artifacts)}")
        for artifact in result.artifacts[:10]:
            print(f"  - {artifact.action:<9} {artifact.path} ({artifact.bytes} B, sha {artifact.sha256[:12]}…)")
    if attempt.diagnosis is not None:
        _kv("Diagnose", attempt.diagnosis.code)
        _kv("Ursache", attempt.diagnosis.cause[:300], indent=2)
        _kv("Massnahme", attempt.diagnosis.measure[:300], indent=2)
    if attempt.verdict.reasons:
        _kv("Begruendung", " | ".join(r[:160] for r in attempt.verdict.reasons[:4]))
    if attempt.verdict.warnings:
        _kv("Hinweise (weich)", " | ".join(w[:200] for w in attempt.verdict.warnings[:3]))
    if attempt.archive_dir:
        _kv("Archiv", str(attempt.archive_dir))
    _rule("=")


def _print_outcome(outcome: JobOutcome, *, json_mode: bool) -> None:
    if json_mode:
        _dump(outcome.summary())
        return
    for attempt in outcome.attempts:
        _print_attempt(attempt, json_mode=False)
    _rule("=")
    _kv("Job", outcome.job.job_id)
    _kv("Ziel", outcome.job.goal[:120])
    _kv("Status", outcome.status + (f" ({outcome.failure_kind})" if outcome.failure_kind else ""))
    _kv("Durchgaenge", f"{outcome.iterations}/{outcome.job.max_iterations}  (Profil {outcome.job.mode})")
    _kv("Massnahmen", outcome.job.measures_taken)
    _kv("Wirklich failed", "ja" if outcome.job.really_failed else "nein")
    _kv("Genutzte Limbs", ", ".join(outcome.job.limbs_used) or "-")
    if outcome.job.outcome:
        _kv("Outcome", json.dumps(outcome.job.outcome, ensure_ascii=False)[:300])
    _rule("=")


# --------------------------------------------------------------------------- #
# Kommandos
# --------------------------------------------------------------------------- #
def cmd_spec(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    operations = Operations.load(config.protocol_dir / "operations.json")
    registry = config.registry_path
    payload: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "envelopes": [PROTOCOL_INTENT, PROTOCOL_RESULT],
        "reference_implementation": "core/protocol.py",
        "schemas": ["protocol/intent.schema.json", "protocol/result.schema.json"],
        "operations": operations.as_dict(),
        "error_codes": list(ErrorCode.ALL),
        "timer_semantics": {
            "armed_by": "orchestrator (vor Anbeginn des Durchgangs)",
            "deadline_s": "hartes Budget; danach killt der Orchestrator",
            "soft_deadline_s": "hier muss der Limb seinen Statusbericht liefern",
            "grace_s": "Nachfrist fuer die Berichtuebermittlung",
            "on_expiry": "iterate | escalate | abort",
            "report_required_for_status": ["timeout", "partial"],
        },
        "iteration_semantics": {
            "counted_per": "job (nicht pro Agentenaufruf)",
            "absolute_max": ABSOLUTE_MAX_ITERATIONS,
            "profile": config.mode,
            "limits": config.limits.to_dict(),
            "failure_rule": "failed nur, wenn nach dem Versagen keine Massnahme mehr ergriffen werden kann",
        },
    }
    if args.json:
        _dump(payload)
        return EXIT_OK

    _rule("=")
    _say(f"NEU-Protokoll {PROTOCOL_VERSION}   ({PROTOCOL_INTENT}, {PROTOCOL_RESULT})")
    _say(f"Referenz: core/protocol.py   Schemas: protocol/*.schema.json   Register: {config.relative(registry)}")
    _rule("=")
    _say()
    _say("Intent-Envelope (Pflichtfelder)")
    for key in ("protocol", "version", "intent_id", "created_at", "source{role,node_id}", "target{limb}", "job{job_id,goal,iteration,max_iterations}", "task{operation,params}"):
        _say(f"  - {key}")
    _say("Intent-Envelope (optional)")
    for key in ("trace_id", "parent_intent_id", "idempotency_key", "timer{deadline_s,soft_deadline_s,grace_s,on_expiry,armed_at,soft_expires_at,expires_at}", "task{title,objective,acceptance,verification}", "constraints", "elevation", "context"):
        _say(f"  - {key}")
    _say()
    _say("Result-Envelope")
    for key in ("protocol", "version", "result_id", "intent_id", "job_id", "iteration", "status", "operation", "limb{name,version,pid}", "started_at", "finished_at", "duration_ms"):
        _say(f"  - {key}")
    for key in ("output", "artifacts[]", "status_report{state,explanation,done,remaining,blockers,suggested_next}", "timer{armed_at,expires_at,reported_at,remaining_ms,overrun_ms,self_reported}", "diagnostics{stdout,stderr,exit_code}", "error{code,message,hint}", "self_report{confidence,notes}"):
        _say(f"  - {key}")
    _say(f"  status-Werte: success | partial | failed | rejected | timeout")
    _say()
    _say(f"Operationen ({len(operations.names())})")
    _say(f"  {'OPERATION':<20}{'PHASE':<7}{'RISK':<13}{'ELEVATION':<13}{'LIMBS':<14}PFAD-PARAMS")
    for name in operations.names():
        spec = operations.spec(name)
        _say(
            f"  {name:<20}{spec.phase:<7}{spec.risk:<13}{spec.requires_elevation:<13}"
            f"{(','.join(spec.implemented_by) or '-'):<14}{','.join(spec.path_params) or '-'}"
        )
    _say()
    _say("Fehlercodes")
    _say("  " + ", ".join(ErrorCode.ALL))
    _say()
    _say("Timer-Semantik")
    _say("  * Der Orchestrator schaerft timer.armed_at/soft_expires_at/expires_at VOR dem Start des Limbs.")
    _say("  * Soft-Deadline: Der Limb liefert selbst einen status_report (self_reported=true).")
    _say("  * Harte Deadline (+grace_s): Der Orchestrator bricht ab und synthetisiert status='timeout'.")
    _say("  * Nach Ablauf folgt der autodidaktische 2. Durchgang -- der Orchestrator entwirft den Auftrag.")
    _say()
    _say("Iterations-Semantik")
    _say(f"  * Zaehlung pro Job, absolut max {ABSOLUTE_MAX_ITERATIONS}; Profil '{config.mode}': {config.limits.to_dict()}")
    _say("  * failed nur, wenn keine Massnahme mehr ergriffen werden kann; sonst iterating/escalated.")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    config.ensure_dirs()
    transport = FileTransport(config)
    jobs = JobStore(config)
    orch = Orchestrator(config, quiet=True)
    queue = transport.state()
    log_exists = config.system_log_path.is_file()
    payload = {
        "repo_root": str(config.repo_root),
        "config_source": str(config.source_file) if config.source_file else "(eingebaute Defaults)",
        "mode": config.mode,
        "limits": config.limits.to_dict(),
        "timer_defaults": config.timer.to_dict(),
        "flags": {
            "allow_shell_ops": config.allow_shell_ops,
            "allow_test_ops": config.allow_test_ops,
            "allow_repo_write": config.allow_repo_write,
        },
        "runtime": {
            "inbox": queue.inbox,
            "outbox": queue.outbox,
            "archived_jobs": queue.archived,
            "backups": queue.backups,
            "system_log": {"path": config.relative(config.system_log_path), "exists": log_exists, "note": "wird in Phase 3 rekursiv vom Bootstrap-Limb ergaenzt"},
        },
        "agents": {"capacity": orch.agents.capacity, "busy": [s.to_dict() for s in orch.agents.busy()]},
        "limbs": orch.registry.as_dict(),
        "jobs": {"active": jobs.active_count(), "recent": [j.to_dict() for j in jobs.list(limit=5)]},
        "operations": list(orch.operations.names()),
    }
    if args.json:
        _dump(payload)
        return EXIT_OK

    _rule("=")
    _say("NEU-Orchestrator -- Status")
    _rule("=")
    _kv("Repo-Root", config.repo_root)
    _kv("Konfiguration", config.source_file or "(eingebaute Defaults)")
    _kv("Profil", f"{config.mode}  ->  {config.limits.to_dict()}")
    _kv("Timer-Defaults", config.timer.to_dict())
    _kv("Flags", f"shell={config.allow_shell_ops} tests={config.allow_test_ops} repo_write={config.allow_repo_write}")
    _kv("Queues", f"inbox={queue.inbox} outbox={queue.outbox} archiv={queue.archived} backups={queue.backups}")
    _kv("system.log", f"{config.relative(config.system_log_path)} {'(vorhanden)' if log_exists else '(fehlt -- Phase 3 Auftrag)'}")
    _kv("Agent-Slots", f"capacity={orch.agents.capacity} busy={len(orch.agents.busy())}")
    _kv("Jobs", f"aktiv={jobs.active_count()}")
    _say()
    _say("Limbs")
    for name, spec in orch.registry.as_dict()["limbs"].items():
        marker = "aktiv " if spec["status"] == "active" and spec["entrypoint_exists"] else "inaktiv"
        _say(f"  [{marker}] {name:<10} v{spec['version']:<7} phase {spec['phase']}  ops: {', '.join(spec['operations']) or '-'}")
        if spec["status"] != "active":
            _say(f"              status='{spec['status']}' -- {spec['description'][:90]}")
    _say()
    _say("Letzte Jobs")
    recent = jobs.list(limit=5)
    if not recent:
        _say("  (noch keine)")
    for record in recent:
        _say(f"  {summarize(record)}")
    _rule("=")
    return EXIT_OK


def cmd_job_run(args: argparse.Namespace) -> int:
    orch = _orchestrator(args)
    params = _load_params(args.params, args.param)
    try:
        outcome = orch.run_job(
            goal=args.goal,
            operation=args.op,
            params=params,
            limb=args.limb,
            max_iterations=args.max_iterations,
            deadline_s=args.deadline,
            soft_deadline_s=args.soft_deadline,
            grace_s=args.grace,
            on_expiry=args.on_expiry,
            on_failure=args.on_failure,
            title=args.title or "",
            objective=args.objective or "",
            acceptance=tuple(args.accept or ()),
            constraints=_constraints(args),
            elevation=_elevation(args),
            context_summary=args.context or "",
            auto_iterate=not args.no_auto_iterate,
        )
    except ProtocolError as exc:
        _dump({"ok": False, "error": exc.to_dict()}) if args.json else _say(f"[protokoll] {exc}")
        return EXIT_PROTOCOL
    _print_outcome(outcome, json_mode=args.json)
    return EXIT_OK if outcome.status == JOB_RESOLVED else EXIT_JOB_FAILED


def cmd_job_list(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    jobs = JobStore(config)
    records = jobs.list(limit=args.limit, active_only=args.active)
    if args.json:
        _dump([r.to_dict() for r in records])
        return EXIT_OK
    if not records:
        _say("(keine Jobs in runtime/jobs/)")
        return EXIT_OK
    for record in records:
        _say(summarize(record))
    return EXIT_OK


def cmd_job_show(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    jobs = JobStore(config)
    record = jobs.get(args.job_id)
    if record is None:
        _say(f"[fehler] Job '{args.job_id}' nicht gefunden.")
        return EXIT_USAGE
    history = jobs.read_history(args.job_id)
    if args.json:
        _dump({"job": record.to_dict(), "history": history})
        return EXIT_OK
    _rule("=")
    _kv("Job", record.job_id)
    _kv("Ziel", record.goal)
    _kv("Status", record.status + (f" ({record.failure_kind})" if record.failure_kind else ""))
    _kv("Profil", f"{record.mode}  limits={config.limits.to_dict()}")
    _kv("Durchgaenge", f"{record.iteration}/{record.max_iterations}")
    _kv("Massnahmen", record.measures_taken)
    _kv("Wirklich failed", "ja" if record.really_failed else "nein")
    _kv("Limbs", ", ".join(record.limbs_used) or "-")
    _kv("Operationen", ", ".join(record.operations_used) or "-")
    _say()
    _say("Durchgaenge")
    for entry in record.history:
        _say(f"  D{entry.iteration}: {entry.operation} @ {entry.limb} -> {entry.status}/{entry.verdict} "
             f"({entry.duration_ms} ms){' TIMER-ABLUF' if entry.timer_expired else ''}"
             f"{' self-report' if entry.self_reported else ''}{f' err={entry.error_code}' if entry.error_code else ''}")
        if entry.measure:
            _say(f"        Massnahme: {entry.measure[:140]}")
    _say()
    _say("Historie (runtime/jobs/*.history.jsonl)")
    for event in history[-12:]:
        _say(f"  {event.get('at', '?')}  {event.get('event', '?')}  {json.dumps({k: v for k, v in event.items() if k not in {'event', 'at', 'history', 'outcome'}}, ensure_ascii=False)[:180]}")
    _rule("=")
    return EXIT_OK


def cmd_job_reclaim(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    orch = Orchestrator(config, quiet=True)
    jobs = orch.jobs
    reclaimed = orch.reclaim_orphans() + jobs.reclaim_stale()
    if args.json:
        _dump({"reclaimed": [r.to_dict() for r in reclaimed], "active": jobs.active_count()})
        return EXIT_OK
    if not reclaimed:
        _say("[ok] Keine verwaisten Jobs. Aktiv: " + str(jobs.active_count()))
        return EXIT_OK
    _say(f"[ok] {len(reclaimed)} verwaiste(r) Job(s) eskaliert:")
    for record in reclaimed:
        _say("  " + summarize(record))
    return EXIT_OK


def cmd_dispatch(args: argparse.Namespace) -> int:
    orch = _orchestrator(args)
    raw = sys.stdin.read() if args.intent == Path("-") or str(args.intent) == "-" else Path(args.intent).read_text(encoding="utf-8")
    try:
        attempt = orch.dispatch_raw(raw)
    except ProtocolError as exc:
        if args.json:
            _dump({"ok": False, "error": exc.to_dict()})
        else:
            _say(f"[protokoll] {exc}")
        return EXIT_PROTOCOL
    _print_attempt(attempt, json_mode=args.json)
    return EXIT_OK if attempt.ok else EXIT_JOB_FAILED


def cmd_intent(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    from core.kernel import Kernel

    kernel = Kernel(config)
    params = _load_params(args.params, args.param)
    try:
        intent = kernel.build_intent(
            operation=args.op,
            params=params,
            limb=args.limb,
            goal=args.goal or args.title or args.op,
            iteration=args.iteration,
            max_iterations=args.max_iterations,
            deadline_s=args.deadline,
            soft_deadline_s=args.soft_deadline,
            grace_s=args.grace,
            on_expiry=args.on_expiry,
            on_failure=args.on_failure,
            title=args.title or "",
            objective=args.objective or "",
            acceptance=tuple(args.accept or ()),
            verification={"type": args.verify_type, "command": args.verify_command} if args.verify_type and args.verify_type != "none" else None,
            constraints=_constraints(args),
            elevation=_elevation(args),
            context_summary=args.context or "",
        )
    except ProtocolError as exc:
        if args.json:
            _dump({"ok": False, "error": exc.to_dict()})
        else:
            _say(f"[protokoll] {exc}")
        return EXIT_PROTOCOL

    if args.dispatch:
        orch = Orchestrator(config, quiet=bool(args.quiet))
        attempt = orch.dispatch(intent)
        _print_attempt(attempt, json_mode=args.json)
        return EXIT_OK if attempt.ok else EXIT_JOB_FAILED

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(intent.to_json() + "\n", encoding="utf-8")
        if not args.json:
            _say(f"[ok] Intent geschrieben: {args.out}")
    if args.json:
        _dump(json.loads(intent.to_json()))
    else:
        _say(intent.to_json())
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    operations = Operations.load(config.protocol_dir / "operations.json")
    problems: list[dict[str, Any]] = []
    intent: Intent | None = None

    if args.intent:
        try:
            intent = Intent.from_file(args.intent, operations=operations)
        except ProtocolError as exc:
            problems.append({"file": str(args.intent), **exc.to_dict()})
    if args.result:
        try:
            Result.from_file(args.result, intent=intent)
        except ProtocolError as exc:
            problems.append({"file": str(args.result), **exc.to_dict()})
    if not args.intent and not args.result:
        _say("[usage] --intent und/oder --result angeben")
        return EXIT_USAGE

    ok = not problems
    if args.json:
        _dump({"ok": ok, "protocol": PROTOCOL_VERSION, "problems": problems})
    else:
        _say(f"[{'ok' if ok else 'FEHLER'}] Protokoll {PROTOCOL_VERSION}")
        for problem in problems:
            _say(f"  {problem['file']}: [{problem['code']}] {problem['path']}: {problem['message']}")
        if intent is not None and ok:
            _say(f"  intent {intent.intent_id} op={intent.operation} limb={intent.target_limb} "
                 f"job={intent.job_id} iter={intent.iteration}/{intent.job.max_iterations} timer={intent.timer.deadline_s}s")
    return EXIT_OK if ok else EXIT_PROTOCOL


def cmd_loop(args: argparse.Namespace) -> int:
    orch = _orchestrator(args)
    if args.watch:
        _say("[usage] --watch (Dauerbetrieb) folgt in Phase 4; aktuell ist --once verfuegbar.")
        return EXIT_USAGE
    attempts = orch.run_inbox_once()
    if args.json:
        _dump({"processed": len(attempts), "attempts": [a.summary() for a in attempts]})
        return EXIT_OK
    _say(f"[loop] {len(attempts)} Intent(s) abgearbeitet")
    for attempt in attempts:
        _say(f"  - {attempt.intent.intent_id} {attempt.intent.operation} -> {attempt.result.status}/{attempt.verdict.decision}")
    return EXIT_OK


def cmd_scale(args: argparse.Namespace) -> int:
    """Skalierungsprofil dauerhaft setzen -- nur mit menschlicher Freigabe."""
    config = _config_from_args(args)
    if args.profile not in SCALE_PROFILES:
        _say(f"[usage] Profil muss eines von {', '.join(SCALE_PROFILES)} sein.")
        return EXIT_USAGE
    if args.approved_by != "human":
        _say(
            "[abgelehnt] neu.config.json steht unter dem Constitution Guard (human_only_globs).\n"
            "            Ein Limb oder der Core darf sich seine Rechte nicht selbst erweitern.\n"
            "            Freigabe durch den User: --approved-by human"
        )
        return EXIT_JOB_FAILED
    path = config.repo_root / "neu.config.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    profile = dict(SCALE_PROFILES[args.profile])
    updated = {**current, "mode": args.profile, "limits": profile}
    backup = FileTransport(config).backup_file(path, reason=f"scale -> {args.profile} (approved_by=human)")
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload = {"ok": True, "profile": args.profile, "limits": profile, "config": config.relative(path), "backup": config.relative(backup) if backup else None}
    if args.json:
        _dump(payload)
    else:
        _say(f"[ok] Profil '{args.profile}' gesetzt: {profile}")
        _say(f"     Datei: {config.relative(path)}" + (f"  Backup: {config.relative(backup)}" if backup else ""))
    return EXIT_OK


# --------------------------------------------------------------------------- #
# Parameter-Helfer
# --------------------------------------------------------------------------- #
def _load_params(raw: str | None, pairs: Sequence[str] | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if raw:
        text = Path(raw[1:]).read_text(encoding="utf-8") if raw.startswith("@") else raw
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"[usage] --params ist kein gueltiges JSON: {exc}")
        if not isinstance(loaded, dict):
            raise SystemExit("[usage] --params muss ein JSON-Objekt sein")
        params.update(loaded)
    for pair in pairs or ():
        if "=" not in pair:
            raise SystemExit(f"[usage] --param erwartet schluessel=wert (gefunden: {pair!r})")
        key, value = pair.split("=", 1)
        params[key.strip()] = _coerce_scalar(value)
    return params


def _coerce_scalar(value: str) -> Any:
    lowered = value.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if value.startswith(("[", "{")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _constraints(args: argparse.Namespace) -> dict[str, Any]:
    constraints: dict[str, Any] = {}
    if getattr(args, "sandbox", None):
        constraints["sandbox_root"] = args.sandbox
    if getattr(args, "allow_shell", False):
        constraints["allow_shell"] = True
    if getattr(args, "allow_network", False):
        constraints["allow_network"] = True
    if getattr(args, "dry_run", False):
        constraints["dry_run"] = True
    if getattr(args, "no_backup", False):
        constraints["backup"] = False
    if getattr(args, "max_output_bytes", None):
        constraints["max_output_bytes"] = args.max_output_bytes
    return constraints


def _elevation(args: argparse.Namespace) -> dict[str, Any] | None:
    level = getattr(args, "elevate", None)
    if not level or level == "none":
        return None
    return {
        "level": level,
        "reason": args.reason or "",
        "approved_by": args.approved_by or "core",
        "requested_paths": tuple(args.path or ()),
    }


def _add_timer_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--deadline", type=float, default=None, help="hartes Zeitbudget des Durchgangs in Sekunden")
    parser.add_argument("--soft-deadline", type=float, default=None, help="weiche Marke fuer den Statusbericht des Limbs")
    parser.add_argument("--grace", type=float, default=None, help="Nachfrist zwischen Soft-Report und hartem Kill")
    parser.add_argument("--on-expiry", choices=("iterate", "escalate", "abort"), default="iterate", help="Reaktion bei Timer-Ablauf (Default: iterate)")
    parser.add_argument("--on-failure", choices=("autodidactic", "return_to_core", "abort"), default="autodidactic", help="Reaktion bei Fehlschlag (Default: autodidactic)")


def _add_task_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--op", required=True, help="Operation gemaess protocol/operations.json")
    parser.add_argument("--limb", default="echo", help="Ziel-Limb (Default: echo)")
    parser.add_argument("--params", default=None, help="Parameter als JSON-Objekt oder @datei.json")
    parser.add_argument("--param", action="append", default=[], help="Einzelparameter schluessel=wert (mehrfach)")
    parser.add_argument("--title", default=None, help="Kurztitel des Auftrags")
    parser.add_argument("--objective", default=None, help="Zielbeschreibung fuer den Limb")
    parser.add_argument("--accept", action="append", default=[], help="Acceptance-Kriterium (mehrfach)")
    parser.add_argument("--context", default=None, help="Kontextzusammenfassung fuer den Limb")
    parser.add_argument("--sandbox", default=None, help="Sandbox-Wurzel (Default: workspace)")
    parser.add_argument("--allow-shell", action="store_true", help="constraints.allow_shell=true")
    parser.add_argument("--allow-network", action="store_true", help="constraints.allow_network=true")
    parser.add_argument("--dry-run", action="store_true", help="Limb soll nichts schreiben")
    parser.add_argument("--no-backup", action="store_true", help="Backups deaktivieren")
    parser.add_argument("--max-output-bytes", type=int, default=None, help="Groessenlimit fuer Ausgaben")
    parser.add_argument("--elevate", choices=("none", "workspace", "repo_write"), default=None, help="Rechteanhebung")
    parser.add_argument("--reason", default=None, help="Begruendung der Rechteanhebung (>= 20 Zeichen)")
    parser.add_argument("--approved-by", default=None, help="core | human")
    parser.add_argument("--path", action="append", default=[], help="Deklarierter Zielpfad fuer elevation.requested_paths (mehrfach)")


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m orchestrator",
        description="NEU-Orchestrator: steuert Jobs, Timer und Limbs (Protokoll 1.1).",
    )
    parser.add_argument("--repo-root", default=None, help="Repository-Wurzel (Default: dieses Repo)")
    parser.add_argument("--mode", choices=tuple(SCALE_PROFILES), default=None, help="Profil fuer diesen Aufruf ueberschreiben (dev=1/1/1/1)")
    parser.add_argument("--json", action="store_true", help="Maschinenlesbare Ausgabe auf stdout")
    parser.add_argument("--quiet", action="store_true", help="Event-Ausgabe auf stderr unterdruecken")
    sub = parser.add_subparsers(dest="command", required=True)

    p_spec = sub.add_parser("spec", help="Protokoll, Operationen, Timer- und Iterations-Semantik anzeigen")
    p_spec.set_defaults(func=cmd_spec)

    p_status = sub.add_parser("status", help="Konfiguration, Queues, Jobs, Limbs, Agent-Slots")
    p_status.set_defaults(func=cmd_status)

    p_job = sub.add_parser("job", help="Job-Lebenszyklus (run/list/show)")
    job_sub = p_job.add_subparsers(dest="job_command", required=True)

    p_run = job_sub.add_parser("run", help="Ziel als Job ausfuehren (inkl. Timer + autodidaktischem 2. Durchgang)")
    p_run.add_argument("--goal", required=True, help="Ziel des Jobs (ueber alle Durchgaenge stabil)")
    p_run.add_argument("--max-iterations", type=int, default=None, help=f"Durchgaenge (max {ABSOLUTE_MAX_ITERATIONS}, gedeckelt durch das Profil)")
    p_run.add_argument("--no-auto-iterate", action="store_true", help="Autodidaktik deaktivieren (nur ein Durchgang)")
    _add_task_flags(p_run)
    _add_timer_flags(p_run)
    p_run.set_defaults(func=cmd_job_run)

    p_list = job_sub.add_parser("list", help="Jobs auflisten")
    p_list.add_argument("--limit", type=int, default=25)
    p_list.add_argument("--active", action="store_true", help="nur aktive Jobs")
    p_list.set_defaults(func=cmd_job_list)

    p_show = job_sub.add_parser("show", help="Job inkl. Historie und Statusberichten anzeigen")
    p_show.add_argument("job_id")
    p_show.set_defaults(func=cmd_job_show)

    p_reclaim = job_sub.add_parser("reclaim", help="Verwaiste (abgestuerzte) Jobs eskalieren und freigeben")
    p_reclaim.set_defaults(func=cmd_job_reclaim)

    p_dispatch = sub.add_parser("dispatch", help="Einzelnen Intent zustellen (ein Durchgang, keine Autodidaktik)")
    p_dispatch.add_argument("--intent", required=True, type=Path, help="Intent-Datei oder '-' fuer stdin")
    p_dispatch.set_defaults(func=cmd_dispatch)

    p_intent = sub.add_parser("intent", help="Intent erzeugen, validieren und optional zustellen")
    _add_task_flags(p_intent)
    _add_timer_flags(p_intent)
    p_intent.add_argument("--goal", default=None, help="Job-Ziel")
    p_intent.add_argument("--iteration", type=int, default=1, help="Durchgang (1..max_iterations)")
    p_intent.add_argument("--max-iterations", type=int, default=None, help="Iterations-Budget des Jobs")
    p_intent.add_argument("--verify-type", choices=("none", "file_exists", "hash", "unittest", "pytest", "shell"), default=None)
    p_intent.add_argument("--verify-command", default=None)
    p_intent.add_argument("--out", default=None, help="Intent zusaetzlich in diese Datei schreiben")
    p_intent.add_argument("--print", dest="print_only", action="store_true", default=True, help="Intent nur ausgeben (Default)")
    p_intent.add_argument("--dispatch", action="store_true", help="Intent sofort zustellen (ein Durchgang)")
    p_intent.set_defaults(func=cmd_intent)

    p_validate = sub.add_parser("validate", help="Intent-/Result-Datei gegen Protokoll 1.1 pruefen")
    p_validate.add_argument("--intent", type=Path, default=None)
    p_validate.add_argument("--result", type=Path, default=None)
    p_validate.set_defaults(func=cmd_validate)

    p_loop = sub.add_parser("loop", help="Inbox abarbeiten")
    p_loop.add_argument("--once", action="store_true", default=True, help="Ein Durchlauf (Default)")
    p_loop.add_argument("--watch", action="store_true", help="Dauerbetrieb (ab Phase 4)")
    p_loop.set_defaults(func=cmd_loop)

    p_scale = sub.add_parser("scale", help="Skalierungsprofil dauerhaft setzen (Constitution Guard: nur mit --approved-by human)")
    p_scale.add_argument("--profile", required=True, choices=tuple(SCALE_PROFILES))
    p_scale.add_argument("--approved-by", default="core", choices=("core", "human"))
    p_scale.set_defaults(func=cmd_scale)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ProtocolError as exc:
        if getattr(args, "json", False):
            _dump({"ok": False, "error": exc.to_dict()})
        else:
            _say(f"[protokoll] {exc}")
        return EXIT_PROTOCOL
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - die CLI darf nie mit Stacktrace sterben
        if getattr(args, "json", False):
            _dump({"ok": False, "error": {"code": ErrorCode.INTERNAL, "message": f"{type(exc).__name__}: {exc}"}})
        else:
            _say(f"[intern] {type(exc).__name__}: {exc}")
        return EXIT_PROTOCOL


if __name__ == "__main__":
    raise SystemExit(main())
