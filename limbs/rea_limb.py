"""REA-Subagent-Limb (Phase 3) -- Reverse Engineering als eigener Knoten.

Dieser Limb ist kein Dateiarm, sondern ein **Subagent**: Er bringt sein eigenes
Werkzeug mit (REA, https://github.com/NabilRFG12/Reverse-Engineer-anything),
betreibt es ausschliesslich innerhalb der ihm zugewiesenen Sandbox und liefert
Belege statt Behauptungen zurueck.

Aufgabenprofil:

* ``rea.ping``         -- Ist REA in *dieser* Sandbox installiert? Version, Pfade, Node.
* ``rea.install``      -- Installation aus dem Git-Repository (Quellbau) oder aus npm
                          (vorgebaut), optional mit pwntools-venv fuer den ELF-Provider.
* ``rea.doctor``       -- ``rea doctor`` als JSON, verdichtet auf Checks/Capabilities.
* ``rea.capabilities`` -- Operationsmatrix inkl. Nebenwirkungen.
* ``rea.analyze``      -- Genau ein freigegebenes REA-Kommando gegen ein Ziel in der Sandbox.

Grenzen (warum das sicher ist):

1. **Kein Shell-String.** Argumente sind Listen. ``command`` ist ein Schluessel aus
   :data:`COMMANDS`; jede Position und jede Option ist dort deklariert.
2. **Pfade gehen durch die Policy.** ``ctx.resolve()`` loest jeden Pfad gegen die
   Sandbox des Subagenten auf; ``..`` und absolute Pfade werden abgewiesen.
3. **Eigene Prozessgruppe.** Startet ein Kind, wird bei Timer-Ablauf die *Gruppe*
   beendet -- inklusive npm/tsc/node-Kindern.
4. **Eigenes Zuhause.** ``HOME``, ``TMPDIR``, ``XDG_CACHE_HOME`` und der npm-Cache
   zeigen in die Sandbox. Ein Lauf schreibt nicht ins Host-Home.
5. **Netz nur wo noetig.** ``rea.install`` verlangt ``constraints.allow_network=true``;
   statische Analyse oeffnet keinen Socket.

Aufruf: ``python3 limbs/rea_limb.py --intent runtime/inbox/rea/<id>.json``
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _entry in (str(Path(__file__).resolve().parent), str(_REPO_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

if __package__ in (None, ""):  # direkter Skriptaufruf durch den Orchestrator
    from base import LimbBase, LimbContext, LimbError  # type: ignore[import-not-found]
else:  # Import als Paket (Tests, Tooling)
    from limbs.base import LimbBase, LimbContext, LimbError

from core.protocol import PROTOCOL_VERSION, ErrorCode, utc_now_iso  # noqa: E402

#: Das Repository aus dem Auftrag. Aenderbar pro Installationslauf (params.repository),
#: damit ein Fork oder ein lokaler Klon ohne Codeaenderung genutzt werden kann.
REA_REPOSITORY = "https://github.com/NabilRFG12/Reverse-Engineer-anything.git"
REA_PACKAGE = "rea-agents"
INSTALL_MARKER = ".rea-install.json"

#: REA 6.x verlangt diese drei Pakete fuer den pwntools-ELF-Provider (genaue Pins).
PWNTOOLS_PACKAGES = ("pwntools==4.15.0", "pyelftools==0.33", "unicorn==2.1.2")

DEFAULT_TIMEOUT_S = 900.0
#: Deckel fuer die In-Memory-Ausgabe. Der Volltext steht immer im Log-Artefakt;
#: nur was fuer die Zusammenfassung noetig ist, bleibt im Speicher.
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
MAX_SUMMARY_ITEMS = 12

#: Abbildung REA-Fehlercode -> NEU-Fehlercode. Unbekannte Codes werden INTERNAL.
_REA_ERRORS = {
    "provider_unavailable": ErrorCode.TARGET_NOT_FOUND,
    "missing_analysis_engine": ErrorCode.TARGET_NOT_FOUND,
    "unsupported_target": ErrorCode.UNSUPPORTED_OP,
    "unsupported_host": ErrorCode.UNSUPPORTED_OP,
    "invalid_request": ErrorCode.SCHEMA_INVALID,
    "invalid_target": ErrorCode.SCHEMA_INVALID,
    "permission_denied": ErrorCode.POLICY_DENIED,
    "timeout": ErrorCode.TIMEOUT,
}


@dataclass(frozen=True)
class ReaCommand:
    """Form eines freigegebenen REA-Kommandos.

    ``path_args``  Anzahl der fuehrenden Positionalargumente, die Sandbox-Pfade sind.
    ``literals``   Anzahl weiterer Positionalargumente (Name, Adresse, Suchbegriff).
    ``flags``      Erlaubte Optionsschluessel aus ``params.options``.
    """

    name: str
    path_args: int = 0
    literals: int = 0
    flags: tuple[str, ...] = ()
    note: str = ""

    def shape(self) -> dict[str, Any]:
        return {"path_args": self.path_args, "literals": self.literals, "flags": list(self.flags), "note": self.note}


#: Allowlist. Was hier nicht steht, kann der Subagent nicht aufrufen -- auch wenn
#: REA es koennte. Erweiterung ist eine bewusste Entscheidung, kein Freitext.
COMMANDS: dict[str, ReaCommand] = {
    "analyze-javascript-application": ReaCommand(
        "analyze-javascript-application", path_args=1, flags=("artifact_format",),
        note="JavaScript/Electron-Anwendung statisch rekonstruieren (ohne Engine, ohne Netz).",
    ),
    "analyze": ReaCommand("analyze", path_args=1, flags=("provider", "snapshot"), note="Ueberblick ueber eine App."),
    "inspect": ReaCommand("inspect", path_args=1, flags=("provider", "snapshot"), note="Ueberblick mit Belegen."),
    "inspect-binary-layout": ReaCommand(
        "inspect-binary-layout", path_args=1, note="ELF/Mach-O-Layout ohne Ausfuehrung (pwntools-Provider).",
    ),
    "inspect-artifact": ReaCommand("inspect-artifact", path_args=1, note="Artefakt-Inventar ohne Ausfuehrung."),
    "inspect-managed-members": ReaCommand("inspect-managed-members", path_args=1, note="PE/CLI-Metadaten (statisch)."),
    "inspect-evm-interface": ReaCommand("inspect-evm-interface", path_args=1, note="EVM-Selektoren aus Bytecode."),
    "inspect-web-network-capture": ReaCommand("inspect-web-network-capture", path_args=1, note="HAR/mitmproxy-Aufzeichnung."),
    "strings": ReaCommand("strings", path_args=1, flags=("provider",), note="Strings des Ziels."),
    "instructions": ReaCommand("instructions", path_args=1, flags=("provider",), note="Rohe Instruktionen."),
    "function": ReaCommand("function", path_args=1, literals=1, flags=("provider",), note="Funktionsdossier (Name/Adresse)."),
    "decompile": ReaCommand("decompile", path_args=1, literals=1, flags=("provider",), note="Pseudocode einer Stelle."),
    "xrefs": ReaCommand("xrefs", path_args=1, literals=1, flags=("provider",), note="Referenzen auf eine Adresse."),
    "search": ReaCommand("search", path_args=1, literals=1, flags=("provider",), note="Suche im Ziel."),
    "evidence-import": ReaCommand("evidence-import", path_args=1, note="Evidence-Bundle validieren."),
    "evidence-export": ReaCommand("evidence-export", path_args=2, note="Evidence kanonisch exportieren."),
    "compare": ReaCommand("compare", path_args=2, note="Zwei Evidence-Bundles vergleichen."),
    "compare-source-to-bundle": ReaCommand("compare-source-to-bundle", path_args=2, note="Quellbaum vs. Bundle."),
    "import-reference-source": ReaCommand("import-reference-source", path_args=1, note="Historische Quelle importieren."),
    "providers": ReaCommand("providers", note="Verfuegbare Analyse-Provider."),
    "capabilities": ReaCommand("capabilities", note="Faehigkeiten und Nebenwirkungen."),
    "doctor": ReaCommand("doctor", flags=("provider", "target", "client"), note="Bereitschaftspruefung."),
}


@dataclass(frozen=True)
class Layout:
    """Verzeichnisvertrag eines REA-Subagenten (relativ zur eigenen Sandbox)."""

    install: Path
    targets: Path
    out: Path
    logs: Path
    tmp: Path
    home: Path
    cache: Path

    @property
    def marker(self) -> Path:
        return self.install / INSTALL_MARKER

    def dirs(self) -> tuple[Path, ...]:
        return (self.install, self.targets, self.out, self.logs, self.tmp, self.home, self.cache)

    def describe(self, ctx: LimbContext) -> dict[str, str]:
        return {
            "install": ctx.rel(self.install),
            "targets": ctx.rel(self.targets),
            "out": ctx.rel(self.out),
            "logs": ctx.rel(self.logs),
            "tmp": ctx.rel(self.tmp),
            "home": ctx.rel(self.home),
            "cache": ctx.rel(self.cache),
        }


@dataclass
class ProcResult:
    argv: list[str]
    returncode: int | None
    stdout: bytes
    stderr: bytes
    duration_s: float
    timed_out: bool
    timeout_reason: str = ""
    stdout_log: str = ""
    stderr_log: str = ""

    @property
    def stdout_text(self) -> str:
        return self.stdout.decode("utf-8", errors="replace")

    @property
    def stderr_text(self) -> str:
        return self.stderr.decode("utf-8", errors="replace")


@dataclass
class _Steps:
    """Kurzer Nachweis, was ein Installationslauf tatsaechlich getan hat."""

    entries: list[dict[str, Any]] = field(default_factory=list)

    def add(self, step: str, *, exit_code: int | None, duration_s: float, detail: str = "") -> None:
        self.entries.append(
            {"step": step, "exit": exit_code, "duration_s": round(duration_s, 3), "detail": detail[:400]}
        )

    def to_list(self) -> list[dict[str, Any]]:
        return self.entries[:32]


class ReaLimb(LimbBase):
    name = "rea"
    version = "1.0.0"
    description = "REA-Subagent: Reverse Engineering in eigener Sandbox (install/doctor/capabilities/analyze)"

    def handlers(self) -> dict[str, Callable[[Mapping[str, Any], LimbContext], Mapping[str, Any]]]:
        return {
            "rea.ping": self._ping,
            "rea.install": self._install,
            "rea.doctor": self._doctor,
            "rea.capabilities": self._capabilities,
            "rea.analyze": self._analyze,
        }

    # =================================================================== #
    # Gemeinsame Bausteine
    # =================================================================== #
    def _layout(self, ctx: LimbContext, *, create: bool) -> Layout:
        layout = Layout(
            install=ctx.resolve("rea"),
            targets=ctx.resolve("targets"),
            out=ctx.resolve("out"),
            logs=ctx.resolve("logs"),
            tmp=ctx.resolve("tmp"),
            home=ctx.resolve("home"),
            cache=ctx.resolve("cache"),
        )
        if create:
            for path in layout.dirs():
                path.mkdir(parents=True, exist_ok=True)
        return layout

    def _read_marker(self, layout: Layout) -> dict[str, Any] | None:
        if not layout.marker.is_file():
            return None
        try:
            data = json.loads(layout.marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _entrypoint(self, layout: Layout) -> tuple[Path, dict[str, Any]]:
        marker = self._read_marker(layout)
        if marker is None:
            raise LimbError(
                ErrorCode.PATH_NOT_FOUND,
                "REA ist in dieser Sandbox nicht installiert.",
                hint="Zuerst 'rea.install' zustellen (Parameter source=git|npm, constraints.allow_network=true).",
            )
        entry = layout.install / str(marker.get("entrypoint") or "")
        if not marker.get("entrypoint") or not entry.is_file():
            raise LimbError(
                ErrorCode.PATH_NOT_FOUND,
                f"Installationsmarker zeigt auf einen fehlenden Einstiegspunkt: {entry.name}",
                hint="Installation mit force=true wiederholen.",
            )
        return entry, marker

    def _node(self) -> str:
        node = os.environ.get("NEU_NODE_BIN") or shutil.which("node")
        if not node:
            raise LimbError(
                ErrorCode.PATH_NOT_FOUND,
                "Node.js wurde nicht gefunden (REA 6.x verlangt Node 22.19+, 24.11+ oder 26+).",
                hint="Node installieren oder NEU_NODE_BIN auf die ausfuehrbare Datei setzen.",
            )
        return node

    def _node_version(self, node: str) -> str:
        try:
            done = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.SubprocessError):
            return ""
        return (done.stdout or "").strip().lstrip("v")

    def _env(self, layout: Layout) -> dict[str, str]:
        """Umgebung mit eigenem Zuhause: kein Schreibzugriff ausserhalb der Sandbox."""
        env = dict(os.environ)
        cache = layout.cache
        env.update(
            {
                "HOME": str(layout.home),
                "TMPDIR": str(layout.tmp),
                "TMP": str(layout.tmp),
                "TEMP": str(layout.tmp),
                "XDG_CACHE_HOME": str(cache),
                "XDG_CONFIG_HOME": str(layout.home / ".config"),
                "XDG_DATA_HOME": str(layout.home / ".local" / "share"),
                "npm_config_cache": str(cache / "npm"),
                "npm_config_update_notifier": "false",
                "npm_config_fund": "false",
                "npm_config_audit": "false",
                "NO_COLOR": "1",
                "CI": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_NO_INPUT": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        venv_python = layout.install / "pyenv" / "bin" / "python"
        if venv_python.is_file():
            env["REA_PWNTOOLS_PYTHON"] = str(venv_python)
        return env

    def _budget(self, ctx: LimbContext, requested: float | None, *, default: float = DEFAULT_TIMEOUT_S) -> float:
        """Wie lange ein Kindprozess laufen darf -- nie laenger als die Limb-Uhr."""
        budget = default if requested is None else max(1.0, float(requested))
        if ctx.intent.timer.unlimited:
            net = ctx.intent.timer.hard_timeout_s()
            if net is not None:
                budget = min(budget, max(1.0, net - 1.0))
        else:
            soft = ctx.soft_remaining_s()
            if soft is not None:
                # 1 s Vorlauf: das Kind muss *vor* dem Wachhund des Limbs sterben,
                # sonst meldet der Limb einen Timeout, waehrend node noch laeuft.
                budget = min(budget, max(0.5, soft - 1.0))
        return budget

    def _log_name(self, ctx: LimbContext, stem: str, suffix: str) -> str:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        safe = re.sub(r"[^a-z0-9_.-]+", "-", stem.lower()).strip("-")[:60] or "run"
        return f"{stamp}-{intent_suffix(ctx)}-{safe}.{suffix}"

    def _run(
        self,
        ctx: LimbContext,
        layout: Layout,
        argv: Sequence[str],
        *,
        cwd: Path,
        timeout_s: float,
        stem: str,
        max_bytes: int = MAX_CAPTURE_BYTES,
    ) -> ProcResult:
        """Startet ein Kind in eigener Prozessgruppe und beendet die *Gruppe* bei Ablauf."""
        cwd.mkdir(parents=True, exist_ok=True)
        layout.logs.mkdir(parents=True, exist_ok=True)
        out_log = layout.logs / self._log_name(ctx, stem, "stdout.log")
        err_log = layout.logs / self._log_name(ctx, stem, "stderr.log")
        env = self._env(layout)
        started = time.time()
        timed_out = False
        reason = ""
        stdout_buf = bytearray()
        stderr_buf = bytearray()
        lock = threading.Lock()

        with out_log.open("wb") as out_handle, err_log.open("wb") as err_handle:
            try:
                # argv-Liste, kein Shell-Interpolat -- deshalb unkritisch.
                proc = subprocess.Popen(
                    list(argv),
                    cwd=str(cwd),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
            except OSError as exc:
                raise LimbError(ErrorCode.IO, f"Prozess konnte nicht gestartet werden: {exc}", hint="argv/Node-Pfad pruefen.") from exc

            def pump(stream: Any, buffer: bytearray, handle: Any) -> None:
                try:
                    while True:
                        chunk = stream.read(65536)
                        if not chunk:
                            break
                        handle.write(chunk)
                        with lock:
                            room = max_bytes - len(buffer)
                            if room > 0:
                                buffer.extend(chunk[:room])
                finally:
                    with contextlib.suppress(Exception):  # Aufraeumen darf nie werfen
                        stream.close()

            threads = [
                threading.Thread(target=pump, args=(proc.stdout, stdout_buf, out_handle), daemon=True),
                threading.Thread(target=pump, args=(proc.stderr, stderr_buf, err_handle), daemon=True),
            ]
            for thread in threads:
                thread.start()

            while proc.poll() is None:
                if time.time() - started > timeout_s:
                    timed_out, reason = True, "param"
                    break
                if ctx.expired():
                    timed_out, reason = True, "timer"
                    break
                time.sleep(0.05)

            if timed_out:
                _kill_group(proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - SIGKILL ist bereits unterwegs
                _kill_group(proc)
            for thread in threads:
                thread.join(timeout=5)

        return ProcResult(
            argv=list(argv),
            returncode=proc.returncode,
            stdout=bytes(stdout_buf),
            stderr=bytes(stderr_buf),
            duration_s=round(time.time() - started, 3),
            timed_out=timed_out,
            timeout_reason=reason,
            stdout_log=ctx.rel(out_log) if out_log.exists() else "",
            stderr_log=ctx.rel(err_log) if err_log.exists() else "",
        )

    def _reexec(self, ctx: LimbContext, layout: Layout, entry: Path, args: Sequence[str], *, stem: str, timeout_s: float) -> ProcResult:
        node = self._node()
        argv = [node, str(entry), *args]
        return self._run(ctx, layout, argv, cwd=layout.install, timeout_s=timeout_s, stem=stem)

    def _parse_json(self, result: ProcResult) -> dict[str, Any] | None:
        text = result.stdout_text.strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _timeout_output(
        self, ctx: LimbContext, *, what: str, result: ProcResult, done: Sequence[str]
    ) -> dict[str, Any]:
        ctx.note(f"timeout: {what} nach {result.duration_s}s abgebrochen (Grund: {result.timeout_reason or 'unbekannt'})")
        return {
            "__status__": "timeout",
            "__explanation__": (
                f"{what} wurde nach {result.duration_s}s abgebrochen "
                f"({'Limb-Timer' if result.timeout_reason == 'timer' else 'Parameter-Timeout'}). "
                f"Die Prozessgruppe wurde beendet; Rohausgabe liegt in den Logs."
            ),
            "__suggested_next__": "Mit unbegrenzter Zeit (constraints.unlimited / --unlimited) oder kleinerem Umfang wiederholen.",
            "timed_out": True,
            "duration_s": result.duration_s,
            "logs": {"stdout": result.stdout_log, "stderr": result.stderr_log},
            "done_steps": list(done),
            "command": result.argv[1:3],
        }

    def _exec_failure(self, what: str, result: ProcResult, payload: Mapping[str, Any] | None) -> LimbError:
        code = str((payload or {}).get("code") or "")
        message = str((payload or {}).get("message") or "").strip()
        remediation = (payload or {}).get("remediation")
        hint = ""
        if isinstance(remediation, Mapping):
            hint = str(remediation.get("action") or remediation.get("detail") or "")
        elif isinstance(remediation, str):
            hint = remediation
        tail = result.stderr_text.strip().splitlines()[-6:]
        detail = message or (" | ".join(tail) if tail else f"exit={result.returncode}")
        return LimbError(
            _REA_ERRORS.get(code, ErrorCode.INTERNAL),
            f"{what} fehlgeschlagen ({code or result.returncode}): {detail}"[:16000],
            hint=hint or "Logs im Subagenten-Sandbox-Verzeichnis pruefen (logs/).",
        )

    # =================================================================== #
    # rea.ping -- Handshake ohne Nebenwirkungen
    # =================================================================== #
    def _ping(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        layout = self._layout(ctx, create=False)
        marker = self._read_marker(layout)
        node = os.environ.get("NEU_NODE_BIN") or shutil.which("node") or ""
        entry = layout.install / str((marker or {}).get("entrypoint") or "") if marker else None
        installed = bool(marker and entry and entry.is_file())
        venv = layout.install / "pyenv" / "bin" / "python"
        return {
            "limb": self.name,
            "version": self.version,
            "protocol": PROTOCOL_VERSION,
            "sandbox_root": ctx.rel(ctx.sandbox_root),
            "installed": installed,
            "install_hint": "" if installed else "rea.install mit source=git|npm und constraints.allow_network=true zustellen.",
            "rea": {
                "version": (marker or {}).get("version"),
                "source": (marker or {}).get("source"),
                "repository": (marker or {}).get("repository"),
                "entrypoint": (marker or {}).get("entrypoint"),
                "installed_at": (marker or {}).get("installed_at"),
            },
            "node": {"path": node, "version": self._node_version(node) if node else ""},
            "pwntools_python": ctx.rel(venv) if venv.is_file() else None,
            "layout": layout.describe(ctx),
            "operations": sorted(self.handlers()),
            "commands": sorted(COMMANDS),
            "timer_armed": ctx.armed,
        }

    # =================================================================== #
    # rea.install
    # =================================================================== #
    def _install(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        source = str(params.get("source") or "git").strip().lower()
        if source not in {"git", "npm"}:
            raise LimbError(ErrorCode.SCHEMA_INVALID, "params.source muss 'git' oder 'npm' sein.", hint=f"gefunden: {source!r}")
        repository = str(params.get("repository") or REA_REPOSITORY)
        ref = str(params.get("ref") or "").strip()
        package = str(params.get("package") or REA_PACKAGE)
        package_version = str(params.get("package_version") or "").strip()
        build = _bool_param(params, "build", True)
        force = _bool_param(params, "force", False)
        with_pwntools = _bool_param(params, "with_pwntools", False)
        python_bin = str(params.get("python") or sys.executable)
        timeout_s = self._budget(ctx, _opt_float(params, "timeout_s"), default=1800.0)

        layout = self._layout(ctx, create=False)
        marker = self._read_marker(layout)
        reuse_only = False
        if marker and not force:
            entry = layout.install / str(marker.get("entrypoint") or "")
            if entry.is_file():
                wants_pwntools = with_pwntools and not bool((marker.get("pwntools") or {}).get("ok"))
                if not wants_pwntools:
                    return {
                        "installed": True,
                        "reused": True,
                        "source": marker.get("source"),
                        "version": marker.get("version"),
                        "entrypoint": marker.get("entrypoint"),
                        "pwntools": marker.get("pwntools"),
                        "sandbox_root": ctx.rel(ctx.sandbox_root),
                        "note": "Bereits installiert; force=true installiert neu.",
                    }
                # Installation steht, nur die optionale Zutat fehlt: nicht neu
                # klonen, nur das venv nachziehen.
                reuse_only = True

        if ctx.intent.constraints.dry_run:
            return {
                "dry_run": True,
                "would": {
                    "source": source,
                    "repository": repository if source == "git" else package,
                    "ref": ref,
                    "build": build if source == "git" else False,
                    "with_pwntools": with_pwntools,
                    "target": ctx.rel(layout.install),
                },
                "note": "dry_run=true: kein Prozess gestartet, kein Byte geschrieben.",
            }

        if not ctx.intent.constraints.allow_network:
            raise LimbError(
                ErrorCode.POLICY_DENIED,
                "rea.install braucht Netzwerkzugriff, aber constraints.allow_network ist false.",
                hint="Intent mit allow_network=true zustellen (CLI: --allow-network).",
            )

        node = self._node()
        layout = self._layout(ctx, create=True)
        plan = [
            "Sandbox-Layout anlegen",
            f"REA aus {source} installieren",
            "Version verifizieren",
            "pwntools-venv (optional)",
            "Installationsmarker schreiben",
        ]
        ctx.plan(*plan)
        ctx.checkpoint("Sandbox-Layout angelegt")

        if not reuse_only and layout.install.exists() and any(layout.install.iterdir()):
            previous = self._read_marker(layout)
            if previous is None:
                raise LimbError(
                    ErrorCode.ALREADY_EXISTS,
                    f"{ctx.rel(layout.install)} ist nicht leer und gehoert nicht diesem Subagenten (kein Marker).",
                    hint="Anderes Sandbox-Verzeichnis waehlen; dieser Limb loescht keine fremden Baeume.",
                )
            if not force:
                raise LimbError(ErrorCode.ALREADY_EXISTS, "Installationsverzeichnis ist belegt.", hint="force=true zum Neuinstallieren.")
            shutil.rmtree(layout.install)
            layout.install.mkdir(parents=True, exist_ok=True)

        started = time.time()
        steps = _Steps()
        entry_rel = ""
        version = ""

        if reuse_only:
            assert marker is not None  # reuse_only wird nur mit Marker gesetzt
            entry_rel = str(marker.get("entrypoint") or "")
            version = str(marker.get("version") or "")
            for previous in (marker.get("steps") or [])[:16]:
                if isinstance(previous, Mapping):
                    steps.entries.append(dict(previous))
            steps.add("Installation wiederverwendet", exit_code=0, duration_s=0.0, detail="nur pwntools-venv nachgezogen")
        elif source == "git":
            entry_rel, version = self._install_git(
                ctx, layout, repository=repository, ref=ref, build=build, steps=steps, deadline=started + timeout_s
            )
        else:
            entry_rel, version = self._install_npm(
                ctx, layout, package=package, version=package_version, steps=steps, deadline=started + timeout_s
            )
        ctx.checkpoint("REA installiert")

        pwntools: dict[str, Any] = {"ok": False, "reason": "nicht angefordert"}
        if with_pwntools:
            pwntools = self._install_pwntools(ctx, layout, python_bin=python_bin, steps=steps, deadline=started + timeout_s)

        marker_payload = {
            "schema": "neu.rea-install/1",
            "source": source,
            "repository": repository if source == "git" else "",
            "ref": ref,
            "package": package if source == "npm" else "",
            "entrypoint": entry_rel,
            "version": version,
            "node": {"path": node, "version": self._node_version(node)},
            "pwntools": pwntools,
            "installed_at": (marker or {}).get("installed_at") if reuse_only else utc_now_iso(),
            "duration_s": round(time.time() - started, 3),
            "steps": steps.to_list(),
        }
        ctx.write_atomic(layout.marker, json.dumps(marker_payload, indent=2, ensure_ascii=False) + "\n")
        marker_artifact = ctx.record(layout.marker, "created")
        ctx.finish_step("Version verifizieren")
        ctx.finish_step("pwntools-venv (optional)")
        ctx.finish_step("Installationsmarker schreiben")

        # Protokoll 1.2 kennt als Artefakt-Aktionen nur created/modified/deleted/
        # read/unchanged. Logs entstehen in diesem Lauf -> "created".
        log_paths: list[str] = []
        for entry in sorted(layout.logs.glob("*.log")):
            if entry.is_file():
                log_paths.append(ctx.record(entry, "created").path)

        return {
            "installed": True,
            "reused": False,
            "source": source,
            "version": version,
            "entrypoint": entry_rel,
            "pwntools": pwntools,
            "duration_s": round(time.time() - started, 3),
            "steps": steps.to_list(),
            "marker": ctx.rel(layout.marker),
            "marker_sha256": marker_artifact.sha256,
            "sandbox_root": ctx.rel(ctx.sandbox_root),
            "logs": log_paths[-6:],
        }

    def _install_git(
        self,
        ctx: LimbContext,
        layout: Layout,
        *,
        repository: str,
        ref: str,
        build: bool,
        steps: _Steps,
        deadline: float,
    ) -> tuple[str, str]:
        layout.install.mkdir(parents=True, exist_ok=True)
        git = shutil.which("git")
        if not git:
            raise LimbError(ErrorCode.PATH_NOT_FOUND, "git wurde nicht gefunden.", hint="git installieren oder source=npm nutzen.")
        if not any(layout.install.iterdir()):
            clone = [git, "clone", "--depth", "1", "--quiet"]
            if ref:
                clone += ["--branch", ref]
            clone += [repository, str(layout.install)]
            result = self._run(ctx, layout, clone, cwd=layout.install.parent, timeout_s=_left(deadline), stem="git-clone")
            steps.add("git clone", exit_code=result.returncode, duration_s=result.duration_s)
            if result.returncode != 0:
                raise LimbError(ErrorCode.IO, f"git clone fehlgeschlagen: {_tail(result.stderr_text)}", hint=f"Repository/Ref pruefen: {repository} {ref}")
        else:
            fetch_ref = ref or "HEAD"
            fetch = [git, "-C", str(layout.install), "fetch", "--depth", "1", "origin", fetch_ref]
            step = self._run(ctx, layout, fetch, cwd=layout.install, timeout_s=_left(deadline), stem="git-fetch")
            steps.add("git fetch", exit_code=step.returncode, duration_s=step.duration_s)
            if step.returncode != 0:
                raise LimbError(ErrorCode.IO, f"git fetch fehlgeschlagen: {_tail(step.stderr_text)}", hint="force=true fuer einen frischen Klon.")
            checkout = [git, "-C", str(layout.install), "checkout", "--quiet", "FETCH_HEAD"]
            step = self._run(ctx, layout, checkout, cwd=layout.install, timeout_s=_left(deadline), stem="git-checkout")
            steps.add("git checkout", exit_code=step.returncode, duration_s=step.duration_s)
        ctx.checkpoint("Quellbaum bereitgestellt")

        npm = self._npm()
        ci = [npm, "ci", "--no-audit", "--no-fund", "--progress=false"]
        step = self._run(ctx, layout, ci, cwd=layout.install, timeout_s=_left(deadline), stem="npm-ci")
        steps.add("npm ci", exit_code=step.returncode, duration_s=step.duration_s)
        if step.returncode != 0:
            raise LimbError(ErrorCode.IO, f"npm ci fehlgeschlagen: {_tail(step.stderr_text)}", hint="Netzwerk/Registry pruefen (allow_network=true).")
        ctx.checkpoint("Abhaengigkeiten installiert")

        if build:
            step = self._run(ctx, layout, [npm, "run", "build"], cwd=layout.install, timeout_s=_left(deadline), stem="npm-build")
            steps.add("npm run build", exit_code=step.returncode, duration_s=step.duration_s)
            if step.returncode != 0:
                raise LimbError(ErrorCode.IO, f"npm run build fehlgeschlagen: {_tail(step.stderr_text)}", hint="Node-Version pruefen (22.19+/24.11+/26+).")
            ctx.checkpoint("REA gebaut")

        entry_rel = "scripts/rea.mjs"
        entry = layout.install / entry_rel
        if not entry.is_file():
            raise LimbError(ErrorCode.PATH_NOT_FOUND, f"Einstiegspunkt fehlt nach dem Bau: {entry_rel}", hint="build=true setzen.")
        version = self._probe_version(ctx, layout, entry)
        return entry_rel, version

    def _install_npm(
        self,
        ctx: LimbContext,
        layout: Layout,
        *,
        package: str,
        version: str,
        steps: _Steps,
        deadline: float,
    ) -> tuple[str, str]:
        npm = self._npm()
        spec = f"{package}@{version}" if version else package
        install = [npm, "install", "--prefix", str(layout.install), "--no-audit", "--no-fund", "--no-save", "--progress=false", spec]
        result = self._run(ctx, layout, install, cwd=layout.install, timeout_s=_left(deadline), stem="npm-install")
        steps.add(f"npm install {spec}", exit_code=result.returncode, duration_s=result.duration_s)
        if result.returncode != 0:
            raise LimbError(ErrorCode.IO, f"npm install fehlgeschlagen: {_tail(result.stderr_text)}", hint="Netzwerk/Registry pruefen.")
        ctx.checkpoint("npm-Paket installiert")
        entry_rel = f"node_modules/{package}/scripts/rea.mjs"
        entry = layout.install / entry_rel
        if not entry.is_file():
            raise LimbError(ErrorCode.PATH_NOT_FOUND, f"Einstiegspunkt fehlt: {entry_rel}", hint="Paketname/Version pruefen.")
        version_found = self._probe_version(ctx, layout, entry)
        return entry_rel, version_found

    def _install_pwntools(
        self, ctx: LimbContext, layout: Layout, *, python_bin: str, steps: _Steps, deadline: float
    ) -> dict[str, Any]:
        venv = layout.install / "pyenv"
        venv_python = venv / "bin" / "python"
        try:
            if not venv_python.is_file():
                step = self._run(
                    ctx, layout, [python_bin, "-m", "venv", str(venv)],
                    cwd=layout.install, timeout_s=_left(deadline), stem="pyenv-venv",
                )
                steps.add("python -m venv pyenv", exit_code=step.returncode, duration_s=step.duration_s)
                if step.returncode != 0:
                    return {"ok": False, "reason": f"venv fehlgeschlagen: {_tail(step.stderr_text)}"}
            pip_cmd = [str(venv_python), "-m", "pip", "install", "--no-input", *PWNTOOLS_PACKAGES]
            step = self._run(ctx, layout, pip_cmd, cwd=layout.install, timeout_s=_left(deadline), stem="pyenv-pip")
            steps.add("pip install pwntools", exit_code=step.returncode, duration_s=step.duration_s)
            if step.returncode != 0:
                return {"ok": False, "reason": f"pip fehlgeschlagen: {_tail(step.stderr_text)}"}
        except LimbError as exc:
            return {"ok": False, "reason": exc.message}
        ctx.checkpoint("pwntools-venv bereitgestellt")
        return {"ok": True, "python": ctx.rel(venv_python), "packages": list(PWNTOOLS_PACKAGES)}

    def _npm(self) -> str:
        npm = shutil.which("npm")
        if not npm:
            raise LimbError(ErrorCode.PATH_NOT_FOUND, "npm wurde nicht gefunden.", hint="Node.js inkl. npm installieren.")
        return npm

    def _probe_version(self, ctx: LimbContext, layout: Layout, entry: Path) -> str:
        result = self._reexec(ctx, layout, entry, ["--version"], stem="rea-version", timeout_s=120.0)
        text = result.stdout_text.strip()
        return text.splitlines()[-1].strip() if text else ""

    # =================================================================== #
    # rea.doctor / rea.capabilities
    # =================================================================== #
    def _engine_call(
        self, ctx: LimbContext, args: Sequence[str], *, stem: str, timeout_s: float | None = None
    ) -> tuple[dict[str, Any], ProcResult, Layout]:
        # Rueckgabe: (Payload, Prozess, Layout) -- der Aufrufer entscheidet ueber Timeout.
        layout = self._layout(ctx, create=True)
        entry, _marker = self._entrypoint(layout)
        budget = self._budget(ctx, timeout_s, default=300.0)
        result = self._reexec(ctx, layout, entry, list(args), stem=stem, timeout_s=budget)
        payload = self._parse_json(result)
        if result.timed_out:
            return {}, result, layout
        if payload is None:
            raise LimbError(
                ErrorCode.INTERNAL,
                f"REA lieferte kein JSON ({stem}, exit={result.returncode}): {_tail(result.stderr_text)}",
                hint="Logs pruefen; ggf. Installation erneuern.",
            )
        return payload, result, layout

    def _doctor(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        args = ["doctor", "--format", "json"]
        provider = _opt_str(params, "provider")
        if provider:
            args += ["--provider", provider]
        target = _opt_str(params, "target")
        if target:
            args += ["--target", str(ctx.resolve(target, where="$.task.params.target", must_exist=True))]
        ctx.plan("rea doctor ausfuehren", "Befunde verdichten")
        payload, result, layout = self._engine_call(ctx, args, stem="doctor", timeout_s=_opt_float(params, "timeout_s"))
        if result.timed_out:
            return self._timeout_output(ctx, what="rea doctor", result=result, done=ctx.done)
        ctx.finish_step("rea doctor ausfuehren")

        checks = payload.get("scope_checks") or []
        failed = [
            {"name": c.get("name"), "classification": c.get("classification"), "remediation": c.get("remediation")}
            for c in checks
            if isinstance(c, Mapping) and not c.get("ok")
        ]
        report_path = layout.out / self._log_name(ctx, "doctor", "json")
        ctx.write_atomic(report_path, json.dumps(payload, indent=2, ensure_ascii=False))
        ctx.record(report_path, "created")
        ctx.finish_step("Befunde verdichten")
        return {
            "healthy": payload.get("healthy"),
            "environment_healthy": payload.get("environment_healthy"),
            "checks": [
                {"name": c.get("name"), "ok": c.get("ok"), "classification": c.get("classification")}
                for c in checks
                if isinstance(c, Mapping)
            ][:MAX_SUMMARY_ITEMS],
            "failed_checks": failed[:MAX_SUMMARY_ITEMS],
            "recommendation": payload.get("recommendation"),
            "report": ctx.rel(report_path),
            "duration_s": result.duration_s,
            "logs": {"stdout": result.stdout_log, "stderr": result.stderr_log},
        }

    def _capabilities(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        ctx.plan("rea capabilities abfragen", "Matrix verdichten")
        payload, result, _layout = self._engine_call(
            ctx, ["capabilities", "--format", "json"], stem="capabilities", timeout_s=_opt_float(params, "timeout_s")
        )
        if result.timed_out:
            return self._timeout_output(ctx, what="rea capabilities", result=result, done=ctx.done)
        ctx.finish_step("rea capabilities abfragen")

        entries = payload.get("capabilities") or []
        available = [c.get("operation") for c in entries if isinstance(c, Mapping) and c.get("available")]
        blocked: Counter[str] = Counter(
            str(c.get("availability_code") or "unavailable") for c in entries if isinstance(c, Mapping) and not c.get("available")
        )
        side_effects: Counter[str] = Counter()
        for item in entries:
            if not isinstance(item, Mapping) or not item.get("available"):
                continue
            effects = item.get("effects") or {}
            if isinstance(effects, Mapping):
                for key, value in effects.items():
                    if value is True:
                        side_effects[str(key)] += 1
        ctx.finish_step("Matrix verdichten")
        return {
            "provider": (payload.get("provider") or {}).get("id"),
            "providers": [p.get("id") for p in (payload.get("providers") or []) if isinstance(p, Mapping)],
            "operations_total": len(entries),
            "operations_available": sorted(str(name) for name in available if name)[:200],
            "unavailable_reasons": dict(blocked.most_common(MAX_SUMMARY_ITEMS)),
            "side_effects": dict(side_effects.most_common(MAX_SUMMARY_ITEMS)),
            "duration_s": result.duration_s,
            "logs": {"stdout": result.stdout_log, "stderr": result.stderr_log},
        }

    # =================================================================== #
    # rea.analyze -- genau ein freigegebenes Kommando
    # =================================================================== #
    def _analyze(self, params: Mapping[str, Any], ctx: LimbContext) -> dict[str, Any]:
        command = str(params.get("command") or "").strip()
        spec = COMMANDS.get(command)
        if spec is None:
            raise LimbError(
                ErrorCode.UNSUPPORTED_OP,
                f"REA-Kommando '{command}' ist fuer diesen Subagenten nicht freigegeben.",
                hint=f"Erlaubt: {', '.join(sorted(COMMANDS))}",
            )

        raw_paths = _path_params(params, spec)
        paths: list[Path] = []
        for index, raw in enumerate(raw_paths):
            must_exist = command not in {"evidence-export"}
            paths.append(ctx.resolve(raw, where=f"$.task.params.paths[{index}]", must_exist=must_exist))
        if len(paths) != spec.path_args:
            raise LimbError(
                ErrorCode.SCHEMA_INVALID,
                f"'{command}' erwartet {spec.path_args} Pfadargument(e), bekommen: {len(paths)}.",
                hint=f"Form: {spec.shape()}",
            )

        literals = params.get("args") or []
        if not isinstance(literals, Sequence) or isinstance(literals, (str, bytes)):
            raise LimbError(ErrorCode.SCHEMA_INVALID, "params.args muss eine Liste von Zeichenketten sein.")
        literals = [str(item) for item in literals]
        if len(literals) != spec.literals:
            raise LimbError(
                ErrorCode.SCHEMA_INVALID,
                f"'{command}' erwartet {spec.literals} Literal-Argument(e) in params.args, bekommen: {len(literals)}.",
                hint=f"Form: {spec.shape()}",
            )

        options = params.get("options") or {}
        if not isinstance(options, Mapping):
            raise LimbError(ErrorCode.SCHEMA_INVALID, "params.options muss ein Objekt sein.")
        unknown = sorted(set(options) - set(spec.flags))
        if unknown:
            raise LimbError(
                ErrorCode.SCHEMA_INVALID,
                f"Option(en) {unknown} sind fuer '{command}' nicht freigegeben.",
                hint=f"Erlaubt: {list(spec.flags)}",
            )

        argv: list[str] = [command, *[str(p) for p in paths], *literals]
        for key, value in options.items():
            flag = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    argv.append(flag)
            else:
                argv.extend([flag, str(value)])
        argv += ["--format", "json"]

        layout = self._layout(ctx, create=True)
        entry, marker = self._entrypoint(layout)
        timeout_s = self._budget(ctx, _opt_float(params, "timeout_s"))

        if ctx.intent.constraints.dry_run:
            return {
                "dry_run": True,
                "command": command,
                "argv": [str(entry), *argv],
                "sandbox_root": ctx.rel(ctx.sandbox_root),
                "note": "dry_run=true: kein REA-Prozess gestartet.",
            }

        ctx.plan(f"rea {command} ausfuehren", "Evidence verdichten", "Rohbeleg ablegen")
        result = self._reexec(ctx, layout, entry, argv, stem=command, timeout_s=timeout_s)
        if result.timed_out:
            return self._timeout_output(ctx, what=f"rea {command}", result=result, done=ctx.done)

        payload = self._parse_json(result)
        if payload is None:
            raise LimbError(
                ErrorCode.INTERNAL,
                f"rea {command} lieferte kein JSON (exit={result.returncode}): {_tail(result.stderr_text)}",
                hint="Rohausgabe in logs/ pruefen.",
            )
        if result.returncode != 0 or payload.get("code"):
            raise self._exec_failure(f"rea {command}", result, payload)
        ctx.checkpoint(f"rea {command} ausgefuehrt")

        out_param = _opt_str(params, "out")
        out_path = ctx.resolve(out_param, where="$.task.params.out") if out_param else layout.out / self._log_name(ctx, command, "json")
        raw_text = json.dumps(payload, indent=2, ensure_ascii=False)
        ctx.write_atomic(out_path, raw_text + "\n")
        artifact = ctx.record(out_path, "created")
        summary = summarize_evidence(payload, mode=str(params.get("summary_mode") or "full"))
        ctx.finish_step("Evidence verdichten")
        ctx.finish_step("Rohbeleg ablegen")
        return {
            "command": command,
            "exit_code": result.returncode,
            "duration_s": result.duration_s,
            "rea_version": (marker or {}).get("version"),
            "evidence_id": payload.get("evidence_id"),
            "raw": {
                "path": ctx.rel(out_path),
                "bytes": artifact.bytes,
                "sha256": artifact.sha256,
                "truncated": len(result.stdout) >= MAX_CAPTURE_BYTES,
            },
            "logs": {"stdout": result.stdout_log, "stderr": result.stderr_log},
            "summary": summary,
        }


# ======================================================================= #
# Hilfsfunktionen
# ======================================================================= #
def intent_suffix(ctx: LimbContext) -> str:
    raw = str(getattr(ctx.intent, "intent_id", "") or "intent")
    return re.sub(r"[^A-Za-z0-9_-]+", "", raw)[-12:] or "intent"


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(OSError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    with contextlib.suppress(OSError):
        proc.kill()


def _left(deadline: float) -> float:
    return max(1.0, deadline - time.time())


def _tail(text: str, lines: int = 6) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    return " | ".join(stripped.splitlines()[-lines:])[:1200]


def _opt_str(params: Mapping[str, Any], key: str) -> str:
    value = params.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _opt_float(params: Mapping[str, Any], key: str) -> float | None:
    value = params.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise LimbError(ErrorCode.SCHEMA_INVALID, f"params.{key} muss eine Zahl sein.", hint=f"gefunden: {value!r}") from exc


def _bool_param(params: Mapping[str, Any], key: str, default: bool) -> bool:
    value = params.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "ja", "on"}
    return bool(value)


def _path_params(params: Mapping[str, Any], spec: ReaCommand) -> list[str]:
    """Sammelt ``target`` und ``paths[]`` in stabiler Reihenfolge."""
    raw: list[str] = []
    target = params.get("target")
    if target not in (None, ""):
        raw.append(str(target))
    extra = params.get("paths") or []
    if isinstance(extra, Sequence) and not isinstance(extra, (str, bytes)):
        raw.extend(str(item) for item in extra)
    elif extra:
        raise LimbError(ErrorCode.SCHEMA_INVALID, "params.paths muss eine Liste sein.")
    return raw


def _top(counter: Counter[str], limit: int = MAX_SUMMARY_ITEMS) -> dict[str, int]:
    return {str(key): int(value) for key, value in counter.most_common(limit)}


def summarize_evidence(payload: Mapping[str, Any], *, mode: str = "full") -> dict[str, Any]:
    """Verdichtet eine REA-Evidence auf das, was ein Kern zum Weiterarbeiten braucht.

    Bewusst klein: Der Vollbeleg liegt als Artefakt daneben. Hier stehen Identitaet
    (Hash, Evidence-ID), Form (Knoten/Kanten nach Art), Luecken (unknowns) und die
    Grenzen der Aussage -- nicht 8 MB JSON im Result.
    """
    summary: dict[str, Any] = {
        "evidence_id": payload.get("evidence_id"),
        "operation": payload.get("operation"),
        "predicate_type": payload.get("predicate_type"),
        "confidence": payload.get("confidence"),
    }
    provider = payload.get("provider") or {}
    if isinstance(provider, Mapping):
        summary["provider"] = {"id": provider.get("id"), "version": provider.get("version")}
    subject = payload.get("subject") or {}
    if isinstance(subject, Mapping):
        digest = subject.get("digest") or {}
        summary["subject"] = {
            "name": subject.get("name"),
            "format": subject.get("format"),
            "sha256": digest.get("sha256") if isinstance(digest, Mapping) else None,
        }

    result = payload.get("normalized_result")
    if isinstance(result, Mapping):
        graph = result.get("graph")
        if isinstance(graph, Mapping):
            nodes = graph.get("nodes") or []
            kinds = Counter(str(node.get("kind") or "?") for node in nodes if isinstance(node, Mapping))
            summary["application_graph"] = {
                "nodes": len(nodes),
                "edges": len(graph.get("edges") or []),
                "kinds": _top(kinds),
                "root_nodes": len(graph.get("root_node_ids") or []),
            }
        semantic = result.get("semantic_graph")
        if isinstance(semantic, Mapping):
            nodes = semantic.get("nodes") or []
            kinds = Counter(str(node.get("kind") or "?") for node in nodes if isinstance(node, Mapping))
            unknowns = [u for u in (semantic.get("unknowns") or []) if isinstance(u, Mapping)]
            reasons = Counter(str(u.get("reason") or "?") for u in unknowns)
            named = [
                {
                    "label": node.get("label"),
                    "module": ((node.get("identity") or {}) if isinstance(node.get("identity"), Mapping) else {}).get("module_path"),
                }
                for node in nodes
                if isinstance(node, Mapping) and node.get("kind") == "function" and node.get("label")
            ]
            summary["semantic_graph"] = {
                "nodes": len(nodes),
                "kinds": _top(kinds),
                "relations": len(semantic.get("relations") or []),
                "unknowns": len(unknowns),
                "unknown_reasons": _top(reasons, 6),
                "named_functions": named[:MAX_SUMMARY_ITEMS],
                "coverage": (semantic.get("coverage") or {}).get("status") if isinstance(semantic.get("coverage"), Mapping) else None,
            }
        # Binärformat-Provider (pwntools-ELF, PE/CLI, Mach-O) liefern kein
        # Anwendungsgraph-Objekt, sondern Abschnitte/Segmente/Symbole. Ohne
        # diesen Zweig waere die Zusammenfassung fuer den Native-Fall leer.
        if isinstance(result.get("sections"), list) or result.get("format") in {"elf", "macho", "pe"}:
            summary["binary_layout"] = _summarize_binary(result)
        statistics = result.get("statistics")
        if isinstance(statistics, Mapping):
            summary["statistics"] = dict(list(statistics.items())[:24])
        app_summary = result.get("summary")
        if isinstance(app_summary, Mapping):
            summary["application_summary"] = {
                key: value
                for key, value in app_summary.items()
                if isinstance(value, (int, float, str, bool)) and value not in (0, "", None, False)
            }
    if mode != "full":
        summary.pop("application_summary", None)

    limitations = [str(item) for item in (payload.get("limitations") or [])][:6]
    if limitations:
        summary["limitations"] = limitations
    if payload.get("code"):
        summary["error"] = {"code": payload.get("code"), "message": payload.get("message")}
    return summary




def _name_of(entry: Any) -> str:
    """REA legt Namen als ``{display, bytes_base64}`` ab -- nur ``display`` lesen."""
    if isinstance(entry, Mapping):
        name = entry.get("display")
        return str(name) if name else ""
    return ""


def _summarize_binary(result: Mapping[str, Any]) -> dict[str, Any]:
    sections = [item for item in (result.get("sections") or []) if isinstance(item, Mapping)]
    segments = [item for item in (result.get("segments") or []) if isinstance(item, Mapping)]
    symbols = [item for item in (result.get("symbols") or []) if isinstance(item, Mapping)]
    relocations = result.get("relocations") or []
    raw_linkage = result.get("linkage")
    linkage: dict[str, Any] = dict(raw_linkage) if isinstance(raw_linkage, Mapping) else {}
    raw_mitigations = result.get("mitigations")
    mitigations: dict[str, Any] = dict(raw_mitigations) if isinstance(raw_mitigations, Mapping) else {}
    raw_entry = result.get("entry_point")
    entry: dict[str, Any] = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
    names = [_name_of(item.get("name")) for item in sections]
    symbol_names = []
    for item in symbols:
        name = _name_of(item.get("name"))
        if name:
            symbol_names.append(name)
    return {
        "format": result.get("format"),
        "architecture": dict(result.get("architecture") or {}) if isinstance(result.get("architecture"), Mapping) else {},
        "image_type": result.get("image_type"),
        "entry_point": entry.get("reported_value"),
        "sections": {"count": len(sections), "named": [n for n in names if n][:MAX_SUMMARY_ITEMS]},
        "segments": {
            "count": len(segments),
            "types": _top(Counter(str(item.get("type") or "?") for item in segments), 8),
        },
        "symbols": {"count": len(symbols), "named": symbol_names[:MAX_SUMMARY_ITEMS]},
        "relocations": len(relocations),
        "mitigations": {key: value for key, value in mitigations.items() if key != "evidence_kind"},
        "needed_libraries": list(linkage.get("needed_libraries") or [])[:MAX_SUMMARY_ITEMS]
        if isinstance(linkage.get("needed_libraries"), list)
        else [],
    }



if __name__ == "__main__":
    sys.exit(ReaLimb().main())
