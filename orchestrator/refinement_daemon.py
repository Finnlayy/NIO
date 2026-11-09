"""Refinement-Daemon: Hintergrund-Heilung geparkter Limbs, Schritt fuer Schritt.

Der Daemon ist die ausfuehrende Haelfte des Refinement-Vaults
(``orchestrator/refinement.py``). Ein Lauf:

1. **Claim** -- aeltester faelliger Eintrag (FIFO) unter Lease nach
   ``healing_in_progress``. Nur ein Daemon pro Vault (Instanz-Lock).
2. **Isolierte Test-Ausfuehrung** -- der Candidate wird in ein frisches
   Sandbox-Verzeichnis kopiert; der Test laeuft als Subprozess mit
   geleertem Environment (keine Secrets), eigenem ``HOME``/``TMPDIR`` und
   hartem Timeout. Der Vault selbst wird waehrenddessen nie angefasst.
3. **Ciel-Fehleranalyse** -- schlaegt der Test fehl, bekommt der Healer
   (Ciel-Hook: ``heal(entry, workdir, failure)``) den Fehler-Tail und darf
   **genau einen** kleinen Patch-Candidate zurueckgeben. Der wird als neue
   Version in den Vault uebernommen und erneut getestet -- hoechstens
   ``max_heal_steps_per_run``-mal pro Lauf (inkrementeller Fortschritt
   statt Endlos-Loop in einem Lauf).
4. **Abschluss** -- gruen: ``ready_for_review`` + Apollo-Benachrichtigung.
   Rot: ``fail_healing`` -- zurueck in die Queue mit Backoff oder, nach
   ``max_attempts`` Laeufen, in die Quarantaene.

**Fehlerisolation:** Jeder Schritt (``test`` / ``ciel_heal`` / ``retest``)
faengt seine eigenen Ausnahmen ab und meldet sie als strukturierten Fehler
an genau diesen einen Eintrag. Ein kaputter Limb blockiert weder den
Daemon noch andere Eintraege; ein abgestuerzter Worker hinterlaesst eine
Lease, die der naechste Lauf aufraeumt (``recover_stale_leases``).

**Scheduler:** bewusst **kein** ``apscheduler`` (der NEU-Stack ist
Stdlib-only, ``pyproject.toml``). Zwei gleichwertige Trigger:

* ``run_forever(interval_s=...)`` -- leichter asyncio-Loop, optional nur in
  einem Tageszeit-Fenster (z. B. nachts 02:00-05:00, auch ueber Mitternacht);
* ``python3 -m orchestrator refinement run-once`` aus Cron/systemd-Timer --
  ein Daemon-Lauf pro Aufruf, kein Dauerprozess noetig.

Ohne verdrahteten Healer laeuft der Daemon im reinen Test-Modus:
``NullHealer`` erfindet keine Patches, fehlschlagende Limbs wandern mit
Backoff zurueck in die Queue und am Ende in die Quarantaene -- sichtbar,
statt still repariert zu *behaupten*.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from datetime import time as day_time
from pathlib import Path
from typing import Any, Protocol

from core.atomic import atomic_write_bytes
from core.protocol import utc_now

from .refinement import RefinementVault, VaultEntry

__all__ = [
    "CargoTestSandbox",
    "CielHealer",
    "CommandHealer",
    "CommandSandbox",
    "DaemonAlreadyRunning",
    "FfiSmokeSandbox",
    "HealingReport",
    "NullHealer",
    "RefinementDaemon",
    "SandboxRunner",
    "StepResult",
    "in_active_window",
]

MAX_OUTPUT_CHARS = 16_000
DEFAULT_TIMEOUT_S = 600.0


# --------------------------------------------------------------------------- #
# Schritt-Ergebnisse und Hooks
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StepResult:
    """Ergebnis eines isolierten Schritts (Test oder Heilversuch)."""

    ok: bool
    step: str
    kind: str = ""
    message: str = ""
    detail: str = ""

    @classmethod
    def success(cls, step: str) -> StepResult:
        return cls(ok=True, step=step)

    @classmethod
    def failure(cls, step: str, kind: str, message: str, detail: str = "") -> StepResult:
        return cls(ok=False, step=step, kind=kind, message=message, detail=detail[-MAX_OUTPUT_CHARS:])


class SandboxRunner(Protocol):
    """Testet einen Candidate in ``workdir`` (darf dort nichts persistieren)."""

    def run_tests(self, entry: VaultEntry, workdir: Path) -> StepResult: ...


class CielHealer(Protocol):
    """Ciel-Hook: analysiert einen Fehlschlag, liefert optional einen Patch.

    Rueckgabe: Pfad zum gepatchten Artefakt (innerhalb von ``workdir``) oder
    ``None``, wenn Ciel (noch) keine Korrektur hat. Ausnahmen sind erlaubt --
    der Daemon isoliert sie als ``ciel_heal``-Fehler dieses einen Eintrags.
    """

    def heal(self, entry: VaultEntry, workdir: Path, failure: StepResult) -> Path | None: ...


#: Apollo-Benachrichtigung: wird bei ``ready_for_review`` (und Quarantaene)
#: aufgerufen. Ausnahmen werden geschluckt -- Benachrichtigung ist nie Wahrheit.
NotifyHook = Callable[[VaultEntry], None]


class NullHealer:
    """Default ohne verdrahtetes Ciel: heilt nichts, behauptet nichts."""

    def heal(self, entry: VaultEntry, workdir: Path, failure: StepResult) -> Path | None:
        _ = (entry, workdir, failure)
        return None


class CommandHealer:
    """Ciel als externer Prozess: bekommt Fehler per Env/Datei, liefert Datei.

    Vertrag: Der Befehl laeuft in ``workdir`` mit ``NIO_REFINEMENT_FAILURE``
    (JSON), ``NIO_REFINEMENT_ARTIFACT`` und ``NIO_REFINEMENT_LIMB_ID`` im Env.
    Ein Patch ist die Datei ``workdir/patched/<artefaktname>`` mit Exit 0;
    Exit != 0 oder fehlende Datei heisst "kein Patch".
    """

    def __init__(self, command: tuple[str, ...], *, timeout_s: float = 600.0) -> None:
        if not command:
            raise ValueError("CommandHealer braucht ein Kommando.")
        self.command = tuple(command)
        self.timeout_s = timeout_s

    def heal(self, entry: VaultEntry, workdir: Path, failure: StepResult) -> Path | None:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(workdir),
            "TMPDIR": str(workdir),
            "NIO_REFINEMENT_LIMB_ID": entry.limb_id,
            "NIO_REFINEMENT_ARTIFACT": str(workdir / entry.artifact_filename),
            "NIO_REFINEMENT_FAILURE": json.dumps(
                {"step": failure.step, "kind": failure.kind, "message": failure.message, "detail": failure.detail},
                ensure_ascii=False,
            ),
        }
        done = subprocess.run(
            list(self.command), cwd=workdir, env=env, capture_output=True, text=True, timeout=self.timeout_s, check=False
        )
        if done.returncode != 0:
            return None
        patched = workdir / "patched" / entry.artifact_filename
        return patched if patched.is_file() else None


# --------------------------------------------------------------------------- #
# Sandbox-Laeufer (isolierte Test-Ausfuehrung)
# --------------------------------------------------------------------------- #
def _run_command(command: list[str], *, cwd: Path, timeout_s: float, step: str) -> StepResult:
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(cwd), "TMPDIR": str(cwd), "CARGO_HOME": str(cwd / ".cargo")}
    try:
        done = subprocess.run(
            command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except FileNotFoundError as exc:
        return StepResult.failure(step, "command_not_found", f"Kommando nicht gefunden: {command[0]}", str(exc))
    except subprocess.TimeoutExpired as exc:
        tail = ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
        return StepResult.failure(step, "timeout", f"Test nach {timeout_s:.0f}s abgebrochen.", tail)
    output = "\n".join(part for part in (done.stdout, done.stderr) if part)
    if done.returncode == 0:
        return StepResult.success(step)
    return StepResult.failure(step, "test_failed", f"Exit-Code {done.returncode} von {' '.join(command)}", output)


class CommandSandbox:
    """Fuehrt das pro Eintrag hinterlegte ``test_command`` in der Sandbox aus.

    Platzhalter ``{artifact}`` im Kommando wird durch den Candidate-Pfad in
    der Sandbox ersetzt. Ohne Kommando: ``no_test_command`` -- ein Limb ohne
    Test wird nicht per Augenschein "geheilt".
    """

    def __init__(self, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self.timeout_s = timeout_s

    def run_tests(self, entry: VaultEntry, workdir: Path) -> StepResult:
        if not entry.test_command:
            return StepResult.failure("test", "no_test_command", "Kein test_command im Vault-Eintrag hinterlegt.")
        artifact = str(workdir / entry.artifact_filename)
        command = [part.replace("{artifact}", artifact) for part in entry.test_command]
        return _run_command(command, cwd=workdir, timeout_s=self.timeout_s, step="test")


class CargoTestSandbox:
    """``cargo test`` fuer einen Rust-Limb-Quellbaum in der Sandbox.

    Erwartet, dass das Artefakt ein Verzeichnis-nahe Quelle ist bzw. der
    Eintrag ueber ``test_command`` nicht gesetzt ist -- hier explizit:
    ``manifest`` relativ zum Sandbox-Verzeichnis (Default ``Cargo.toml``).
    """

    def __init__(self, *, manifest: str = "Cargo.toml", timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self.manifest = manifest
        self.timeout_s = timeout_s

    def run_tests(self, entry: VaultEntry, workdir: Path) -> StepResult:
        _ = entry
        if not (workdir / self.manifest).is_file():
            return StepResult.failure("test", "manifest_missing", f"{self.manifest} fehlt in der Sandbox.")
        return _run_command(["cargo", "test", "--manifest-path", self.manifest], cwd=workdir, timeout_s=self.timeout_s, step="test")


class FfiSmokeSandbox:
    """Laedt eine ``.so``-Limb in einem **Kindprozess** und prueft den FFI-Vertrag.

    Laedt bewusst nicht im Daemon-Prozess: Ein defektes Artefakt darf hoechstens
    den Kindprozess mitreissen (Fehlerisolation), nie den Daemon. Geprueft
    werden Contract-Version, ``init_limb`` und ein ``process_payload``-Smoke.
    """

    def __init__(self, *, timeout_s: float = 120.0) -> None:
        self.timeout_s = timeout_s

    def run_tests(self, entry: VaultEntry, workdir: Path) -> StepResult:
        artifact = workdir / entry.artifact_filename
        if artifact.suffix != ".so":
            return StepResult.failure("test", "not_a_shared_library", f"FFI-Smoke braucht eine .so, gefunden: {artifact.name}")
        probe = (
            "import json,sys;"
            "sys.path.insert(0, sys.argv[2]);"
            "from orchestrator.kanban.limb_ffi import LimbFFIError, LimbHotReloader;"
            "r=None\n"
            "try:\n"
            " r=LimbHotReloader(sys.argv[1]); out=r.process_payload(b'{}'); print(json.dumps({'ok': True, 'bytes': len(out)}))\n"
            "except Exception as exc:\n"
            " print(json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}))\n"
            "finally:\n"
            " r.shutdown() if r else None\n"
        )
        repo_root = str(Path(__file__).resolve().parent.parent)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(workdir), "TMPDIR": str(workdir)}
        try:
            done = subprocess.run(
                [sys.executable, "-I", "-c", probe, str(artifact), repo_root],
                cwd=workdir, env=env, capture_output=True, text=True, timeout=self.timeout_s, check=False,
            )
        except subprocess.TimeoutExpired:
            return StepResult.failure("test", "timeout", f"FFI-Smoke nach {self.timeout_s:.0f}s abgebrochen.")
        line = (done.stdout or "").strip().splitlines()[-1] if done.stdout.strip() else ""
        with contextlib.suppress(json.JSONDecodeError):
            parsed = json.loads(line)
            if parsed.get("ok"):
                return StepResult.success("test")
            return StepResult.failure("test", "ffi_failed", str(parsed.get("error", "FFI-Smoke fehlgeschlagen")), done.stderr)
        return StepResult.failure("test", "ffi_failed", f"FFI-Smoke ohne verwertbare Antwort (Exit {done.returncode}).", (done.stderr or line))


def default_sandbox(entry: VaultEntry) -> SandboxRunner:
    """Heuristik: ``test_command`` gewinnt, ``.so`` -> FFI-Smoke, sonst Kommando-Sandbox."""
    if entry.test_command:
        return CommandSandbox()
    if entry.artifact_filename.endswith(".so"):
        return FfiSmokeSandbox()
    return CommandSandbox()


# --------------------------------------------------------------------------- #
# Daemon
# --------------------------------------------------------------------------- #
class DaemonAlreadyRunning(RuntimeError):
    """Ein zweiter Daemon auf demselben Vault ist nicht erlaubt."""


@dataclass(frozen=True)
class HealingReport:
    """Was ein Daemon-Lauf mit einem Eintrag gemacht hat (fuer CLI/Logs)."""

    limb_id: str
    outcome: str  # ready_for_review | requeued | quarantined | empty
    steps: tuple[str, ...] = ()
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"limb_id": self.limb_id, "outcome": self.outcome, "steps": list(self.steps), "detail": self.detail}


def in_active_window(moment: datetime, *, start: day_time | None, end: day_time | None) -> bool:
    """Tageszeit-Fenster, auch ueber Mitternacht (z. B. 22:00-05:00)."""
    if start is None or end is None:
        return True
    current = moment.timetz().replace(tzinfo=None)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


class RefinementDaemon:
    """Ein Heilungslauf pro ``run_once``; ``run_forever`` ist der Scheduler-Loop."""

    def __init__(
        self,
        vault: RefinementVault,
        *,
        sandbox: SandboxRunner | None = None,
        healer: CielHealer | None = None,
        notify: NotifyHook | None = None,
        worker_id: str = "",
        lease_s: float = 900.0,
        max_heal_steps_per_run: int = 3,
        retry_base_s: float = 60.0,
    ) -> None:
        self.vault = vault
        self.sandbox = sandbox
        self.healer: CielHealer = healer or NullHealer()
        self.notify = notify
        self.worker_id = worker_id or f"refinement-daemon-{os.getpid()}"
        self.lease_s = lease_s
        self.max_heal_steps_per_run = max(0, int(max_heal_steps_per_run))
        self.retry_base_s = retry_base_s

    # -- Benachrichtigung ---------------------------------------------------- #
    def _notify(self, entry: VaultEntry) -> None:
        if self.notify is None:
            return
        with contextlib.suppress(Exception):
            self.notify(entry)

    def file_notifier(self, path: Path | str) -> NotifyHook:
        """Standard-Apollo-Hook: eine JSON-Zeile pro Benachrichtigung in eine Datei.

        Apollo (Frontend/API) kann diese Datei pollen bzw. tailen, ohne dass der
        Daemon einen Netzwerk-Client oder Apollo-Interna kennen muss.
        """

        def _notify(entry: VaultEntry) -> None:
            line = json.dumps(
                {"at": entry.updated_at, "limb_id": entry.limb_id, "state": entry.state, "version": entry.version, "attempts": entry.attempts},
                ensure_ascii=False,
            )
            target = Path(path)
            previous = target.read_bytes() if target.is_file() else b""
            atomic_write_bytes(target, previous + (line + "\n").encode("utf-8"))

        return _notify

    # -- Ein Lauf -------------------------------------------------------------- #
    def run_once(self, *, now: datetime | None = None) -> HealingReport:
        """Bearbeitet hoechstens **einen** Eintrag. Leerlauf ist kein Fehler."""
        entry = self.vault.claim_next(worker_id=self.worker_id, lease_s=self.lease_s, now=now)
        if entry is None:
            return HealingReport(limb_id="", outcome="empty", detail="Keine faellige Limb in refinement_queued.")
        return self._heal_entry(entry)

    def run_cycle(self, *, max_items: int = 1, now: datetime | None = None) -> list[HealingReport]:
        """Bis zu ``max_items`` Eintraege; ein Fehler stoppt den Zyklus nie."""
        reports: list[HealingReport] = []
        for _ in range(max(1, max_items)):
            report = self.run_once(now=now)
            reports.append(report)
            if report.outcome == "empty":
                break
        return reports

    def _heal_entry(self, entry: VaultEntry) -> HealingReport:
        steps: list[str] = []
        sandbox = self.sandbox or default_sandbox(entry)
        try:
            with tempfile.TemporaryDirectory(prefix=f"nio-refine-{entry.limb_id}-") as raw_dir:
                workdir = Path(raw_dir)
                shutil.copyfile(self.vault.artifact_path(entry), workdir / entry.artifact_filename)
                failure = self._run_step(steps, "test", lambda: sandbox.run_tests(entry, workdir))
                healed_steps = 0
                while not failure.ok and healed_steps < self.max_heal_steps_per_run:
                    current = failure
                    patch = self._try_heal(entry, workdir, current, steps)
                    if patch is None:
                        break
                    entry = self.vault.replace_candidate(entry.limb_id, patch, worker_id=self.worker_id)
                    # Patch liegt jetzt im Vault; Sandbox auf den neuen Stand bringen.
                    shutil.copyfile(self.vault.artifact_path(entry), workdir / entry.artifact_filename)
                    healed_steps += 1
                    def retest(current: VaultEntry = entry) -> StepResult:
                        return sandbox.run_tests(current, workdir)

                    failure = self._run_step(steps, "retest", retest)
                if failure.ok:
                    done = self.vault.complete_healing(entry.limb_id, worker_id=self.worker_id)
                    self._notify(done)
                    return HealingReport(done.limb_id, "ready_for_review", tuple(steps), "Alle Tests gruen -- wartet auf menschliche Freigabe.")
                failed = self.vault.fail_healing(
                    entry.limb_id,
                    worker_id=self.worker_id,
                    step=failure.step,
                    kind=failure.kind or "failed",
                    message=failure.message,
                    detail=failure.detail,
                    retry_base_s=self.retry_base_s,
                )
                if failed.state == "quarantined":
                    self._notify(failed)
                return HealingReport(failed.limb_id, failed.state, tuple(steps), failure.message)
        except Exception as exc:  # Fehlerisolation: Daemon ueberlebt jeden Eintrag.
            with contextlib.suppress(Exception):
                failed = self.vault.fail_healing(
                    entry.limb_id,
                    worker_id=self.worker_id,
                    step="daemon",
                    kind="daemon_error",
                    message=f"{type(exc).__name__}: {exc}",
                    retry_base_s=self.retry_base_s,
                )
                return HealingReport(failed.limb_id, failed.state, tuple(steps), f"{type(exc).__name__}: {exc}")
            return HealingReport(entry.limb_id, "requeued", tuple(steps), f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _run_step(steps: list[str], label: str, action: Callable[[], StepResult]) -> StepResult:
        try:
            result = action()
        except Exception as exc:  # ein Schritt darf den Lauf nicht abreissen
            result = StepResult.failure(label, "step_error", f"{type(exc).__name__}: {exc}")
        steps.append(f"{label}:{'ok' if result.ok else result.kind or 'failed'}")
        return result

    def _try_heal(self, entry: VaultEntry, workdir: Path, failure: StepResult, steps: list[str]) -> Path | None:
        try:
            patch = self.healer.heal(entry, workdir, failure)
        except Exception as exc:  # Ciel-Fehler isolieren, nicht den Daemon killen
            steps.append(f"ciel_heal:step_error:{type(exc).__name__}")
            return None
        steps.append("ciel_heal:patch" if patch is not None else "ciel_heal:no_patch")
        if patch is not None and not Path(patch).is_file():
            steps.append("ciel_heal:patch_missing")
            return None
        return Path(patch) if patch is not None else None

    # -- Scheduler-Loop -------------------------------------------------------- #
    async def run_forever(
        self,
        *,
        interval_s: float = 300.0,
        active_start: day_time | None = None,
        active_end: day_time | None = None,
        max_cycles: int | None = None,
        max_items_per_cycle: int = 1,
        sleep: Callable[[float], Any] = asyncio.sleep,
        clock: Callable[[], datetime] = utc_now,
    ) -> list[HealingReport]:
        """Leichtgewichtiger asyncio-Scheduler (Ersatz fuer apscheduler/Cron).

        Tickt alle ``interval_s``, arbeitet aber nur im aktiven Fenster.
        ``max_cycles`` begrenzt die Laeufe (Tests, systemd-``Type=oneshot``-Aequivalente).
        Die eigentliche Arbeit laeuft per ``to_thread`` -- ein 10-Minuten-
        ``cargo test`` blockiert den Event-Loop (und damit Apollo) nicht.
        """
        reports: list[HealingReport] = []
        cycles = 0
        with _daemon_lock(self.vault.root):
            while max_cycles is None or cycles < max_cycles:
                cycles += 1
                if in_active_window(clock(), start=active_start, end=active_end):
                    self.vault.recover_stale_leases(now=clock())
                    reports.extend(await asyncio.to_thread(self.run_cycle, max_items=max_items_per_cycle))
                if max_cycles is not None and cycles >= max_cycles:
                    break
                await sleep(max(1.0, interval_s))
        return reports


@contextlib.contextmanager
def _daemon_lock(root: Path) -> Iterator[None]:
    """Instanz-Lock: genau ein Daemon pro Vault (PID-Datei, O_EXCL)."""
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".daemon.lock"
    try:
        handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        # Lebt der eingetragene Prozess noch? Sonst ist die Sperre verwaist.
        pid = 0
        with contextlib.suppress(OSError, ValueError):
            pid = int(lock.read_text(encoding="utf-8").split()[0])
        alive = False
        if pid > 0:
            with contextlib.suppress(OSError):
                os.kill(pid, 0)
                alive = True
        if alive:
            raise DaemonAlreadyRunning(f"Refinement-Daemon laeuft bereits (PID {pid}, Lock {lock}).") from None
        lock.unlink(missing_ok=True)
        handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(handle, f"{os.getpid()}\n".encode())
        yield
    finally:
        os.close(handle)
        lock.unlink(missing_ok=True)
