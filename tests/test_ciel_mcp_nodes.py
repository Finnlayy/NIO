"""Tests der MCP-Node-Anbindung (apollo.ciel.mcp_nodes).

Vollstaendig offline: Ein Fake-MCP-Server spricht echtes JSON-RPC-2.0-Framing
ueber stdio (als Subprozess) bzw. echtes SSE+POST (via lokalem HTTP-Server).
Weder `npx` noch externe URLs werden angeruehrt.

Beweist: Handshake, tools/list, tools/call, isError- und Timeout-Pfade,
Config-Loader (inkl. ${VAR}-Expansion), Ciel-Registry-Integration und das
Fail-closed-Verhalten (ein toter Node stoppt nichts).
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from apollo.ciel import (
    CielConfigError,
    ColdStorageRegistry,
    MCPNodeClient,
    MCPToolError,
    MCPTransportError,
    NCMGate,
    RegistryFunctionExecutor,
    load_and_register_mcp_nodes,
    load_mcp_config,
    register_mcp_node,
)

_FAKE_TOOLS = [
    {
        "name": "stalk_lookup",
        "description": "Look up an address on the chain.",
        "inputSchema": {
            "type": "object",
            "properties": {"address": {"type": "string"}},
            "required": ["address"],
        },
    },
    {
        "name": "stalk_follow",
        "description": "Follow fund flows from an address.",
        "inputSchema": {"type": "object", "properties": {"address": {"type": "string"}}},
    },
    {
        "name": "hang",
        "description": "Never answers (timeout probe).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _fake_rpc_reply(message: dict[str, Any]) -> dict[str, Any] | None:
    """Fake-Server-Logik (wird vom stdio-Skript wie vom SSE-Server genutzt)."""
    method = message.get("method")
    rpc_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "fake-stalkchain", "version": "0.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": _FAKE_TOOLS}}
    if method == "tools/call":
        params = message.get("params", {}) or {}
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        if name == "hang":
            time.sleep(30)
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"content": [{"type": "text", "text": "never"}]}}
        if name == "boom":
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"content": [{"type": "text", "text": "kaboom"}], "isError": True},
            }
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"content": [{"type": "text", "text": f"stalk:{name}:{json.dumps(args, sort_keys=True)}"}]},
        }
    if rpc_id is not None:
        return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": "Method not found"}}
    return None  # Notification -> keine Antwort


_STDIO_SCRIPT = """\
import json
import sys
import time

TOOLS = json.loads({tools_json!r})

def read_message():
    length = None
    while True:
        line = sys.stdin.buffer.readline().decode("utf-8")
        if line == "":
            raise EOFError()
        text = line.strip()
        if not text:
            break
        if ":" in text:
            key, value = text.split(":", 1)
            if key.strip().lower() == "content-length":
                length = int(value.strip())
    if length is None:
        raise ValueError("missing Content-Length")
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))

def send(obj):
    data = json.dumps(obj).encode("utf-8")
    sys.stdout.buffer.write(("Content-Length: %d\\r\\n\\r\\n" % len(data)).encode("ascii") + data)
    sys.stdout.buffer.flush()

while True:
    try:
        message = read_message()
    except (EOFError, ValueError):
        break
    method = message.get("method")
    rpc_id = message.get("id")
    if method == "initialize":
        send({{"jsonrpc": "2.0", "id": rpc_id, "result": {{"protocolVersion": "2024-11-05", "capabilities": {{}}, "serverInfo": {{"name": "fake-stalkchain", "version": "0.0.0"}}}}}})
    elif method == "tools/list":
        send({{"jsonrpc": "2.0", "id": rpc_id, "result": {{"tools": TOOLS}}}})
    elif method == "tools/call":
        params = message.get("params", {{}}) or {{}}
        name = params.get("name")
        args = params.get("arguments", {{}}) or {{}}
        if name == "hang":
            time.sleep(30)
        if name == "boom":
            send({{"jsonrpc": "2.0", "id": rpc_id, "result": {{"content": [{{"type": "text", "text": "kaboom"}}], "isError": True}}}})
        else:
            send({{"jsonrpc": "2.0", "id": rpc_id, "result": {{"content": [{{"type": "text", "text": "stalk:%s:%s" % (name, json.dumps(args, sort_keys=True))}}]}}}})
    elif rpc_id is not None:
        send({{"jsonrpc": "2.0", "id": rpc_id, "error": {{"code": -32601, "message": "Method not found"}}}})
"""


def _write_stdio_server(tmp_path: Path) -> Path:
    script = tmp_path / "fake_mcp_stdio.py"
    script.write_text(_STDIO_SCRIPT.format(tools_json=json.dumps(_FAKE_TOOLS)), encoding="utf-8")
    return script


def _write_config(tmp_path: Path, servers: dict[str, Any]) -> Path:
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
    return path


class _FakeSSEHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "FakeSSE/1"

    def log_message(self, *_args: object) -> None:
        pass

    def _emit(self, event: str, data: str) -> None:
        with self.server.state["lock"]:
            self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode())
            self.wfile.flush()

    def do_GET(self) -> None:
        if self.path != "/mcp":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        with self.server.state["lock"]:
            self.server.state["stream"] = self
        try:
            self._emit("endpoint", "/mcp/messages?sessionId=test1")
            while not self.server.state["stop"].is_set():
                time.sleep(0.02)
        finally:
            with self.server.state["lock"]:
                if self.server.state["stream"] is self:
                    self.server.state["stream"] = None

    def do_POST(self) -> None:
        if not self.path.startswith("/mcp/messages"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        message = json.loads(self.rfile.read(length).decode("utf-8"))
        reply = _fake_rpc_reply(message)
        if reply is not None and "id" in message:
            with self.server.state["lock"]:
                stream = self.server.state["stream"]
            if stream is not None:
                stream._emit("message", json.dumps(reply))
        self.send_response(202)
        self.send_header("Content-Length", "0")
        self.end_headers()


class _FakeSSEServer:
    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeSSEHandler)
        self.httpd.daemon_threads = True
        self.httpd.state = {"lock": threading.RLock(), "stream": None, "stop": threading.Event()}
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/mcp"

    def __enter__(self) -> _FakeSSEServer:
        self.thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.httpd.state["stop"].set()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5.0)


# ---------------------------------------------------------------------------
# stdio-Transport: echter Subprozess-Roundtrip
# ---------------------------------------------------------------------------


def test_stdio_node_roundtrip(tmp_path: Path) -> None:
    script = _write_stdio_server(tmp_path)
    config_path = _write_config(
        tmp_path,
        {"fake": {"command": sys.executable, "args": [str(script)], "timeout_sec": 10.0, "cluster": "chain-data"}},
    )

    async def main() -> tuple[dict[str, Any], list[str], Any]:
        configs = load_mcp_config(config_path)
        assert set(configs) == {"fake"} and configs["fake"].transport == "stdio"
        async with MCPNodeClient(configs["fake"]) as client:
            tools = await client.list_tools()
            assert [t.name for t in tools] == ["stalk_lookup", "stalk_follow", "hang"]
            assert tools[0].input_schema["required"] == ["address"]
            assert tools[0].node == "fake"
            result = await client.call_tool("stalk_lookup", {"address": "0xabc"})
            return dict(client.server_info), [t.name for t in tools], result

    server_info, names, result = asyncio.run(main())
    assert server_info["name"] == "fake-stalkchain"
    assert names == ["stalk_lookup", "stalk_follow", "hang"]
    assert result["content"][0]["text"] == 'stalk:stalk_lookup:{"address": "0xabc"}'


def test_stdio_call_error_and_timeout(tmp_path: Path) -> None:
    script = _write_stdio_server(tmp_path)
    config_path = _write_config(tmp_path, {"fake": {"command": sys.executable, "args": [str(script)], "timeout_sec": 0.3}})

    async def main() -> None:
        configs = load_mcp_config(config_path)
        async with MCPNodeClient(configs["fake"]) as client:
            with pytest.raises(MCPToolError, match="kaboom"):
                await client.call_tool("boom", {})
            started = time.monotonic()
            with pytest.raises(MCPToolError, match=r"[Tt]imeout"):
                await client.call_tool("hang", {})
            assert time.monotonic() - started < 10, "Timeout-Pfad haengt"

    asyncio.run(main())


def test_stdio_dead_process_raises_transport_error(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, {"dead": {"command": "/nonexistent/mcp-server-binary-xyz"}})

    async def main() -> None:
        configs = load_mcp_config(config_path)
        client = MCPNodeClient(configs["dead"])
        with pytest.raises(MCPTransportError, match="scheiterte"):
            await client.start()
        await client.stop()  # wirft nie

    asyncio.run(main())


# ---------------------------------------------------------------------------
# SSE-Transport: echter lokaler HTTP-Roundtrip (kein Netz)
# ---------------------------------------------------------------------------


def test_sse_node_roundtrip() -> None:
    with _FakeSSEServer() as server:
        # Config direkt (ohne Datei) — der Loader wird separat getestet.
        from apollo.ciel import MCPNodeConfig

        config = MCPNodeConfig(name="direct", transport="sse", url=server.url, timeout_sec=10.0)

        async def run() -> tuple[list[str], Any, dict[str, Any]]:
            async with MCPNodeClient(config) as client:
                tools = await client.list_tools()
                result = await client.call_tool("stalk_follow", {"address": "0x1"})
                return [t.name for t in tools], result, dict(client.server_info)

        names, result, server_info = asyncio.run(run())
    assert names == ["stalk_lookup", "stalk_follow", "hang"]
    assert result["content"][0]["text"] == 'stalk:stalk_follow:{"address": "0x1"}'
    assert server_info["name"] == "fake-stalkchain"


def test_sse_unreachable_fails_fast() -> None:
    from apollo.ciel import MCPNodeConfig

    config = MCPNodeConfig(name="down", transport="sse", url="http://127.0.0.1:9/mcp", timeout_sec=2.0)

    async def main() -> None:
        client = MCPNodeClient(config)
        started = time.monotonic()
        with pytest.raises(MCPTransportError):
            await client.start()
        assert time.monotonic() - started < 10
        await client.stop()

    asyncio.run(main())


# ---------------------------------------------------------------------------
# Config-Loader
# ---------------------------------------------------------------------------


def test_load_mcp_config_variants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STALKCHAIN_API_KEY", "sekret-test-key")
    path = _write_config(
        tmp_path,
        {
            "node_stdio": {"command": "npx", "args": ["-y", "x"], "env": {"K": "${STALKCHAIN_API_KEY}"}},
            "node_sse": {"url": "https://example.invalid/mcp", "headers": {"Authorization": "Bearer $STALKCHAIN_API_KEY"}},
            "node_off": {"command": "x", "disabled": True},
        },
    )
    configs = load_mcp_config(path)
    assert configs["node_stdio"].transport == "stdio"
    assert configs["node_sse"].transport == "sse"  # inferiert aus url
    assert configs["node_off"].disabled is True
    from apollo.ciel import expand_env_vars

    assert expand_env_vars(configs["node_stdio"].env["K"]) == "sekret-test-key"
    assert expand_env_vars(configs["node_sse"].headers["Authorization"]) == "Bearer sekret-test-key"
    assert expand_env_vars("x-${FEHLT}-y") == "x--y"

    bad1 = tmp_path / "bad1.json"
    bad1.write_text(json.dumps({"mcpServers": {"x": {"transport": "stdio"}}}), encoding="utf-8")
    with pytest.raises(CielConfigError, match="command"):
        load_mcp_config(bad1)
    bad2 = tmp_path / "bad2.json"
    bad2.write_text(json.dumps({"mcpServers": {"x": {"transport": "pigeon", "command": "y"}}}), encoding="utf-8")
    bad_transport = bad2
    with pytest.raises(CielConfigError, match="Transport"):
        load_mcp_config(bad_transport)
    with pytest.raises(CielConfigError, match="fehlt"):
        load_mcp_config(tmp_path / "gibt-es-nicht.json")


# ---------------------------------------------------------------------------
# Ciel-Integration: Node-Tools -> Cold-Storage -> Gate
# ---------------------------------------------------------------------------


def test_register_mcp_node_into_ciel(tmp_path: Path) -> None:
    from orchestrator.events import CollectingSink, EventBus

    script = _write_stdio_server(tmp_path)
    config_path = _write_config(
        tmp_path,
        {"fake": {"command": sys.executable, "args": [str(script)], "timeout_sec": 10.0, "cluster": "chain-data"}},
    )
    sink = CollectingSink()
    bus = EventBus([sink])
    registry = ColdStorageRegistry(event_bus=bus)

    async def main() -> Any:
        configs = load_mcp_config(config_path)
        registration = await register_mcp_node(registry, configs["fake"], event_bus=bus)
        try:
            assert registration.tools == ("fake.stalk_lookup", "fake.stalk_follow", "fake.hang")
            record = registry.require("fake.stalk_lookup")
            assert record.origin == "mcp:fake"
            assert record.meta["cluster"] == "chain-data"
            assert record.node_id.startswith("ciel-node-")
            assert record.required_state_keys == ["address"]  # aus inputSchema.required
            executor = RegistryFunctionExecutor(registry)
            assert executor.can_execute("fake.stalk_lookup")
            result = await executor.execute("fake.stalk_lookup", {"address": "0xabc"})
            gate = NCMGate(registry)
            matches = gate.match("look up address on chain")
            return result, [m.name for m in matches]
        finally:
            await registration.aclose()

    result, top = asyncio.run(main())
    assert result["content"][0]["text"] == 'stalk:stalk_lookup:{"address": "0xabc"}'
    assert "fake.stalk_lookup" in top  # NCM findet das Node-Tool per Cold-Storage-Anchor
    assert "ciel.mcp.node_registered" in sink.kinds()


def test_load_and_register_fail_closed_per_node(tmp_path: Path) -> None:
    from orchestrator.events import CollectingSink, EventBus

    script = _write_stdio_server(tmp_path)
    config_path = _write_config(
        tmp_path,
        {
            "good": {"command": sys.executable, "args": [str(script)], "timeout_sec": 10.0},
            "bad": {"command": "/nonexistent/mcp-server-binary-xyz"},
            "off": {"command": "/nonexistent/auch-egal", "disabled": True},
        },
    )
    sink = CollectingSink()
    bus = EventBus([sink])
    registry = ColdStorageRegistry(event_bus=bus)

    async def main() -> Any:
        loaded = await load_and_register_mcp_nodes(registry, config_path, event_bus=bus)
        try:
            return loaded
        finally:
            for registration in loaded.registrations:
                await registration.aclose()

    loaded = asyncio.run(main())
    assert [r.node for r in loaded.registrations] == ["good"]
    assert set(loaded.errors) == {"bad"}  # toter Node -> Fehler, kein Crash
    assert "off" not in loaded.errors  # disabled -> still uebersprungen
    assert "good.stalk_lookup" in registry
    assert "ciel.mcp.node_registered" in sink.kinds()
    assert "ciel.mcp.node_failed" in sink.kinds()
