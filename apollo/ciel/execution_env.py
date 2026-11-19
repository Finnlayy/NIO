"""Abbruchsignal und Ausführungsumgebung für Tool-Aufrufe (NIO Phase 3).

* :class:`CancellationToken` — asyncio-basiertes Abbruchsignal mit Ursache, Callbacks
  und verknüpften Kind-Tokens (``child()``), die mit dem Elternteil mitfeuern.
* :class:`ExecutionEnvironment` — Protokoll für die Ausführung eines Tool-Calls unter
  Token und Zeitlimit.
* :class:`LocalExecutionEnv` — umhüllt den bestehenden :class:`ToolExecutor` im Prozess.
* :class:`SubprocessExecutionEnv` — führt einen Call als eigene Prozessgruppe aus;
  Abbruch oder Timeout beendet Eltern- und Enkelprozesse (SIGTERM, Grace, SIGKILL).

Ciel bleibt entkoppelt: kein Import aus ``orchestrator``. Container-Isolation läuft
über ``orchestrator.kanban.sandbox.DockerSandbox`` außerhalb dieses Moduls.

Alle Methoden von :class:`CancellationToken` laufen auf dem Event-Loop-Thread.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import time
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import Any, Protocol

from .errors import CielError, ToolNotExecutable, ToolNotFound
from .models import ToolCall, ToolResult
from .ncm_gate import ToolExecutor

logger = logging.getLogger(__name__)

#: Standard-Grace zwischen SIGTERM und SIGKILL (Sekunden).
DEFAULT_GRACE_S = 0.25

__all__ = [
    "DEFAULT_GRACE_S",
    "AbortReason",
    "ArgvFactory",
    "CancellationToken",
    "ExecutionAbortedError",
    "ExecutionEnvironment",
    "LocalExecutionEnv",
    "SubprocessExecutionEnv",
]


class AbortReason(StrEnum):
    """Ursache eines Abbruchs."""

    USER_ABORT = "USER_ABORT"
    PARENT_ABORT = "PARENT_ABORT"
    TIMEOUT = "TIMEOUT"
    SHUTDOWN = "SHUTDOWN"


class ExecutionAbortedError(CielError):
    """Die Ausführung wurde über ein :class:`CancellationToken` abgebrochen."""

    def __init__(self, reason: AbortReason | str, detail: str = "") -> None:
        self.reason = AbortReason(reason)
        self.detail = detail
        super().__init__(f"ABORTED:{self.reason.value}" + (f" ({detail})" if detail else ""))


AbortCallback = Callable[[AbortReason, str], None]


class CancellationToken:
    """Abbruchsignal mit einmaliger Ursache.

    Das erste ``cancel()`` gewinnt; spätere Aufrufe ändern weder Ursache noch Detail.
    Kind-Tokens (``child()``) feuern mit dem Elternteil, nicht umgekehrt.
    """

    def __init__(self, *, parent: CancellationToken | None = None) -> None:
        self._event = asyncio.Event()
        self._reason: AbortReason | None = None
        self._detail = ""
        self._callbacks: list[AbortCallback] = []
        self._children: list[CancellationToken] = []
        if parent is not None:
            parent._children.append(self)
            if parent.cancelled:
                self.cancel(AbortReason.PARENT_ABORT, parent.detail)

    @property
    def cancelled(self) -> bool:
        return self._reason is not None

    @property
    def reason(self) -> AbortReason | None:
        return self._reason

    @property
    def detail(self) -> str:
        return self._detail

    def cancel(self, reason: AbortReason | str = AbortReason.USER_ABORT, detail: str = "") -> None:
        """Löst den Abbruch aus, weckt Wartende, ruft Callbacks und Kinder auf. Idempotent."""
        if self._reason is not None:
            return
        self._reason = AbortReason(reason)
        self._detail = detail
        self._event.set()
        for callback in list(self._callbacks):
            try:
                callback(self._reason, detail)
            except Exception:  # ein kaputter Callback darf den Abbruch nicht verhindern
                logger.exception("Abbruch-Callback fehlgeschlagen")
        for child in list(self._children):
            child.cancel(AbortReason.PARENT_ABORT, detail)

    def on_cancel(self, callback: AbortCallback) -> None:
        """Registriert einen Callback ``(reason, detail)``; ist bereits abgebrochen, läuft er sofort."""
        if self._reason is not None:
            callback(self._reason, self._detail)
            return
        self._callbacks.append(callback)

    async def wait_cancelled(self) -> None:
        """Wartet, bis ``cancel()`` aufgerufen wurde."""
        await self._event.wait()

    def raise_if_cancelled(self) -> None:
        """Wirft :class:`ExecutionAbortedError`, wenn abgebrochen wurde."""
        if self._reason is not None:
            raise ExecutionAbortedError(self._reason, self._detail)

    def child(self) -> CancellationToken:
        """Kind-Token, das mit diesem Token mitfeuert, aber dessen Abbruch nicht zurückmeldet."""
        return CancellationToken(parent=self)


class ExecutionEnvironment(Protocol):
    """Führt einen Tool-Call unter Abbruchsignal und Zeitlimit aus."""

    async def execute(self, call: ToolCall, *, token: CancellationToken, timeout_s: float) -> ToolResult: ...


def _silence(task: asyncio.Future[Any]) -> None:
    """Verwirft das Ergebnis eines abgebrochenen Tasks, ohne auf ihn zu warten."""
    task.add_done_callback(lambda t: t.cancelled() or t.exception())


def _aborted_result(call: ToolCall, token: CancellationToken, started: float) -> ToolResult:
    reason = token.reason.value if token.reason is not None else AbortReason.USER_ABORT.value
    return ToolResult(
        call_id=call.id,
        name=call.name,
        ok=False,
        error=f"ABORTED:{reason}",
        elapsed_s=time.monotonic() - started,
    )


def _timeout_result(call: ToolCall, timeout_s: float, started: float) -> ToolResult:
    error = f"Tool {call.name!r} überschritt das Timeout von {timeout_s:g}s."
    return ToolResult(call_id=call.id, name=call.name, ok=False, error=error, timed_out=True, elapsed_s=time.monotonic() - started)


class LocalExecutionEnv:
    """Führt Calls über den bestehenden :class:`ToolExecutor` im Prozess aus.

    Der Handler läuft als Task und wird gegen ``token.wait_cancelled()`` geraced.
    Bei Abbruch oder Timeout wird der Task abgebrochen und nicht mehr abgewartet.
    """

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor

    async def execute(self, call: ToolCall, *, token: CancellationToken, timeout_s: float) -> ToolResult:
        started = time.monotonic()
        if token.cancelled:
            return _aborted_result(call, token, started)
        task = asyncio.ensure_future(self._executor.execute(call.name, dict(call.arguments)))
        cancel_wait = asyncio.ensure_future(token.wait_cancelled())
        try:
            done, _pending = await asyncio.wait({task, cancel_wait}, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            task.cancel()
            _silence(task)
            raise
        finally:
            cancel_wait.cancel()
        if task not in done:
            task.cancel()
            _silence(task)
            if token.cancelled:
                return _aborted_result(call, token, started)
            return _timeout_result(call, timeout_s, started)
        try:
            value = task.result()
        except (ToolNotFound, ToolNotExecutable) as exc:
            return ToolResult(call_id=call.id, name=call.name, ok=False, error=str(exc), elapsed_s=time.monotonic() - started)
        except Exception as exc:
            error = f"Tool {call.name!r} scheiterte: {exc}"
            return ToolResult(call_id=call.id, name=call.name, ok=False, error=error, elapsed_s=time.monotonic() - started)
        return ToolResult(call_id=call.id, name=call.name, ok=True, result=value, elapsed_s=time.monotonic() - started)


#: Baut aus einem Tool-Call den Kommando-Vektor des Subprozesses.
ArgvFactory = Callable[[ToolCall], Sequence[str]]


class SubprocessExecutionEnv:
    """Führt Calls als Subprozess in eigener Prozessgruppe aus.

    Der Call wird als JSON ``{"name", "arguments"}`` auf stdin übergeben; stdout wird als
    JSON geparst (sonst als Text) und ist das Ergebnis. Abbruch oder Timeout senden
    SIGTERM an die gesamte Gruppe, nach ``grace_s`` SIGKILL. Logik wie
    ``SubprocessSandbox._stop_proc`` in ``orchestrator/kanban/sandbox.py``.
    Die Umgebung ist minimal (nur ``PATH``), damit keine Geheimnisse durchsickern.
    """

    def __init__(
        self,
        argv_for: ArgvFactory,
        *,
        grace_s: float = DEFAULT_GRACE_S,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._argv_for = argv_for
        self._grace_s = max(0.0, grace_s)
        self._cwd = cwd
        self._env = dict(env) if env is not None else {"PATH": os.environ.get("PATH", "")}

    async def execute(self, call: ToolCall, *, token: CancellationToken, timeout_s: float) -> ToolResult:
        started = time.monotonic()
        if token.cancelled:
            return _aborted_result(call, token, started)
        payload = json.dumps({"name": call.name, "arguments": dict(call.arguments)}, ensure_ascii=False).encode("utf-8")
        proc = await asyncio.create_subprocess_exec(
            *self._argv_for(call),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
            cwd=self._cwd,
            start_new_session=True,
        )
        comm = asyncio.ensure_future(proc.communicate(payload))
        cancel_wait = asyncio.ensure_future(token.wait_cancelled())
        try:
            done, _pending = await asyncio.wait({comm, cancel_wait}, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            comm.cancel()
            _silence(comm)
            await self._terminate(proc)
            raise
        finally:
            cancel_wait.cancel()
        if comm not in done:
            comm.cancel()
            _silence(comm)
            await self._terminate(proc)
            if token.cancelled:
                return _aborted_result(call, token, started)
            return _timeout_result(call, timeout_s, started)
        stdout_raw, stderr_raw = comm.result()
        elapsed = time.monotonic() - started
        if proc.returncode != 0:
            tail = stderr_raw.decode("utf-8", errors="replace")[-2000:]
            error = f"Tool {call.name!r} beendete mit Code {proc.returncode}: {tail}"
            return ToolResult(call_id=call.id, name=call.name, ok=False, error=error, elapsed_s=elapsed)
        text = stdout_raw.decode("utf-8", errors="replace")
        value: Any
        try:
            value = json.loads(text) if text.strip() else None
        except ValueError:
            value = text
        return ToolResult(call_id=call.id, name=call.name, ok=True, result=value, elapsed_s=elapsed)

    async def _terminate(self, proc: asyncio.subprocess.Process) -> None:
        """Beendet die Prozessgruppe: SIGTERM, nach der Grace-Zeit SIGKILL, danach Reaping des Leaders."""
        pgid = proc.pid  # start_new_session=True: der Leader ist Gruppenleiter
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._grace_s
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGTERM)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(proc.wait(), timeout=self._grace_s)
        # Grace-Zeit auch für Enkelprozesse der Gruppe, auch wenn der Leader schon beendet ist.
        remaining = deadline - loop.time()
        if remaining > 0:
            await asyncio.sleep(remaining)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)
        if proc.returncode is None:
            await proc.wait()
