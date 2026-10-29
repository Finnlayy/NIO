"""Tests fuer die Kanban-FastAPI-Schicht (WP-07)."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

try:
    import fastapi
    from fastapi.testclient import TestClient
except ImportError:
    fastapi = None  # type: ignore

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import AuditEntry, Experience, KanbanBoard, KanbanTask, RustLimb, Worker
from orchestrator.kanban.runtime import build_runtime

if fastapi is not None:
    from orchestrator.kanban.api import AuditEntryOut, BoardOut, ExperienceOut, RustLimbOut, TaskOut, WorkerOut, build_app


@unittest.skipUnless(fastapi is not None, "FastAPI nicht installiert")
class KanbanApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Write some secrets
        self.api_token = "secret123"
        self.config = KanbanConfig(
            repo_root=self.root,
            store="sqlite",
            sqlite_path=self.root / "kanban.db",
            bus="memory",
            sandbox="subprocess",
            workspace_dir=self.root / "workspace",
            vault_dir=self.root / "vault",
            api_token=self.api_token,
        )
        self.runtime = await build_runtime(self.config)
        self.app = build_app(self.runtime)
        self.client = TestClient(self.app)

        # Pre-populate some basic entities directly
        self.board = await self.runtime.service.create_board("test-board", actor="test")

    async def asyncTearDown(self) -> None:
        await self.runtime.close()
        self.temp_dir.cleanup()

    def test_model_parity(self) -> None:
        """Pydantic-Out-Modelle muessen 1:1 die Felder der Dataclasses haben."""
        mapping = {
            TaskOut: KanbanTask,
            WorkerOut: Worker,
            ExperienceOut: Experience,
            AuditEntryOut: AuditEntry,
            BoardOut: KanbanBoard,
            RustLimbOut: RustLimb,
        }
        for pydantic_model, dataclass_model in mapping.items():
            py_fields = set(pydantic_model.model_fields.keys())
            dc_fields = set(dataclass_model.__dataclass_fields__.keys())
            self.assertEqual(py_fields, dc_fields, f"Mismatch in {pydantic_model.__name__} vs {dataclass_model.__name__}")

    def test_auth_missing(self) -> None:
        resp = self.client.get("/api/v1/kanban/boards")
        self.assertEqual(resp.status_code, 401)

    def test_auth_invalid(self) -> None:
        resp = self.client.get("/api/v1/kanban/boards", headers={"Authorization": "Bearer wrong"})
        self.assertEqual(resp.status_code, 401)

    def test_crud_board_and_task(self) -> None:
        headers = {"Authorization": f"Bearer {self.api_token}"}

        # List boards
        resp = self.client.get("/api/v1/kanban/boards", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["name"], "test-board")

        # Create task
        resp = self.client.post("/api/v1/kanban/tasks", json={
            "board_id": self.board.id,
            "title": "API Task",
            "description": "desc"
        }, headers=headers)
        self.assertEqual(resp.status_code, 200)
        task_id = resp.json()["id"]

        # Get task
        resp = self.client.get(f"/api/v1/kanban/tasks/{task_id}", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["task"]["title"], "API Task")

        # Transition task (valid)
        resp = self.client.post(f"/api/v1/kanban/tasks/{task_id}/transition", json={
            "target": "backlog",
            "reason": "moving"
        }, headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "backlog")

        # Transition task (invalid: conflict -> expecting backlog, passing blocked)
        resp = self.client.post(f"/api/v1/kanban/tasks/{task_id}/transition", json={
            "target": "ready",
            "expected": "blocked"
        }, headers=headers)
        self.assertEqual(resp.status_code, 409)

    def test_tool_call_invalid_token(self) -> None:
        resp = self.client.post("/api/v1/kanban/tools/kanban_show", json={"arguments": {}},
                                headers={"Authorization": "Bearer not-a-task-token"})
        self.assertEqual(resp.status_code, 401)

    def test_operator_routes_closed_without_token(self) -> None:
        self.runtime.config = replace(self.config, api_token="")
        resp = self.client.get("/api/v1/kanban/boards", headers={"Authorization": "Bearer anything"})
        self.assertEqual(resp.status_code, 503)

    async def test_tool_token_is_scoped_to_its_task(self) -> None:
        own = await self.runtime.service.create_task(board_id=self.board.id, title="own", actor="test")
        other = await self.runtime.service.create_task(board_id=self.board.id, title="other", actor="test")
        await self.runtime.tokens.put("tok-own", {"task_id": own.id, "worker_uid": "alpha"}, 60)
        headers = {"Authorization": "Bearer tok-own"}

        resp = self.client.post("/api/v1/kanban/tools/kanban_show", json={"arguments": {}}, headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["task"]["id"], own.id)

        resp = self.client.post("/api/v1/kanban/tools/kanban_show", json={"arguments": {"task_id": other.id}}, headers=headers)
        self.assertEqual(resp.status_code, 403)

        # Das Operator-Token gilt nicht als Task-Token und umgekehrt.
        resp = self.client.get("/api/v1/kanban/boards", headers=headers)
        self.assertEqual(resp.status_code, 401)

    def test_unknown_task_is_404(self) -> None:
        headers = {"Authorization": f"Bearer {self.api_token}"}
        self.assertEqual(self.client.get("/api/v1/kanban/tasks/t-000000000000", headers=headers).status_code, 404)

    def test_rust_limb_registry(self) -> None:
        headers = {"Authorization": f"Bearer {self.api_token}"}
        limb = {"name": "pricer", "version": "0.1.0", "contract_version": "1", "endpoint": "http://127.0.0.1:9"}
        self.assertEqual(self.client.post("/api/v1/rust-limbs", json=limb, headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/rust-limbs", headers=headers).json(), [limb])
        self.assertTrue((self.root / "runtime" / "kanban" / "rust_limbs.json").is_file())
        resp = self.client.post("/api/v1/rust-limbs/pricer/invoke", json={"request_id": "r1", "operation": "x"}, headers=headers)
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(self.client.get("/api/v1/audit/verify", headers=headers).json()["ok"], True)


if __name__ == "__main__":
    unittest.main()
