"""Trading-Limb (Phase 5) -- Sigma als eigener Handels-Knoten.

Sigma (https://github.com/Finnlayy/Sigma) ist die deterministische, vollstaendig
getestete Handels-Engine: TradingView-Scraper, tvremix/TradingView-MCP
(CSV-Interchange), DuckDB/Parquet-Lake und die 912-Test-Suite. Was Sigma
*fehlt*, ist genau das, was NEU besitzt: ein Orchestrator. Sigma ist ein
FastAPI-Dienst ohne Lebenszyklus-Verwaltung, ohne Sandbox und ohne
Intent/Result-Protokoll.

Dieser Limb ist deshalb **kein Fork und kein Vendor-Drop**, sondern der Adapter:

    Intent  ->  trading_limb  ->  HTTP (stdlib urllib)  ->  Sigma-Worker
            <-  Result      <-                          <-

Damit bleiben Sigmas 912 Tests unveraendert der Vertrag (wir patchen nichts),
waehrend NEU Lebenszyklus, Timeouts, Prozessgruppe und Nachweise stellt.

Aufgabenprofil:

* ``trading.ping``            -- Ist Sigma installiert? Laeuft der Worker?
* ``trading.install``         -- Sigma auf gepinntem Commit klonen + venv + deps.
* ``trading.start``           -- Worker als eigene Prozessgruppe starten.
* ``trading.stop``            -- Prozessgruppe beenden (TERM, dann KILL).
* ``trading.status``          -- Health + Lake-Kurzfassung als Nachweis.
* ``trading.lake_summary``    -- Parquet-Inventar (Zeilen, Dateien, MB, Symbole).
* ``trading.lake_compact``    -- Partitionen nach Parquet verdichten.
* ``trading.backtest_run``    -- Backtest ueber den TV-MCP-CSV-Pfad.

Grenzen (warum das sicher ist):

1. **Kein Shell-String.** Jedes Kommando ist eine argv-Liste.
2. **Pfade durch die Policy.** ``ctx.resolve()`` haelt alles in der Sandbox.
3. **Eigene Prozessgruppe.** ``start_new_session=True``; ``stop`` beendet die
   Gruppe, damit uvicorn-Kinder nicht verwaisen.
4. **Eigenes Zuhause.** ``HOME``, ``TMPDIR``, ``XDG_CACHE_HOME`` und die
   Sigma-Daten zeigen in die Sandbox -- ein Lauf schreibt nicht ins Host-Home.
5. **Netz nur wo noetig.** ``trading.install`` verlangt Netz; der Betrieb
   spricht ausschliesslich ``127.0.0.1:<port>``.

Aufruf: ``python3 limbs/trading_limb.py --intent runtime/inbox/trading/<id>.json``
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from base import LimbBase, LimbContext, LimbError  # noqa: E402
from core.protocol import ErrorCode  # noqa: E402

#: Sigma-Repository und der gepinnte Commit, gegen den getestet wurde.
SIGMA_REPOSITORY = "https://github.com/Finnlayy/Sigma.git"
SIGMA_REF = "e6635c01cde0b13edaab4ada8a47873ee25d4cbb"
SIGMA_VERSION = "sigma-hybrid-1.0"

#: Privater Port des Workers. Nicht 8000/8001 -- dort lauschen Sigmas eigene
#: Standardwerte bzw. der Contagion-Endpunkt.
DEFAULT_PORT = 8731

INSTALL_MARKER = ".nio-trading-install.json"
PID_FILE = "worker.pid"


@dataclass
class Layout:
    """Verzeichnisvertrag des Trading-Knotens (relativ zur eigenen Sandbox)."""

    install: Path
    venv: Path
    data: Path
    logs: Path
    tmp: Path
    home: Path
    cache: Path

    @property
    def marker(self) -> Path:
        return self.install / INSTALL_MARKER

    @property
    def pid_file(self) -> Path:
        return self.logs / PID_FILE

    @property
    def python(self) -> Path:
        return self.venv / "bin" / "python"

    @property
    def log(self) -> Path:
        return self.logs / "worker.log"

    def dirs(self) -> tuple[Path, ...]:
        return (self.install, self.data, self.logs, self.tmp, self.home, self.cache)


class TradingLimb(LimbBase):
    name = "trading"
    version = "1.0.0"
    description = "Sigma als Handels-Knoten: TV-MCP-Backtests und DuckDB/Parquet-Lake hinter dem NEU-Protokoll."

    # ------------------------------------------------------------- Vertrag
    def handlers(self):
        return {
            "trading.ping": self._ping,
            "trading.install": self._install,
            "trading.start": self._start,
            "trading.stop": self._stop,
            "trading.status": self._status,
            "trading.lake_summary": self._lake_summary,
            "trading.lake_compact": self._lake_compact,
            "trading.backtest_run": self._backtest_run,
        }

    # --------------------------------------------------------------- Layout
    def _layout(self, ctx: LimbContext, *, create: bool) -> Layout:
        layout = Layout(
            install=ctx.resolve("sigma"),
            venv=ctx.resolve("venv"),
            data=ctx.resolve("data"),
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

    def _env(self, layout: Layout, port: int) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(layout.home),
            "TMPDIR": str(layout.tmp),
            "XDG_CACHE_HOME": str(layout.cache),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            # Sigma schreibt ausschliesslich in die Sandbox.
            "SIGMA_DATA_DIR": str(layout.data),
            # Kein echter Broker und kein echter TV-Endpunkt im Limbbetrieb:
            # der Worker startet mit Fakes, damit er ohne Netz hochkommt.
            "SIGMA_ALLOW_FAKE_REDIS": "1",
        }
        return env

    # ----------------------------------------------------------- Werkzeuge
    def _run(
        self,
        ctx: LimbContext,
        layout: Layout,
        argv: list[str],
        *,
        timeout_s: float,
        cwd: Path | None = None,
        check: bool = True,
        step: str = "",
    ) -> subprocess.CompletedProcess[str]:
        """argv-Liste, kein Shell-String. ``check`` meldet Fehlschlaege als LimbError."""
        try:
            proc = subprocess.run(  # noqa: S603 - argv-Liste, kein Shell
                argv,
                cwd=str(cwd or layout.install),
                env=self._env(layout, DEFAULT_PORT),
                capture_output=True,
                text=True,
                timeout=max(1.0, timeout_s),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LimbError(
                ErrorCode.TIMEOUT,
                f"Kommando ueberschritt {timeout_s:.0f}s: {' '.join(argv[:3])}",
                hint="Deadline erhoehen oder Netz pruefen.",
            ) from exc
        except OSError as exc:
            raise LimbError(ErrorCode.IO, f"Kommando nicht startbar: {exc}", hint="Pfad/venv pruefen.") from exc
        if check and proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[-500:]
            raise LimbError(
                ErrorCode.IO,
                f"{step or argv[1] if len(argv) > 1 else argv[0]} fehlgeschlagen (exit {proc.returncode}): {detail}",
                hint="Voraussetzungen pruefen (git, python3-venv, Netz).",
            )
        return proc

    def _budget(self, ctx: LimbContext, default_s: float) -> float:
        remaining = ctx.soft_remaining_s()
        if remaining is None:
            return default_s
        return max(1.0, min(default_s, remaining - 0.5))

    def _port(self, ctx: LimbContext) -> int:
        raw = ctx.intent.task.params.get("port", DEFAULT_PORT)
        try:
            port = int(raw)
        except (TypeError, ValueError):
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"port ist keine Zahl: {raw!r}") from None
        if not 1024 <= port <= 65535:
            raise LimbError(ErrorCode.SCHEMA_INVALID, f"port ausserhalb 1024..65535: {port}")
        return port

    def _request(
        self,
        ctx: LimbContext,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        timeout_s: float = 30.0,
    ) -> dict[str, Any]:
        """stdlib-HTTP gegen den lokalen Worker -- keine dritte Abhaengigkeit."""
        port = self._port(ctx)
        url = f"http://127.0.0.1:{port}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=max(1.0, timeout_s)) as response:  # noqa: S310 - festes 127.0.0.1
                payload = response.read().decode("utf-8", "replace")
                status = response.status
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise LimbError(
                ErrorCode.INTERNAL,
                f"Worker antwortete HTTP {exc.code} auf {path}: {detail}",
                hint="Parameter pruefen (z. B. /api/backtest/ohlc erwartet 'pair', nicht 'symbol').",
            ) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise LimbError(
                ErrorCode.IO,
                f"Worker nicht erreichbar ({url}): {exc}",
                hint="Zuerst trading.start ausfuehren.",
            ) from exc

        if status >= 400:
            raise LimbError(ErrorCode.INTERNAL, f"Worker antwortete HTTP {status} auf {path}")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise LimbError(
                ErrorCode.INTERNAL,
                f"Worker lieferte kein JSON auf {path}: {payload[:200]}",
            ) from exc
        return parsed if isinstance(parsed, dict) else {"data": parsed}

    def _healthy(self, ctx: LimbContext, *, timeout_s: float = 2.0) -> dict[str, Any] | None:
        try:
            return self._request(ctx, "GET", "/api/v1/health", timeout_s=timeout_s)
        except LimbError:
            return None

    # -------------------------------------------------------------- Handler
    def _ping(self, params, ctx: LimbContext):
        layout = self._layout(ctx, create=False)
        marker = self._read_marker(layout)
        port = self._port(ctx)
        health = self._healthy(ctx) if layout.python.is_file() else None
        return {
            "installed": marker is not None,
            "running": health is not None,
            "sigma_ref": (marker or {}).get("ref"),
            "sigma_version": (marker or {}).get("version"),
            "port": port,
            "python": str(layout.python) if layout.python.is_file() else None,
            "health": health,
        }

    def _installed(self, layout: Layout) -> bool:
        """Installation gilt nur, wenn Code *und* Marker *und* Interpreter da sind."""
        return (
            self._read_marker(layout) is not None
            and (layout.install / "app").is_dir()
            and layout.python.is_file()
        )

    def _install(self, params, ctx: LimbContext):
        layout = self._layout(ctx, create=True)
        ref = str(params.get("ref") or SIGMA_REF)
        git = shutil.which("git")
        if not git:
            raise LimbError(ErrorCode.IO, "git ist nicht installiert", hint="git im Image bereitstellen.")

        started = time.time()

        if self._installed(layout):
            marker = self._read_marker(layout) or {}
            return {
                "installed": True,
                "already_present": True,
                "sigma_ref": marker.get("ref"),
                "sigma_version": marker.get("version"),
            }

        ctx.plan("Sigma klonen", "auf Pin setzen", "venv anlegen", "Abhaengigkeiten installieren", "Marker schreiben")

        # Halbe Installationen nie weiterverwenden: der Baum wird neu aufgebaut.
        if layout.install.exists():
            shutil.rmtree(layout.install, ignore_errors=True)
        layout.install.mkdir(parents=True, exist_ok=True)

        # Sigma ist als Repo ~818 MB, davon ~166 MB fremde .deb-Partials.
        # Wir brauchen nur Code: Blobless + Sparse holt ~2.7 MB Arbeitsbaum.
        # 'sigma/' ist ein echtes Importziel (routes_sigma -> sigma.loops).
        self._run(
            ctx, layout,
            [git, "clone", "--depth", "1", "--filter=blob:none", "--sparse",
             SIGMA_REPOSITORY, str(layout.install)],
            timeout_s=self._budget(ctx, 600.0), cwd=layout.install.parent, step="git clone",
        )
        self._run(
            ctx, layout,
            [git, "-C", str(layout.install), "sparse-checkout", "set", "--no-cone",
             "/app/", "/sigma/", "/tests/", "/config/", "/requirements.txt", "/pytest.ini"],
            timeout_s=self._budget(ctx, 300.0), cwd=layout.install, step="sparse-checkout",
        )
        ctx.checkpoint("Sigma geklont")

        # Der Clone steht auf dem Default-Branch. Nur wenn der Pin davon
        # abweicht, wird nachgeladen (GitHub verweigert sonst 'not our ref').
        head = self._run(ctx, layout, [git, "-C", str(layout.install), "rev-parse", "HEAD"],
                         timeout_s=60.0, cwd=layout.install, step="rev-parse HEAD")
        resolved = (head.stdout or "").strip()
        if not resolved.startswith(ref[:12]):
            self._run(ctx, layout, [git, "-C", str(layout.install), "fetch", "--depth", "1", "origin", ref],
                      timeout_s=self._budget(ctx, 300.0), cwd=layout.install, step="git fetch")
            self._run(ctx, layout, [git, "-C", str(layout.install), "checkout", "--quiet", "FETCH_HEAD"],
                      timeout_s=120.0, cwd=layout.install, step="git checkout")
            head = self._run(ctx, layout, [git, "-C", str(layout.install), "rev-parse", "HEAD"],
                             timeout_s=60.0, cwd=layout.install, step="rev-parse HEAD")
            resolved = (head.stdout or "").strip()

        if not resolved.startswith(ref[:12]):
            raise LimbError(
                ErrorCode.INTERNAL,
                f"Checkout steht auf {resolved[:12] or '?'}, erwartet {ref[:12]}",
                hint="Ohne Pin ist die getestete Suite nicht mehr der Vertrag.",
            )
        ctx.checkpoint("Sigma auf Pin gesetzt")

        # Historie braucht danach niemand: 167 MB .git fuer 2.7 MB Code.
        # Die Provenienz steht im Marker; ein Re-Install baut den Baum neu auf.
        shutil.rmtree(layout.install / ".git", ignore_errors=True)

        if not layout.python.is_file():
            self._run(ctx, layout, [sys.executable, "-m", "venv", str(layout.venv)],
                      timeout_s=self._budget(ctx, 300.0), cwd=layout.install, step="python -m venv")
        if not layout.python.is_file():
            raise LimbError(ErrorCode.IO, f"venv ohne Interpreter: {layout.python}",
                            hint="python3-venv im Image installieren.")
        ctx.checkpoint("venv angelegt")

        requirements = layout.install / "requirements.txt"
        if not requirements.is_file():
            raise LimbError(ErrorCode.PATH_NOT_FOUND, f"requirements.txt fehlt in {layout.install}")
        self._run(
            ctx, layout,
            [str(layout.python), "-m", "pip", "install", "--quiet",
             "--disable-pip-version-check", "-r", str(requirements)],
            timeout_s=self._budget(ctx, 900.0), cwd=layout.install, step="pip install",
        )
        ctx.checkpoint("Abhaengigkeiten installiert")

        marker = {
            "ref": ref,
            "resolved_sha": resolved,
            "version": SIGMA_VERSION,
            "repository": SIGMA_REPOSITORY,
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "install_s": round(time.time() - started, 1),
            "install_bytes": self._tree_size(layout.install),
        }
        ctx.write_atomic(layout.marker, json.dumps(marker, indent=2, sort_keys=True) + "\n")
        ctx.record(layout.marker, "created")
        ctx.finish_step("Marker geschrieben")
        return {
            "installed": True,
            "already_present": False,
            "sigma_ref": ref,
            "resolved_sha": resolved,
            "sigma_version": SIGMA_VERSION,
            "install_s": marker["install_s"],
            "install_bytes": marker["install_bytes"],
            "layout": ctx.rel(layout.install),
        }

    def _start(self, params, ctx: LimbContext):
        layout = self._layout(ctx, create=True)
        if not layout.python.is_file():
            raise LimbError(ErrorCode.PATH_NOT_FOUND, "Sigma ist nicht installiert", hint="Zuerst trading.install.")

        port = self._port(ctx)
        if self._healthy(ctx) is not None:
            return {"started": False, "already_running": True, "port": port}

        argv = [
            str(layout.python), "-m", "uvicorn",
            "app.server.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ]
        log_handle = layout.log.open("ab")
        try:
            proc = subprocess.Popen(  # noqa: S603 - argv-Liste
                argv,
                cwd=str(layout.install),
                env=self._env(layout, port),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            log_handle.close()
            raise LimbError(ErrorCode.IO, f"Worker nicht startbar: {exc}") from exc

        layout.pid_file.write_text(str(proc.pid), encoding="utf-8")

        # Auf Health warten, statt blind zu schlafen.
        deadline = time.time() + self._budget(ctx, 120.0)
        while time.time() < deadline:
            if proc.poll() is not None:
                tail = self._tail(layout.log)
                raise LimbError(ErrorCode.LIMB_CRASH,
                                f"Worker beendete sich mit Code {proc.returncode}. {tail}",
                                hint="logs/worker.log pruefen.")
            if self._healthy(ctx) is not None:
                return {"started": True, "pid": proc.pid, "port": port, "log": ctx.rel(layout.log)}
            time.sleep(0.5)

        self._kill_group(proc.pid)
        raise LimbError(ErrorCode.TIMEOUT, "Worker wurde nicht rechtzeitig gesund",
                        hint=f"logs/worker.log pruefen: {self._tail(layout.log)}")

    def _stop(self, params, ctx: LimbContext):
        layout = self._layout(ctx, create=False)
        pid = None
        if layout.pid_file.is_file():
            try:
                pid = int(layout.pid_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                pid = None
        if pid is None:
            return {"stopped": False, "reason": "keine PID-Datei", "port": self._port(ctx)}
        killed = self._kill_group(pid)
        layout.pid_file.unlink(missing_ok=True)
        return {"stopped": killed, "pid": pid, "port": self._port(ctx)}

    def _kill_group(self, pid: int) -> bool:
        """Beendet die *Gruppe* -- uvicorn startet Kinder."""
        for sig, wait_s in ((signal.SIGTERM, 5.0), (signal.SIGKILL, 2.0)):
            try:
                os.killpg(os.getpgid(pid), sig)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            end = time.time() + wait_s
            while time.time() < end:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    return True
                time.sleep(0.1)
        return False

    def _status(self, params, ctx: LimbContext):
        layout = self._layout(ctx, create=False)
        health = self._healthy(ctx)
        if health is None:
            raise LimbError(ErrorCode.IO, "Worker laeuft nicht", hint="trading.start ausfuehren.")
        out: dict[str, Any] = {"running": True, "port": self._port(ctx), "health": health,
                               "marker": self._read_marker(layout)}
        try:
            out["lake"] = self._request(ctx, "GET", "/api/lake/summary", timeout_s=15.0)
        except LimbError as exc:
            out["lake_error"] = exc.message
        return out

    def _lake_summary(self, params, ctx: LimbContext):
        return self._request(ctx, "GET", "/api/lake/summary", timeout_s=self._budget(ctx, 30.0))

    def _lake_compact(self, params, ctx: LimbContext):
        body = {k: v for k, v in params.items() if k in {"symbol", "interval", "day"}}
        return self._request(ctx, "POST", "/api/lake/compact", body=body, timeout_s=self._budget(ctx, 120.0))

    def _backtest_run(self, params, ctx: LimbContext):
        """Nur die dokumentierten Felder -- keine beliebigen Durchreichungen."""
        body = {
            "strategyType": params.get("strategy") or params.get("strategyType") or "sma_cross",
            "assetPair": params.get("pair") or params.get("assetPair") or "BTC/USD",
            "interval": int(params.get("interval") or 60),
            "candleCount": int(params.get("candleCount") or 300),
            "initialBalance": float(params.get("initialBalance") or 10_000.0),
        }
        if isinstance(params.get("params"), dict):
            body["parameters"] = params["params"]
        if params.get("strategyId"):
            body["strategyId"] = str(params["strategyId"])
        return self._request(ctx, "POST", "/api/backtest/run", body=body, timeout_s=self._budget(ctx, 180.0))

    # ------------------------------------------------------------- Helfer
    @staticmethod
    def _tree_size(path: Path) -> int:
        total = 0
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    continue
        return total

    @staticmethod
    def _tail_only(text: str | None, limit: int = 400) -> str:
        return (text or "").strip()[-limit:]

    @staticmethod
    def _tail(path: Path, limit: int = 800) -> str:
        try:
            data = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return data[-limit:].replace("\n", " ")


if __name__ == "__main__":
    sys.exit(TradingLimb().main())
