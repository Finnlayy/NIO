"""Sandbox-Ausfuehrung für Kanban-Worker (Docker und lokaler Subprozess).

Isoliert den Worker-Code, injiziert Geheimnisse als Umgebungsvariablen
und ueberwacht den Heartbeat und die Ausfuehrungszeit.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import logging
import os
import signal
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import KanbanTask, Worker

__all__ = [
    "DockerSandbox",
    "SandboxResult",
    "SandboxRunner",
    "SandboxSpec",
    "SubprocessSandbox",
    "build_sandbox",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SandboxSpec:
    run_id: str
    task: KanbanTask
    worker: Worker
    run_dir: Path
    env: dict[str, str]
    secrets: dict[str, str]
    image: str
    deadline_s: float


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    timed_out: bool
    cancelled: bool
    out_dir: Path
    stderr_tail: str


class SandboxRunner(Protocol):
    async def run(
        self,
        spec: SandboxSpec,
        *,
        on_heartbeat: Callable[[], Awaitable[None]],
    ) -> SandboxResult: ...

    async def cancel(self, run_id: str) -> None: ...


class _ProcessSandbox:
    """Basisklasse für Prozess-basierte Sandboxes mit Heartbeat-Ueberwachung."""

    def __init__(self, config: KanbanConfig) -> None:
        self.config = config
        self._running: dict[str, asyncio.subprocess.Process] = {}
        self._cancelled: set[str] = set()

    async def run(
        self,
        spec: SandboxSpec,
        *,
        on_heartbeat: Callable[[], Awaitable[None]],
    ) -> SandboxResult:
        run_id = spec.run_id
        out_dir = spec.run_dir / "out"
        heartbeat_file = out_dir / "heartbeat"

        # Basis-Env und Worker-Script vorbereiten, falls Subklassen es nicht tun
        # wird aber ueberschrieben von build_argv und get_env in den Subklassen
        argv, env, cwd = self._prepare(spec)

        logger.debug(f"Starte Sandbox {run_id}")

        # Prozess starten
        proc = await asyncio.create_subprocess_exec(
            *argv,
            env=env,
            cwd=cwd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        self._running[run_id] = proc

        stderr_q: collections.deque[bytes] = collections.deque(maxlen=16384)

        async def read_stderr() -> None:
            if not proc.stderr:
                return
            with contextlib.suppress(Exception):
                while True:
                    chunk = await proc.stderr.read(4096)
                    if not chunk:
                        break
                    # Wir merken uns nur die letzten ~16 KiB
                    stderr_q.append(chunk)

        stderr_task = asyncio.create_task(read_stderr())

        last_mtime = 0.0
        start_time = asyncio.get_running_loop().time()
        deadline = start_time + spec.deadline_s

        timed_out = False

        try:
            # Polling-Schleife für Heartbeat und Beendigung
            poll_interval = min(1.0, self.config.heartbeat_s)
            while True:
                # Prozess beendet?
                if proc.returncode is not None:
                    break

                # Deadline ueberschritten?
                now = asyncio.get_running_loop().time()
                if now > deadline:
                    timed_out = True
                    await self.cancel(run_id)
                    break

                # Abgebrochen durch cancel()?
                if run_id in self._cancelled:
                    break

                # Heartbeat pruefen
                try:
                    mtime = heartbeat_file.stat().st_mtime
                    if mtime > last_mtime:
                        last_mtime = mtime
                        await on_heartbeat()
                except FileNotFoundError:
                    pass

                try:
                    await asyncio.wait_for(proc.wait(), timeout=poll_interval)
                    break
                except TimeoutError:
                    continue

        finally:
            await stderr_task
            self._running.pop(run_id, None)

            # Warten, falls der Prozess noch laeuft (nach Cancel)
            if proc.returncode is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(proc.wait(), timeout=self.config.stop_grace_s + 2.0)

        # Stderr zusammensetzen und auf 16 KiB stutzen
        full_stderr = b"".join(stderr_q)
        if len(full_stderr) > 16384:
            full_stderr = b"..." + full_stderr[-16381:]
        stderr_tail = full_stderr.decode("utf-8", errors="replace")

        return SandboxResult(
            exit_code=proc.returncode,
            timed_out=timed_out,
            cancelled=run_id in self._cancelled,
            out_dir=out_dir,
            stderr_tail=stderr_tail,
        )

    def _prepare(self, spec: SandboxSpec) -> tuple[list[str], dict[str, str], str | None]:
        raise NotImplementedError

    async def cancel(self, run_id: str) -> None:
        self._cancelled.add(run_id)
        if proc := self._running.get(run_id):
            if proc.returncode is not None:
                return

            self._stop_proc(proc)

    def _stop_proc(self, proc: asyncio.subprocess.Process) -> None:
        raise NotImplementedError


class SubprocessSandbox(_ProcessSandbox):
    """Sandbox fuer Entwicklung und Tests (keine Isolation, keine Limits)."""

    def _prepare(self, spec: SandboxSpec) -> tuple[list[str], dict[str, str], str | None]:
        # Dev/Test-Pfad ohne Docker. Keine CPU/RAM-Limits.
        run_dir = spec.run_dir
        work_dir = run_dir / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "tmp").mkdir(parents=True, exist_ok=True)

        pkg_dir = Path(__file__).parent.resolve()
        worker_script = pkg_dir / "worker_entry.py"

        argv = [sys.executable, "-I", str(worker_script)]

        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(run_dir / "tmp"),
            "TMPDIR": str(run_dir / "tmp"),
            "NIO_KANBAN_IN": str(run_dir / "in"),
            "NIO_KANBAN_OUT": str(run_dir / "out"),
            "NIO_KANBAN_WORKDIR": str(work_dir),
            "NIO_KANBAN_HEARTBEAT_S": str(self.config.heartbeat_s),
            "NIO_KANBAN_API_URL": self.config.sandbox_api_url,
        }
        env.update(spec.env)
        env.update(spec.secrets)

        return argv, env, str(work_dir)

    def _stop_proc(self, proc: asyncio.subprocess.Process) -> None:
        # Prozessgruppe gracefully beenden
        try:
            pid = proc.pid
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)

            # Ein Grace-Timeout-Task killt hart nach stop_grace_s
            loop = asyncio.get_running_loop()

            def _kill() -> None:
                if proc.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(pgid, signal.SIGKILL)

            loop.call_later(self.config.stop_grace_s, _kill)
        except ProcessLookupError:
            pass


class DockerSandbox(_ProcessSandbox):
    """Sandbox ueber Docker mit CPU/RAM/PIDs-Limits und Isolation."""

    def __init__(self, config: KanbanConfig) -> None:
        super().__init__(config)
        self._container_names: dict[str, str] = {}

    @staticmethod
    def build_argv(spec: SandboxSpec, config: KanbanConfig) -> list[str]:
        run_dir = spec.run_dir
        uid = spec.worker.uid
        run_id = spec.run_id

        pkg_dir = Path(__file__).parent.resolve()
        worker_script = pkg_dir / "worker_entry.py"
        mcp_shim = pkg_dir / "mcp_shim.py"

        argv = [
            config.docker_bin,
            "run",
            "--rm",
            "--name",
            f"nio-w-{uid}-{run_id}",
            "--cpus",
            config.cpus,
            "--memory",
            config.memory,
            "--memory-swap",
            config.memory,
            "--pids-limit",
            str(config.pids_limit),
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=64m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "1000:1000",
            "--network",
            config.network,
        ]

        if config.network != "none":
            argv.extend(["--add-host", "host.docker.internal:host-gateway"])

        argv.extend(
            [
                "-v",
                f"{run_dir}/in:/nio/in:ro",
                "-v",
                f"{run_dir}/out:/nio/out:rw",
                "-v",
                f"{run_dir}/work:/workspace:rw",
                "-v",
                f"{worker_script}:/nio/bin/worker_entry.py:ro",
                "-v",
                f"{mcp_shim}:/nio/bin/mcp_shim.py:ro",
                "-e",
                "NIO_KANBAN_IN=/nio/in",
                "-e",
                "NIO_KANBAN_OUT=/nio/out",
                "-e",
                "NIO_KANBAN_WORKDIR=/workspace",
                "-e",
                f"NIO_KANBAN_HEARTBEAT_S={config.heartbeat_s}",
                "-e",
                f"NIO_KANBAN_API_URL={config.sandbox_api_url}",
            ]
        )

        for k in spec.env:
            argv.extend(["-e", f"{k}={spec.env[k]}"])

        # Secrets nur mit Namen (Wert kommt aus env des Subprozesses)
        for k in spec.secrets:
            argv.extend(["-e", k])

        argv.extend(
            [
                spec.image,
                "python3",
                "/nio/bin/worker_entry.py",
            ]
        )

        return argv

    def _prepare(self, spec: SandboxSpec) -> tuple[list[str], dict[str, str], str | None]:
        # out/ und work/ muessen fuer UID 1000 schreibbar sein
        out_dir = spec.run_dir / "out"
        work_dir = spec.run_dir / "work"
        out_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir, 0o777)
        os.chmod(work_dir, 0o777)

        argv = self.build_argv(spec, self.config)
        self._container_names[spec.run_id] = f"nio-w-{spec.worker.uid}-{spec.run_id}"

        # minimale Env + Secrets
        env = {}
        for k in ["PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG"]:
            if k in os.environ:
                env[k] = os.environ[k]

        env.update(spec.secrets)

        return argv, env, None

    def _stop_proc(self, proc: asyncio.subprocess.Process) -> None:
        # Hier nicht benutzt, wir ueberschreiben cancel stattdessen
        pass

    async def cancel(self, run_id: str) -> None:
        self._cancelled.add(run_id)
        if proc := self._running.get(run_id):
            if proc.returncode is not None:
                return

            container_name = self._container_names.get(run_id)
            if container_name:
                stop_proc = await asyncio.create_subprocess_exec(
                    self.config.docker_bin,
                    "stop",
                    "-t",
                    str(int(self.config.stop_grace_s)),
                    container_name,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await stop_proc.wait()

            # Subprozess falls noetig noch aufraeumen
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def build_sandbox(config: KanbanConfig) -> SandboxRunner:
    if config.sandbox == "docker":
        return DockerSandbox(config)
    return SubprocessSandbox(config)
