from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import unittest
from collections.abc import AsyncIterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from orchestrator.kanban.audit import AuditLedger
from orchestrator.kanban.bus import HeartbeatStore, KanbanBus, TokenStore
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import (
    KanbanBoard,
    KanbanEvent,
    KanbanTask,
    TaskStatus,
    TransitionError,
    Worker,
    WorkerStatus,
)
from orchestrator.kanban.service import ConflictError, KanbanService
from orchestrator.kanban.store import KanbanStore
from orchestrator.kanban.tools import KanbanToolbox, register_kanban_tools


class FakeKanbanStore(KanbanStore):
    def __init__(self):
        self.boards = {}
        self.tasks = {}
        self.workers = {}
        self.audit = []
        self.audit_seq = 0

    async def init(self) -> None: pass
    async def close(self) -> None: pass

    async def create_board(self, board: KanbanBoard) -> KanbanBoard:
        self.boards[board.id] = board
        return board

    async def get_board(self, board_id: str) -> KanbanBoard | None:
        return self.boards.get(board_id)

    async def list_boards(self) -> list[KanbanBoard]:
        return list(self.boards.values())

    async def create_task(self, task: KanbanTask) -> KanbanTask:
        self.tasks[task.id] = task
        return task

    async def get_task(self, task_id: str) -> KanbanTask | None:
        return self.tasks.get(task_id)

    async def list_tasks(self, *, board_id=None, status=None, parent_id=None) -> list[KanbanTask]:
        res = list(self.tasks.values())
        if board_id:
            res = [t for t in res if t.board_id == board_id]
        if status:
            res = [t for t in res if t.status == status]
        if parent_id:
            res = [t for t in res if t.parent_id == parent_id]
        return res

    async def cas_task(self, task_id: str, expected: TaskStatus | None, changes: Any) -> KanbanTask | None:
        task = self.tasks.get(task_id)
        if not task:
            return None
        if expected is not None and task.status != expected:
            return None

        for k, v in changes.items():
            setattr(task, k, v)
        return task

    async def apply_decomposition(self, parent_id: str, children: list[KanbanTask]) -> KanbanTask | None: return None
    async def promotable_tasks(self) -> list[KanbanTask]: return []
    async def rollup_candidates(self) -> list[KanbanTask]: return []

    async def upsert_worker(self, worker: Worker) -> Worker:
        self.workers[worker.uid] = worker
        return worker

    async def get_worker(self, uid: str) -> Worker | None:
        return self.workers.get(uid)

    async def list_workers(self, *, status=None) -> list[Worker]:
        res = list(self.workers.values())
        if status:
            res = [w for w in res if w.status == status]
        return res

    async def cas_worker(self, uid: str, expected: WorkerStatus | None, changes: Any) -> Worker | None: return None
    async def add_experience(self, experience: Any) -> Any: return None
    async def list_experiences(self, *, worker_uid=None, limit=100) -> list[Any]: return []

    async def append_audit(self, draft: Any) -> Any:
        self.audit_seq += 1
        entry = type("AuditEntry", (), {"seq": self.audit_seq, "actor": draft.actor, "action": draft.action, "category": draft.category, "subject": draft.subject, "payload": draft.payload})()
        self.audit.append(entry)
        return entry

    async def list_audit(self, *, after_seq=0, limit=10000) -> list[Any]:
        return [e for e in self.audit if e.seq > after_seq][:limit]

class FakeKanbanBus(KanbanBus):
    async def publish(self, event: KanbanEvent) -> None: pass
    async def subscribe(self) -> AsyncIterator[KanbanEvent]:
        while False:
            yield
    async def close(self) -> None: pass

class FakeHeartbeatStore(HeartbeatStore):
    async def beat(self, task_id: str, ttl_s: float, *, worker_uid: str = "") -> None: pass
    async def alive(self, task_id: str) -> bool: return True
    async def clear(self, task_id: str) -> None: pass

class FakeTokenStore(TokenStore):
    def __init__(self): self.tokens = {}
    async def put(self, token: str, claims: dict[str, str], ttl_s: float) -> None: self.tokens[token] = claims
    async def get(self, token: str) -> dict[str, str] | None: return self.tokens.get(token)
    async def revoke(self, token: str) -> None: self.tokens.pop(token, None)


class TestKanbanServiceTools(unittest.TestCase):
    def setUp(self):
        self.store = FakeKanbanStore()
        self.bus = FakeKanbanBus()
        self.ledger = AuditLedger(self.store)
        self.heartbeats = FakeHeartbeatStore()
        self.tokens = FakeTokenStore()
        self.config = KanbanConfig()

        self.service = KanbanService(
            store=self.store,
            bus=self.bus,
            ledger=self.ledger,
            heartbeats=self.heartbeats,
            tokens=self.tokens,
            config=self.config
        )

    def test_service_create_task_cycle(self):
        async def run():
            board = await self.service.create_board("test", actor="sys")
            t1 = await self.service.create_task(board_id=board.id, title="t1", actor="sys")
            t2 = await self.service.create_task(board_id=board.id, title="t2", dependencies=[t1.id], actor="sys")
            t3 = await self.service.create_task(board_id=board.id, title="t3", dependencies=[t2.id], actor="sys")

            self.store.tasks[t1.id].dependencies = [t3.id]

            with self.assertRaises(ValueError) as cm:
                await self.service._check_cycles([t2.id])
            self.assertIn("Zyklus", str(cm.exception))

            with self.assertRaises(ValueError):
                await self.service.create_task(board_id=board.id, title="t5", dependencies=["not-exist"], actor="sys")

        asyncio.run(run())

    def test_service_transition_cas(self):
        async def run():
            board = await self.service.create_board("test", actor="sys")
            t = await self.service.create_task(board_id=board.id, title="t", actor="sys")

            with self.assertRaises(TransitionError):
                await self.service.transition(t.id, TaskStatus.IN_PROGRESS, actor="sys", expected=TaskStatus.COMPLETED)

            with self.assertRaises(ConflictError):
                await self.service.transition(t.id, TaskStatus.READY, actor="sys", expected=TaskStatus.BACKLOG)

            t_updated = await self.service.transition(t.id, TaskStatus.BACKLOG, actor="sys", expected=TaskStatus.TRIAGE)
            self.assertEqual(t_updated.status, TaskStatus.BACKLOG)

        asyncio.run(run())

    def test_toolbox_permissions_and_actions(self):
        async def run():
            board = await self.service.create_board("test", actor="sys")
            w_a = await self.service.create_worker(uid="worker-a", name="A", skills=[], actor="sys")
            w_b = await self.service.create_worker(uid="worker-b", name="B", skills=[], actor="sys")

            t_a = await self.service.create_task(board_id=board.id, title="ta", actor="sys")
            t_b = await self.service.create_task(board_id=board.id, title="tb", actor="sys")

            await self.tokens.put("tok_a", {"task_id": t_a.id, "worker_uid": w_a.uid}, 3600)
            await self.tokens.put("tok_b", {"task_id": t_b.id, "worker_uid": w_b.uid}, 3600)

            toolbox = KanbanToolbox(self.service, self.tokens)

            with self.assertRaises(PermissionError):
                await toolbox.call("kanban_show", {}, "invalid")

            with self.assertRaises(PermissionError):
                await toolbox.call("kanban_show", {"task_id": t_b.id}, "tok_a")

            res = await toolbox.call("kanban_create", {"title": "sub-a"}, "tok_a")
            sub_id = res["task"]["id"]
            self.assertEqual(res["task"]["parent_id"], t_a.id)

            res_show = await toolbox.call("kanban_show", {"task_id": sub_id}, "tok_a")
            self.assertEqual(res_show["task"]["id"], sub_id)

            await self.service.transition(t_a.id, TaskStatus.BACKLOG, actor="sys")
            await self.service.transition(t_a.id, TaskStatus.READY, actor="sys")
            await self.service.transition(t_a.id, TaskStatus.IN_PROGRESS, actor="sys")
            await toolbox.call("kanban_complete", {"result_payload": {"done": True}}, "tok_a")

            t_a_after = await self.store.get_task(t_a.id)
            self.assertEqual(t_a_after.status, TaskStatus.COMPLETED)
            self.assertEqual(t_a_after.result_payload, {"done": True})

            audit = [e for e in self.store.audit if e.action == "transition" and e.subject == t_a.id]
            self.assertEqual(audit[-1].actor, "worker:worker-a")

        asyncio.run(run())

class MCPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/v1/kanban/tools":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps([{"name": "test_tool"}]).encode())

    def do_POST(self):
        if self.path.startswith("/api/v1/kanban/tools/"):
            auth = self.headers.get("Authorization")
            if auth != "Bearer valid-token":
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
                return

            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "tool": body["tool"]}).encode())

class TestKanbanMCP(unittest.TestCase):
    def test_mcp_shim(self):
        server = HTTPServer(("127.0.0.1", 0), MCPHandler)
        port = server.server_port

        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        try:
            env = os.environ.copy()
            env["NIO_KANBAN_API_URL"] = f"http://127.0.0.1:{port}"
            env["NIO_KANBAN_TASK_TOKEN"] = "valid-token"

            shim_path = "orchestrator/kanban/mcp_shim.py"

            inputs = [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
                json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "test_tool", "arguments": {}}}),
            ]

            proc = subprocess.Popen(
                [sys.executable, shim_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )

            out, _ = proc.communicate(input="\n".join(inputs) + "\n")
            lines = [line for line in out.splitlines() if line.strip()]

            self.assertEqual(len(lines), 3)

            r1 = json.loads(lines[0])
            self.assertEqual(r1["id"], 1)
            self.assertIn("protocolVersion", r1["result"])

            r2 = json.loads(lines[1])
            self.assertEqual(r2["id"], 2)
            self.assertEqual(r2["result"]["tools"][0]["name"], "test_tool")

            r3 = json.loads(lines[2])
            self.assertEqual(r3["id"], 3)
            self.assertFalse(r3["result"]["isError"])
            content = r3["result"]["content"][0]["text"]
            self.assertIn("success", content)

        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1.0)

    def test_mcp_shim_auth_error(self):
        server = HTTPServer(("127.0.0.1", 0), MCPHandler)
        port = server.server_port

        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        try:
            env = os.environ.copy()
            env["NIO_KANBAN_API_URL"] = f"http://127.0.0.1:{port}"
            env["NIO_KANBAN_TASK_TOKEN"] = "invalid"

            shim_path = "orchestrator/kanban/mcp_shim.py"

            inputs = [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "test_tool", "arguments": {}}}),
            ]

            proc = subprocess.Popen(
                [sys.executable, shim_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )

            out, _ = proc.communicate(input="\n".join(inputs) + "\n")
            lines = [line for line in out.splitlines() if line.strip()]

            self.assertEqual(len(lines), 1)

            r1 = json.loads(lines[0])
            self.assertEqual(r1["id"], 1)
            self.assertTrue(r1["result"]["isError"])

        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1.0)

class TestCielRegistry(unittest.TestCase):
    def test_ciel_registration(self):
        try:
            import apollo.ciel.registry  # noqa: F401
        except ImportError:
            self.skipTest("apollo is missing")

        class FakeRegistry:
            def __init__(self): self.tools = {}
            def get(self, name): return self.tools.get(name)
            def register(self, tool, handler=None, origin="fastmcp", persist=True):
                self.tools[tool["name"]] = tool

        registry = FakeRegistry()
        register_kanban_tools(registry, None, lambda: "tok")
        self.assertIn("kanban_show", registry.tools)
