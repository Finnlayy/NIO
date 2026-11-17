#!/usr/bin/env python3
"""Sandbox-Gate fuer Self-Coding-Laeufe (Audit 2026-11-08, Befund SC-05).

Prueft den Branch eines Git-Worktrees, bevor er ins Live-Repo uebernommen werden darf.

Grundsatz: Die Abnahme liegt im **Live-Repo**, nicht im Worktree. Der Worktree liefert
nur den Code; die Kern-Tests kommen aus dem Live-Repo (``HEAD``). Ein Worker kann rote
Tests also weder loeschen noch umschreiben, um das Gate gruen zu bekommen.

Ablauf:

0. Staging: ``git archive HEAD`` des Worktrees in ein Temp-Verzeichnis -- geprueft wird
   genau der committete Stand, der spaeter gemerged wird (nichts Uncommittetes).
   ``tests/`` im Staging wird durch ``tests/`` aus dem Live-Repo (``HEAD``) ersetzt.

Stufen, in dieser Reihenfolge, Abbruch bei der ersten roten Stufe:

1. ``policy``   -- rot, wenn der Branch seit der Merge-Base geschuetzte Pfade aendert:
                   ``tests/*``, ``tools/selfcode/*`` und ``human_only_globs`` aus
                   ``neu.config.json`` des Live-Repos. Solche Aenderungen braucht einen Menschen.
2. ``compile``  -- jede ``.py``-Datei im Staging wird mit ``compile()`` geparst.
3. ``unittest`` -- ``python3 -W error::ResourceWarning -m unittest discover -s tests -t .``
                   im Staging (Worktree-Code + Live-Tests), wie ``make test-core``.
4. ``smoke``    -- ``python3 -m orchestrator --runtime-dir <tmp> status`` im Staging
                   (faengt HR-03: kaputter Kern verhindert den naechsten Start).

Aufruf::

    python3 tools/selfcode/sandbox_gate.py --worktree <pfad> --run-id <id> [--live-repo <pfad>] [--timeout 110]

``--live-repo`` ist standardmaessig das Repo, in dem dieses Skript liegt.

Ausgabe: genau eine JSON-Zeile auf stdout, Fortschritt auf stderr.
Exit-Codes: 0 = Gate bestanden · 1 = Gate nicht bestanden · 2 = Aufruf ungueltig.

Fail-closed: Fehlt etwas (Worktree, Git, ``tests/``) oder laeuft die Zeit ab, gilt das
Gate als nicht bestanden. Nur stdlib (plus das ``git``-Binary).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "neu/sandbox-gate"
VERSION = "1.1"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

DEFAULT_TIMEOUT_S = 110.0  # bleibt unter dem 120-s-Limit, mit dem der Dispatcher das Gate aufruft
GIT_TIMEOUT_S = 30.0
TAIL_LINES = 40
DEFAULT_LIVE_REPO = Path(__file__).resolve().parents[2]

# Immer geschuetzt, unabhaengig von neu.config.json: die Abnahme selbst.
GATE_PROTECTED_GLOBS: tuple[str, ...] = ("tests/*", "tools/selfcode/*")
# Fallback, falls neu.config.json im Live-Repo fehlt oder kaputt ist (Stand Audit 2026-11-08).
FALLBACK_HUMAN_ONLY_GLOBS: tuple[str, ...] = (
    "neu.config.json", "core/policy.py", "core/config.py", "core/kernel.py",
    "orchestrator/runner.py", "orchestrator/planner.py", "orchestrator/kanban/sandbox.py",
    "limbs/container.py", "limbs/registry.json", "protocol/operations.json",
    "prompts/core/kernel_system.md", ".git/*", ".github/*",
)

SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", ".venv", "venv", ".next", "runtime", "workspace"})


class GateError(Exception):
    """Vorbereitung des Gates gescheitert (fail-closed)."""


@dataclass
class Stage:
    name: str
    status: str = "skipped"  # passed | failed | skipped
    duration_s: float = 0.0
    returncode: int | None = None
    timed_out: bool = False
    detail: str = ""
    output_tail: list[str] = field(default_factory=list)


def _tail(text: str, n: int = TAIL_LINES) -> list[str]:
    return text.splitlines()[-n:]


def _log(msg: str) -> None:
    print(f"[sandbox_gate] {msg}", file=sys.stderr, flush=True)


def _git(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=GIT_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError(f"git {' '.join(args)} fehlgeschlagen: {exc}") from exc
    if proc.returncode != 0:
        raise GateError(f"git {' '.join(args)} in {repo}: {proc.stderr.strip()}")
    return proc.stdout


def _git_archive(repo: Path, rev: str, dest: Path, paths: Sequence[str] = ()) -> None:
    """Entpackt ``git archive <rev> [paths]`` nach ``dest`` (nur committeter Inhalt)."""
    with tempfile.TemporaryFile() as buf:
        try:
            proc = subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar", rev, *paths],
                stdin=subprocess.DEVNULL, stdout=buf, stderr=subprocess.PIPE,
                timeout=GIT_TIMEOUT_S, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GateError(f"git archive fehlgeschlagen: {exc}") from exc
        if proc.returncode != 0:
            raise GateError(f"git archive {rev} in {repo}: {proc.stderr.decode('utf-8', 'replace').strip()}")
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:") as tar:
            if hasattr(tarfile, "data_filter"):  # Python >= 3.11.4 / 3.12
                tar.extractall(dest, filter="data")
            else:  # pragma: no cover - aeltere 3.11-Patchstaende; Quelle ist das eigene git archive
                tar.extractall(dest)


def load_protected_globs(live_repo: Path) -> list[str]:
    globs = list(GATE_PROTECTED_GLOBS)
    human_only: list[str] = list(FALLBACK_HUMAN_ONLY_GLOBS)
    try:
        data = json.loads((live_repo / "neu.config.json").read_text(encoding="utf-8"))
        configured = data.get("human_only_globs")
        if isinstance(configured, list) and all(isinstance(g, str) for g in configured):
            human_only = list(configured)
    except (OSError, ValueError):
        pass
    for g in human_only:
        if g not in globs:
            globs.append(g)
    return globs


def stage_policy(changed: Sequence[str], protected: Sequence[str], base: str) -> Stage:
    stage = Stage("policy")
    hits = [p for p in changed if any(fnmatch.fnmatch(p, g) for g in protected)]
    if hits:
        stage.status = "failed"
        stage.detail = f"{len(hits)} geschuetzte Pfade seit {base[:12]} geaendert; Uebernahme nur durch einen Menschen."
        stage.output_tail = hits[:TAIL_LINES]
    else:
        stage.status = "passed"
        stage.detail = f"{len(changed)} geaenderte Pfade seit {base[:12]}, keiner geschuetzt."
    return stage


def iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        files.extend(Path(dirpath) / n for n in sorted(filenames) if n.endswith(".py"))
    return files


def stage_compile(staging: Path) -> Stage:
    stage = Stage("compile")
    errors: list[str] = []
    files = iter_python_files(staging)
    for path in files:
        rel = path.relative_to(staging)
        try:
            compile(path.read_bytes(), str(rel), "exec", dont_inherit=True)
        except SyntaxError as exc:
            errors.append(f"{rel}:{exc.lineno}: SyntaxError: {exc.msg}")
        except (ValueError, OSError) as exc:  # z. B. Nullbytes, Lesefehler
            errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    if not files:
        stage.status, stage.detail = "failed", "Keine .py-Dateien gefunden."
    elif errors:
        stage.status = "failed"
        stage.detail = f"{len(errors)} von {len(files)} Dateien nicht kompilierbar."
        stage.output_tail = errors[:TAIL_LINES]
    else:
        stage.status, stage.detail = "passed", f"{len(files)} Dateien kompiliert."
    return stage


def _child_env(root: Path) -> dict[str, str]:
    """Umgebung fuer Subprozesse: Importe nur aus dem Staging, kein Bytecode."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONSTARTUP", None)
    return env


def _decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, str) else ""


def _run_stage(name: str, argv: Sequence[str], cwd: Path, timeout_s: float) -> Stage:
    stage = Stage(name)
    if timeout_s <= 0:
        stage.status, stage.timed_out = "failed", True
        stage.detail = "Kein Zeitbudget mehr fuer diese Stufe."
        return stage
    try:
        proc = subprocess.run(
            list(argv), cwd=cwd, env=_child_env(cwd), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, errors="replace", timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stage.status, stage.timed_out = "failed", True
        stage.detail = f"Timeout nach {timeout_s:.1f}s."
        stage.output_tail = _tail(_decode(exc.stdout) + _decode(exc.stderr))
        return stage
    except OSError as exc:
        stage.status, stage.detail = "failed", f"Start fehlgeschlagen: {exc}"
        return stage
    stage.returncode = proc.returncode
    stage.output_tail = _tail(proc.stdout + proc.stderr)
    if proc.returncode == 0:
        stage.status = "passed"
    else:
        stage.status, stage.detail = "failed", f"Exit-Code {proc.returncode}."
    return stage


def stage_unittest(staging: Path, timeout_s: float, python: str) -> Stage:
    if not (staging / "tests").is_dir():
        return Stage("unittest", status="failed", detail="tests/ fehlt im Live-Repo.")
    argv = [python, "-W", "error::ResourceWarning", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"]
    return _run_stage("unittest", argv, staging, timeout_s)


def stage_smoke(staging: Path, timeout_s: float, python: str) -> Stage:
    if not (staging / "orchestrator").is_dir():
        return Stage("smoke", status="failed", detail="Paket orchestrator/ fehlt im Branch.")
    with tempfile.TemporaryDirectory(prefix="sandbox-gate-runtime-") as runtime_dir:
        argv = [python, "-m", "orchestrator", "--runtime-dir", runtime_dir, "status"]
        return _run_stage("smoke", argv, staging, timeout_s)


def run_gate(
    worktree: Path,
    run_id: str,
    live_repo: Path = DEFAULT_LIVE_REPO,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    python: str | None = None,
) -> dict:
    python = python or sys.executable
    started = time.monotonic()
    started_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    report: dict = {
        "schema": SCHEMA, "version": VERSION, "run_id": run_id,
        "worktree": str(worktree), "live_repo": str(live_repo),
        "passed": False, "failed_stage": None, "error": None,
        "head": None, "live_head": None, "merge_base": None, "changed_files": [],
        "started_at": started_at, "duration_s": 0.0, "timeout_s": timeout_s, "stages": [],
    }

    def remaining() -> float:
        return timeout_s - (time.monotonic() - started)

    with tempfile.TemporaryDirectory(prefix=f"sandbox-gate-{run_id[:32]}-") as tmp:
        staging = Path(tmp) / "staging"
        staging.mkdir()
        try:
            head = _git(worktree, "rev-parse", "HEAD").strip()
            live_head = _git(live_repo, "rev-parse", "HEAD").strip()
            base = _git(worktree, "merge-base", live_head, head).strip()
            changed = [p for p in _git(worktree, "diff", "--name-only", "--no-renames", base, head).splitlines() if p]
            report.update(head=head, live_head=live_head, merge_base=base, changed_files=changed)
            _git_archive(worktree, head, staging)
            shutil.rmtree(staging / "tests", ignore_errors=True)
            if "tests" in _git(live_repo, "ls-tree", "--name-only", live_head).split():
                _git_archive(live_repo, live_head, staging, ["tests"])
            protected = load_protected_globs(live_repo)
        except GateError as exc:
            _log(f"Run {run_id}: Vorbereitung gescheitert: {exc}")
            report.update(error=str(exc), duration_s=round(time.monotonic() - started, 3))
            return report

        steps: list[tuple[str, Callable[[], Stage]]] = [
            ("policy", lambda: stage_policy(changed, protected, base)),
            ("compile", lambda: stage_compile(staging)),
            ("unittest", lambda: stage_unittest(staging, remaining(), python)),
            ("smoke", lambda: stage_smoke(staging, remaining(), python)),
        ]
        stages: list[Stage] = []
        failed = False
        for name, step in steps:
            if failed:
                stages.append(Stage(name, detail="Uebersprungen nach vorheriger roter Stufe."))
                continue
            _log(f"Run {run_id}: Stufe {name} ...")
            t0 = time.monotonic()
            stage = step()
            stage.duration_s = round(time.monotonic() - t0, 3)
            _log(f"Run {run_id}: Stufe {name} -> {stage.status} ({stage.duration_s}s) {stage.detail}".rstrip())
            stages.append(stage)
            failed = stage.status != "passed"

    report.update(
        passed=not failed,
        failed_stage=next((s.name for s in stages if s.status == "failed"), None),
        duration_s=round(time.monotonic() - started, 3),
        stages=[asdict(s) for s in stages],
    )
    return report


def _usage_error(run_id: str, worktree: str, message: str) -> int:
    _log(message)
    print(json.dumps({
        "schema": SCHEMA, "version": VERSION, "run_id": run_id, "worktree": worktree,
        "passed": False, "failed_stage": None, "error": message, "stages": [],
    }, ensure_ascii=False))
    return EXIT_USAGE


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sandbox-Gate: policy, compile, unittest, smoke fuer einen Worktree-Branch (SC-05).")
    parser.add_argument("--worktree", required=True, help="Pfad zum zu pruefenden Git-Worktree")
    parser.add_argument("--run-id", required=True, help="Kennung des Kanban-Laufs (Bericht und Log)")
    parser.add_argument("--live-repo", default=str(DEFAULT_LIVE_REPO),
                        help="Live-Repo, aus dem Tests und Schutzregeln kommen (Standard: Repo dieses Skripts)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S,
                        help=f"Gesamtbudget in Sekunden (Standard {DEFAULT_TIMEOUT_S:g})")
    args = parser.parse_args(argv)

    if not args.run_id.strip():
        return _usage_error(args.run_id, args.worktree, "--run-id darf nicht leer sein.")
    if args.timeout <= 0:
        return _usage_error(args.run_id, args.worktree, "--timeout muss positiv sein.")
    worktree = Path(args.worktree).resolve()
    live_repo = Path(args.live_repo).resolve()
    if not worktree.is_dir():
        return _usage_error(args.run_id, args.worktree, f"Worktree nicht gefunden: {worktree}")
    if not live_repo.is_dir():
        return _usage_error(args.run_id, args.worktree, f"Live-Repo nicht gefunden: {live_repo}")

    report = run_gate(worktree, args.run_id, live_repo=live_repo, timeout_s=args.timeout)
    print(json.dumps(report, ensure_ascii=False))
    return EXIT_PASS if report["passed"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
