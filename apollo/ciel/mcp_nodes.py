"""MCP-Node-Anbindung: externe (FastMCP-kompatible) Server als Ciel-Skills.

Liest eine Claude-style ``mcp_config.json`` (``{"mcpServers": {...}}``),
verbindet jeden Node und registriert dessen Tools in der
:class:`ColdStorageRegistry` (Herkunft ``mcp:<node>``) — damit fliessen sie
automatisch durch NCM-Gate, JIT-Injection und Graph-Telemetry.

Transporte (beide Stdlib-only, beide mit strikten Timeouts):

* **stdio** (Standard, z. B. ``npx -y mcp-remote https://...`` als Subprozess):
  JSON-RPC 2.0 mit ``Content-Length``-Framing.
* **sse** (Remote direkt, ohne Node-Abhaengigkeit): Legacy-MCP-SSE —
  GET-Event-Stream plus POST der JSON-RPC-Nachrichten an die ``endpoint``-URL.

Fail-closed: Ein toter Node erzeugt einen Eintrag in ``errors``, aber stoppt
weder andere Nodes noch die Schicht (``load_and_register_mcp_nodes``).
Secrets (API-Keys) kommen nie in die Config-Datei, sondern als
``${VAR}``-Referenzen aus der Umgebung (``expand_env_vars``).
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apollo import __version__ as APOLLO_VERSION

from .bus import emit
from .errors import CielConfigError, MCPToolError, MCPTransportError
from .models import BaseModel, ConfigDict, Field
from .registry import ColdStorageRegistry

#: MCP-Protokollversion, die dieser Client spricht.
MCP_PROTOCOL_VERSION = "2024-11-05"

#: Client-Name im initialize-Handshake.
MCP_CLIENT_NAME = "nio-ciel"

#: Sicherheitsdeckel fuer tools/list-Pagination.
_MAX_LIST_PAGES = 100

_ENV_RE = re.compile(r"\$(\w+|\{[^}]*\})")


def expand_env_vars(value: str) -> str:
    """Expandiert ``${VAR}``/``$VAR`` aus der Umgebung (fehlend -> "")."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key.startswith("{") and key.endswith("}"):
            key = key[1:-1]
        return os.environ.get(key, "")

    return _ENV_RE.sub(_replace, value)


class MCPNodeConfig(BaseModel):
    """Konfiguration eines einzelnen MCP-Nodes (ein ``mcpServers``-Eintrag)."""

    model_config = ConfigDict(extra="ignore")

    name: str
    transport: str = "stdio"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_sec: float = 30.0
    cluster: str = ""
    disabled: bool = False


class MCPTool(BaseModel):
    """Ein via ``tools/list`` gemeldetes MCP-Tool."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    node: str = ""


def load_mcp_config(path: str | Path) -> dict[str, MCPNodeConfig]:
    """Laedt ``mcp_config.json`` (``{"mcpServers": {name: {...}}}``).

    Inferiert ``transport`` (``url`` ohne ``command`` -> ``sse``), sonst
    ``stdio``. Wirft :class:`CielConfigError` bei Strukturfehlern — fail-fast,
    damit Tippfehler nicht stillschweigend Nodes verlieren.
    """
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CielConfigError(f"MCP-Konfiguration fehlt: {config_path}") from exc
    except (OSError, ValueError) as exc:
        raise CielConfigError(f"MCP-Konfiguration {config_path} ist unlesbar: {exc}") from exc
    if not isinstance(payload, dict):
        raise CielConfigError(f"MCP-Konfiguration {config_path}: Root muss ein Objekt sein.")
    servers = payload.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise CielConfigError(f"MCP-Konfiguration {config_path}: 'mcpServers' muss ein Objekt sein.")
    configs: dict[str, MCPNodeConfig] = {}
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            raise CielConfigError(f"MCP-Node {name!r}: Eintrag muss ein Objekt sein.")
        transport = str(entry.get("transport") or ("sse" if entry.get("url") and not entry.get("command") else "stdio"))
        if transport not in ("stdio", "sse"):
            raise CielConfigError(f"MCP-Node {name!r}: unbekannter Transport {transport!r} (stdio|sse erwartet).")
        try:
            timeout = float(entry.get("timeout_sec", 30.0))
        except (TypeError, ValueError) as exc:
            raise CielConfigError(f"MCP-Node {name!r}: 'timeout_sec' ist keine Zahl.") from exc
        if timeout <= 0:
            raise CielConfigError(f"MCP-Node {name!r}: 'timeout_sec' muss > 0 sein.")
        config = MCPNodeConfig(
            name=str(name),
            transport=transport,
            command=str(entry.get("command") or ""),
            args=[str(a) for a in (entry.get("args") or [])],
            env={str(k): str(v) for k, v in dict(entry.get("env") or {}).items()},
            url=str(entry.get("url") or ""),
            headers={str(k): str(v) for k, v in dict(entry.get("headers") or {}).items()},
            timeout_sec=timeout,
            cluster=str(entry.get("cluster") or ""),
            disabled=bool(entry.get("disabled", False)),
        )
        if transport == "stdio" and not config.command:
            raise CielConfigError(f"MCP-Node {name!r}: stdio-Transport braucht 'command'.")
        if transport == "sse" and not config.url:
            raise CielConfigError(f"MCP-Node {name!r}: sse-Transport braucht 'url'.")
        configs[str(name)] = config
    return configs


class _TransportEOF(Exception):
    """Intern: Gegenseite hat den Stream geschlossen."""


class StdioMCPTransport:
    """JSON-RPC-2.0-Transport ueber Subprozess-stdio (``Content-Length``-Framing)."""

    def __init__(
        self,
        node: str,
        command: str,
        args: Sequence[str] = (),
        env: Mapping[str, str] | None = None,
        *,
        timeout_sec: float = 30.0,
    ) -> None:
        self._node = node
        self._command = command
        self._args = list(args)
        self._env = dict(env or {})
        self._timeout = timeout_sec
        self._proc: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._pending: dict[int | str, asyncio.Future[Any]] = {}
        self._ids = itertools.count(1)
        self._write_lock = asyncio.Lock()
        self._stderr_tail: list[str] = []

    @property
    def node(self) -> str:
        return self._node

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    @property
    def recent_stderr(self) -> tuple[str, ...]:
        return tuple(self._stderr_tail)

    async def start(self) -> None:
        """Startet den Subprozess und die Reader-Tasks (idempotent)."""
        if self.running:
            return
        await self.stop()
        env = dict(os.environ)
        for key, value in self._env.items():
            env[str(key)] = expand_env_vars(str(value))
        try:
            self._proc = await asyncio.create_subprocess_exec(
                self._command,
                *self._args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            raise MCPTransportError(self._node, f"Start von {self._command!r} scheiterte: {exc}") from exc
        loop = asyncio.get_running_loop()
        self._reader_task = loop.create_task(self._read_loop(), name=f"mcp-stdio-{self._node}")
        self._stderr_task = loop.create_task(self._drain_stderr(), name=f"mcp-stderr-{self._node}")

    async def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        """Sendet einen JSON-RPC-Request und wartet (mit Timeout) auf die Antwort."""
        if not self.running or self._proc is None or self._proc.stdin is None:
            raise MCPTransportError(self._node, "Transport laeuft nicht (start() vergessen?).")
        rpc_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[rpc_id] = future
        await self._send({"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": dict(params or {})})
        try:
            message = await asyncio.wait_for(future, timeout=self._timeout)
        except TimeoutError:
            self._pending.pop(rpc_id, None)
            raise MCPTransportError(self._node, f"JSON-RPC {method!r}: Timeout nach {self._timeout:g}s.") from None
        error = message.get("error")
        if error is not None:
            raise MCPTransportError(self._node, f"JSON-RPC {method!r}: {error}.")
        return message.get("result")

    async def notify(self, method: str, params: Mapping[str, Any] | None = None) -> None:
        """Sendet eine JSON-RPC-Notification (keine Antwort erwartet)."""
        if not self.running:
            raise MCPTransportError(self._node, "Transport laeuft nicht (start() vergessen?).")
        await self._send({"jsonrpc": "2.0", "method": method, "params": dict(params or {})})

    async def stop(self) -> None:
        """Beendet Reader-Tasks und Subprozess (Terminate, notfalls Kill)."""
        for task_attr in ("_reader_task", "_stderr_task"):
            task = getattr(self, task_attr)
            setattr(self, task_attr, None)
            if task is not None and not task.done():
                task.cancel()
        proc, self._proc = self._proc, None
        for rpc_id, future in list(self._pending.items()):
            self._pending.pop(rpc_id, None)
            if not future.done():
                future.set_exception(MCPTransportError(self._node, "Transport gestoppt."))
        if proc is not None:
            if proc.returncode is None:
                with _suppress_all():
                    proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except TimeoutError:
                    with _suppress_all():
                        proc.kill()
                    with _suppress_all():
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    with _suppress_all():
                        stream.close()

    async def _send(self, message: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        frame = json.dumps(message, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
        async with self._write_lock:
            try:
                self._proc.stdin.write(header + frame)
                await self._proc.stdin.drain()
            except (BrokenPipeError, ConnectionError, asyncio.IncompleteReadError) as exc:
                raise MCPTransportError(self._node, f"Senden scheiterte (Prozess tot?): {exc}") from exc

    async def _read_loop(self) -> None:
        try:
            while True:
                try:
                    message = await self._read_message()
                except ValueError:
                    continue  # kaputte Zeile/JSON: robust weiterlesen
                self._dispatch(message)
        except (asyncio.CancelledError, _TransportEOF):
            pass
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            for rpc_id, future in list(self._pending.items()):
                self._pending.pop(rpc_id, None)
                if not future.done():
                    future.set_exception(MCPTransportError(self._node, "stdio geschlossen (EOF)."))

    async def _read_message(self) -> dict[str, Any]:
        assert self._proc is not None and self._proc.stdout is not None
        stdout = self._proc.stdout
        length: int | None = None
        while True:
            line = await stdout.readline()
            if line in (b"", None):
                raise _TransportEOF()
            text = line.decode("utf-8", "replace").strip()
            if not text:
                break
            if ":" in text:
                key, value = text.split(":", 1)
                if key.strip().lower() == "content-length":
                    length = int(value.strip())
        if length is None or length < 0 or length > 100_000_000:
            raise ValueError(f"Ungueltige Content-Length: {length!r}")
        body = await stdout.readexactly(length)
        parsed = json.loads(body.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("JSON-RPC-Nachricht ist kein Objekt.")
        return parsed

    def _dispatch(self, message: dict[str, Any]) -> None:
        if "id" in message and ("result" in message or "error" in message):
            future = self._pending.pop(message["id"], None)
            if future is not None and not future.done():
                future.set_result(message)
        elif "id" in message and "method" in message:
            # Server-zu-Client-Request: Wir bieten nichts an -> Method-not-found.
            async def _reply() -> None:
                with _suppress_all():
                    await self._send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Method not found"}})

            with suppress(RuntimeError):
                asyncio.get_running_loop().create_task(_reply())
        # Server-Notifications werden ignoriert (reiner Client).

    async def _drain_stderr(self) -> None:
        try:
            assert self._proc is not None and self._proc.stderr is not None
            while True:
                line = await self._proc.stderr.readline()
                if not line:
                    return
                self._stderr_tail.append(line.decode("utf-8", "replace").rstrip()[-500:])
                del self._stderr_tail[:-20]
        except (asyncio.CancelledError, ValueError, OSError, AttributeError, AssertionError):
            return


class _suppress_all:
    """Kontextmanager: schluckt alles (Shutdown-Pfade duerfen nie werfen)."""

    def __enter__(self) -> _suppress_all:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return True


class SSEMCPTransport:
    """Legacy-MCP-SSE-Transport: GET-Event-Stream plus POST der Requests.

    Spricht Remote-Nodes (z. B. ``https://data.stalkchain.com/mcp``) direkt an —
    ohne ``npx``/``mcp-remote``. Der GET-Stream laeuft in einem Daemon-Thread
    (``urllib``), die Event-Verteilung im Loop; POSTs laufen via ``to_thread``.
    """

    def __init__(self, node: str, url: str, headers: Mapping[str, str] | None = None, *, timeout_sec: float = 30.0) -> None:
        self._node = node
        self._url = url
        self._headers = dict(headers or {})
        self._timeout = timeout_sec
        self._pending: dict[int | str, asyncio.Future[Any]] = {}
        self._ids = itertools.count(1)
        self._lines: asyncio.Queue[str | None] = asyncio.Queue()
        self._parser_task: asyncio.Task[None] | None = None
        self._reader_thread: threading.Thread | None = None
        self._response: Any = None
        self._response_lock = threading.Lock()
        self._stopping = threading.Event()
        self._endpoint: str | None = None
        self._endpoint_ready: asyncio.Event | None = None
        self._reader_error = ""

    @property
    def node(self) -> str:
        return self._node

    @property
    def running(self) -> bool:
        return self._parser_task is not None and not self._parser_task.done() and self._endpoint is not None

    async def start(self) -> None:
        """Oeffnet den SSE-Stream und wartet (mit Timeout) auf das ``endpoint``-Event."""
        await self.stop()
        self._stopping.clear()
        self._endpoint = None
        self._reader_error = ""
        self._endpoint_ready = asyncio.Event()
        loop = asyncio.get_running_loop()
        self._parser_task = loop.create_task(self._parse_loop(), name=f"mcp-sse-{self._node}")
        self._reader_thread = threading.Thread(target=self._stream_reader, args=(loop,), name=f"mcp-sse-{self._node}", daemon=True)
        self._reader_thread.start()
        assert self._endpoint_ready is not None
        try:
            await asyncio.wait_for(self._endpoint_ready.wait(), timeout=self._timeout)
        except TimeoutError:
            await self.stop()
            detail = f" ({self._reader_error})" if self._reader_error else ""
            raise MCPTransportError(self._node, f"SSE-Stream {self._url!r}: kein endpoint-Event nach {self._timeout:g}s{detail}.") from None
        if self._endpoint is None:
            await self.stop()
            raise MCPTransportError(self._node, f"SSE-Stream {self._url!r} schloss vor dem endpoint-Event.")

    async def request(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        """POSTet einen JSON-RPC-Request; Antwort kommt ueber den SSE-Stream."""
        endpoint = self._endpoint
        if endpoint is None or self._parser_task is None:
            raise MCPTransportError(self._node, "Transport laeuft nicht (start() vergessen?).")
        rpc_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[rpc_id] = future
        await self._post(endpoint, {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": dict(params or {})}, rpc_id)
        try:
            message = await asyncio.wait_for(future, timeout=self._timeout)
        except TimeoutError:
            self._pending.pop(rpc_id, None)
            raise MCPTransportError(self._node, f"JSON-RPC {method!r}: Timeout nach {self._timeout:g}s.") from None
        error = message.get("error")
        if error is not None:
            raise MCPTransportError(self._node, f"JSON-RPC {method!r}: {error}.")
        return message.get("result")

    async def notify(self, method: str, params: Mapping[str, Any] | None = None) -> None:
        """POSTet eine JSON-RPC-Notification (keine Antwort erwartet)."""
        endpoint = self._endpoint
        if endpoint is None:
            raise MCPTransportError(self._node, "Transport laeuft nicht (start() vergessen?).")
        await self._post(endpoint, {"jsonrpc": "2.0", "method": method, "params": dict(params or {})}, None)

    async def stop(self) -> None:
        """Schliesst Stream, Thread und Parser-Task; offene Requests scheitern sauber."""
        self._stopping.set()
        with self._response_lock:
            response, self._response = self._response, None
        if response is not None:
            with _suppress_all():
                response.close()
        parser, self._parser_task = self._parser_task, None
        if parser is not None and not parser.done():
            parser.cancel()
            with _suppress_all():
                await parser
        thread, self._reader_thread = self._reader_thread, None
        if thread is not None and thread.is_alive():
            with _suppress_all():
                await asyncio.to_thread(thread.join, 2.0)
        for rpc_id, future in list(self._pending.items()):
            self._pending.pop(rpc_id, None)
            if not future.done():
                future.set_exception(MCPTransportError(self._node, "Transport gestoppt."))
        self._endpoint = None

    def _stream_reader(self, loop: asyncio.AbstractEventLoop) -> None:
        """Daemon-Thread: liest den SSE-Stream und reicht Zeilen an den Loop."""

        def _push(line: str | None) -> None:
            with _suppress_all():
                loop.call_soon_threadsafe(self._lines.put_nowait, line)

        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
        for key, value in self._headers.items():
            headers[str(key)] = expand_env_vars(str(value))
        try:
            request = urllib.request.Request(self._url, headers=headers, method="GET")
            response = urllib.request.urlopen(request, timeout=self._timeout)
        except Exception as exc:
            self._reader_error = f"{type(exc).__name__}: {exc}"
            _push(None)
            return
        with self._response_lock:
            if self._stopping.is_set():
                with _suppress_all():
                    response.close()
                _push(None)
                return
            self._response = response
        try:
            for raw in response:
                if self._stopping.is_set():
                    break
                _push(raw.decode("utf-8", "replace"))
        except Exception as exc:
            if not self._stopping.is_set():
                self._reader_error = f"{type(exc).__name__}: {exc}"
        finally:
            with _suppress_all():
                response.close()
            with self._response_lock:
                if self._response is response:
                    self._response = None
            _push(None)

    async def _parse_loop(self) -> None:
        event_name = ""
        data_lines: list[str] = []
        try:
            while True:
                line = await self._lines.get()
                if line is None:
                    return
                text = line.strip("\r\n")
                if text == "":
                    self._dispatch_event(event_name, "\n".join(data_lines))
                    event_name = ""
                    data_lines = []
                elif text.startswith(":"):
                    continue  # SSE-Kommentar/Keepalive
                elif text.startswith("event:"):
                    event_name = text[6:].strip()
                elif text.startswith("data:"):
                    data_lines.append(text[5:].strip())
        except asyncio.CancelledError:
            pass

    def _dispatch_event(self, event_name: str, data: str) -> None:
        if event_name == "endpoint":
            self._endpoint = urllib.parse.urljoin(self._url, data.strip())
            if self._endpoint_ready is not None:
                with _suppress_all():
                    self._endpoint_ready.set()
            return
        if event_name not in ("message", ""):
            return  # unbekannte Events ignorieren
        if not data.strip():
            return
        try:
            message = json.loads(data)
        except ValueError:
            return
        if not isinstance(message, dict):
            return
        if "id" in message and ("result" in message or "error" in message):
            future = self._pending.pop(message["id"], None)
            if future is not None and not future.done():
                future.set_result(message)
        # Server-Requests/Notifications: reiner Client, ignorieren.

    async def _post(self, endpoint: str, payload: dict[str, Any], rpc_id: int | str | None) -> None:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        for key, value in self._headers.items():
            headers[str(key)] = expand_env_vars(str(value))

        def _send() -> bytes:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                detail = ""
                with _suppress_all():
                    detail = exc.read().decode("utf-8", "replace")[:500]
                raise MCPTransportError(self._node, f"POST {endpoint!r}: HTTP {exc.code} {detail}".rstrip()) from exc
            except (urllib.error.URLError, OSError) as exc:
                raise MCPTransportError(self._node, f"POST {endpoint!r}: {exc}") from exc

        try:
            raw = await asyncio.to_thread(_send)
        except MCPTransportError:
            if rpc_id is not None:
                future = self._pending.pop(rpc_id, None)
                if future is not None and not future.done():
                    future.set_exception(MCPTransportError(self._node, f"POST an {endpoint!r} scheiterte."))
            raise
        # Manche Server antworten direkt im POST-Body statt ueber SSE.
        if rpc_id is not None and raw.strip():
            with _suppress_all():
                direct = json.loads(raw.decode("utf-8"))
                if isinstance(direct, dict) and direct.get("id") == rpc_id:
                    future = self._pending.pop(rpc_id, None)
                    if future is not None and not future.done():
                        future.set_result(direct)


class MCPNodeClient:
    """Client eines MCP-Nodes: initialize -> tools/list -> tools/call."""

    def __init__(self, config: MCPNodeConfig) -> None:
        self._config = config
        if config.transport == "stdio":
            self._transport: StdioMCPTransport | SSEMCPTransport = StdioMCPTransport(
                config.name, config.command, config.args, config.env, timeout_sec=config.timeout_sec
            )
        elif config.transport == "sse":
            self._transport = SSEMCPTransport(config.name, config.url, config.headers, timeout_sec=config.timeout_sec)
        else:
            raise CielConfigError(f"MCP-Node {config.name!r}: unbekannter Transport {config.transport!r}.")
        self.server_info: dict[str, Any] = {}
        self._started = False

    @property
    def config(self) -> MCPNodeConfig:
        return self._config

    @property
    def started(self) -> bool:
        return self._started

    async def __aenter__(self) -> MCPNodeClient:
        await self.start()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.stop()

    async def start(self) -> dict[str, Any]:
        """Handshake (``initialize`` + ``notifications/initialized``); gibt Server-Info zurueck."""
        if self._started:
            return self.server_info
        await self._transport.start()
        try:
            result = await self._transport.request(
                "initialize",
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": MCP_CLIENT_NAME, "version": APOLLO_VERSION},
                },
            )
        except Exception:
            await self._transport.stop()
            raise
        self.server_info = dict((result or {}).get("serverInfo", {}) if isinstance(result, dict) else {})
        await self._transport.notify("notifications/initialized", {})
        self._started = True
        return self.server_info

    async def list_tools(self) -> list[MCPTool]:
        """Listet alle Tools des Nodes (mit Cursor-Pagination)."""
        if not self._started:
            raise MCPTransportError(self._config.name, "Client nicht gestartet (start() vergessen?).")
        tools: list[MCPTool] = []
        cursor: str | None = None
        for _ in range(_MAX_LIST_PAGES):
            params: dict[str, Any] = {} if cursor is None else {"cursor": cursor}
            try:
                result = await self._transport.request("tools/list", params)
            except MCPTransportError as exc:
                raise MCPTransportError(self._config.name, f"tools/list scheiterte: {exc}") from exc
            entries = (result or {}).get("tools", []) if isinstance(result, dict) else []
            for entry in entries:
                if not isinstance(entry, dict) or "name" not in entry:
                    continue
                tools.append(
                    MCPTool(
                        name=str(entry["name"]),
                        description=str(entry.get("description") or ""),
                        input_schema=dict(entry.get("inputSchema") or {}),
                        node=self._config.name,
                    )
                )
            cursor = (result or {}).get("nextCursor") if isinstance(result, dict) else None
            if not cursor:
                break
        return tools

    async def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        """Ruft ein Tool auf; ``isError``/RPC-``error`` -> :class:`MCPToolError`."""
        if not self._started:
            raise MCPTransportError(self._config.name, "Client nicht gestartet (start() vergessen?).")
        try:
            result = await self._transport.request("tools/call", {"name": name, "arguments": dict(arguments or {})})
        except MCPTransportError as exc:
            raise MCPToolError(self._config.name, name, str(exc)) from exc
        if isinstance(result, dict) and result.get("isError"):
            raise MCPToolError(self._config.name, name, _content_text(result.get("content")))
        return result

    async def stop(self) -> None:
        """Beendet Transport und Client (idempotent, wirft nie)."""
        self._started = False
        with _suppress_all():
            await self._transport.stop()


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif block is not None:
                parts.append(str(block))
        return "\n".join(parts)[:2000] or "(leerer Fehler-Content)"
    return str(content)[:2000]


@dataclass
class MCPNodeRegistration:
    """Lebende Registrierung: Client + Cold-Storage-Namen (Shutdown via ``aclose``)."""

    node: str
    config: MCPNodeConfig
    client: MCPNodeClient
    tools: tuple[str, ...] = ()
    server_info: dict[str, Any] = field(default_factory=dict)

    async def aclose(self) -> None:
        await self.client.stop()


@dataclass
class MCPNodeLoadResult:
    """Ergebnis von :func:`load_and_register_mcp_nodes` (fail-closed je Node)."""

    registrations: list[MCPNodeRegistration] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


async def register_mcp_node(
    registry: ColdStorageRegistry,
    config: MCPNodeConfig,
    *,
    event_bus: Any | None = None,
) -> MCPNodeRegistration:
    """Verbindet einen Node und registriert seine Tools im Cold-Storage.

    Ciel-Name: ``<node>.<tool>`` (wie die Limb-Bruecke); Herkunft
    ``mcp:<node>``; Cluster aus Config oder ``mcp:<node>``. Jeder Handler
    ruft ``tools/call`` mit dem Node-Timeout auf (zusaetzlich zur
    Sandbox-``wait_for``-Kapselung — doppelte Absicherung).
    """
    if config.disabled:
        raise CielConfigError(f"MCP-Node {config.name!r} ist deaktiviert (disabled=true).")
    client = MCPNodeClient(config)
    server_info = await client.start()
    try:
        mcp_tools = await client.list_tools()
    except Exception:
        await client.stop()
        raise
    cluster = config.cluster.strip() or f"mcp:{config.name}"
    names: list[str] = []
    for tool in mcp_tools:
        ciel_name = f"{config.name}.{tool.name}"
        handler = _make_tool_handler(client, config, tool.name)
        registry.register(
            {
                "name": ciel_name,
                "description": f"[{config.name}] {tool.description or tool.name}".strip(),
                "parameters": dict(tool.input_schema or {"type": "object", "properties": {}}),
                "meta": {"mcp_node": config.name, "mcp_tool": tool.name, "cluster": cluster},
            },
            handler=handler,
            origin=f"mcp:{config.name}",
            is_deterministic=False,
            timeout_sec=float(config.timeout_sec),
            persist=False,
        )
        names.append(ciel_name)
    emit(event_bus, "ciel.mcp.node_registered", {"node": config.name, "tools": len(names), "server": server_info.get("name", "")})
    return MCPNodeRegistration(node=config.name, config=config, client=client, tools=tuple(names), server_info=dict(server_info))


def _make_tool_handler(client: MCPNodeClient, config: MCPNodeConfig, tool_name: str) -> Any:
    async def _handler(arguments: dict[str, Any]) -> Any:
        try:
            return await asyncio.wait_for(client.call_tool(tool_name, dict(arguments)), timeout=float(config.timeout_sec))
        except TimeoutError as exc:
            raise MCPToolError(config.name, tool_name, f"Timeout nach {float(config.timeout_sec):g}s.") from exc

    _handler.__name__ = f"mcp_{config.name}_{tool_name}".replace(".", "_").replace("-", "_")
    return _handler


async def load_and_register_mcp_nodes(
    registry: ColdStorageRegistry,
    config_path: str | Path,
    *,
    only: Sequence[str] | None = None,
    event_bus: Any | None = None,
) -> MCPNodeLoadResult:
    """Laedt ``mcp_config.json`` und registriert alle (nicht deaktivierten) Nodes.

    Fail-closed je Node: Scheitert ein Node (Prozess tot, URL down, Timeout),
    landet er in ``errors`` (+ ``ciel.mcp.node_failed``-Event) — die anderen
    Nodes und die Schicht laufen unbeeinflusst weiter.
    """
    configs = load_mcp_config(config_path)
    wanted = set(only or ())
    result = MCPNodeLoadResult()
    for name, config in configs.items():
        if wanted and name not in wanted:
            continue
        if config.disabled:
            continue
        try:
            result.registrations.append(await register_mcp_node(registry, config, event_bus=event_bus))
        except Exception as exc:
            result.errors[name] = f"{type(exc).__name__}: {exc}"
            emit(event_bus, "ciel.mcp.node_failed", {"node": name, "error": result.errors[name]})
    if registry.cache_path is not None:
        with _suppress_all():
            registry.save_cache(registry.cache_path)
    return result


__all__ = [
    "MCP_CLIENT_NAME",
    "MCP_PROTOCOL_VERSION",
    "MCPNodeClient",
    "MCPNodeConfig",
    "MCPNodeLoadResult",
    "MCPNodeRegistration",
    "MCPTool",
    "SSEMCPTransport",
    "StdioMCPTransport",
    "expand_env_vars",
    "load_and_register_mcp_nodes",
    "load_mcp_config",
    "register_mcp_node",
]
