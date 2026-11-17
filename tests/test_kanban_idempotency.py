"""Idempotenz von ``create_task``: ein wiederholter Sprachbefehl legt keinen zweiten Task an."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.runtime import build_runtime
from orchestrator.kanban.service import ConflictError


class KanbanIdempotencyTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        config = KanbanConfig(
            repo_root=root,
            store="sqlite",
            sqlite_path=root / "kanban.db",
            bus="memory",
            sandbox="subprocess",
            workspace_dir=root / "workspace",
            vault_dir=root / "vault",
            api_token="t",
            stop_file=root / "runtime" / "STOP",
        )
        self.runtime = await build_runtime(config)
        self.service = self.runtime.service
        self.board = await self.service.create_board("Apollo", actor="test")

    async def asyncTearDown(self) -> None:
        await self.runtime.close()
        self.temp_dir.cleanup()

    async def test_same_key_returns_the_first_task(self) -> None:
        first = await self.service.create_task(board_id=self.board.id, title="Hallo", idempotency_key="voice-key-1", actor="test")
        again = await self.service.create_task(board_id=self.board.id, title="Hallo", idempotency_key="voice-key-1", actor="test")
        self.assertEqual(first.id, again.id)
        self.assertEqual(len(await self.runtime.store.list_tasks(board_id=self.board.id)), 1)

    async def test_concurrent_retries_create_one_task(self) -> None:
        results = await asyncio.gather(
            *(self.service.create_task(board_id=self.board.id, title="Hallo", idempotency_key="voice-key-2", actor="test") for _ in range(5))
        )
        self.assertEqual(len({task.id for task in results}), 1)
        self.assertEqual(len(await self.runtime.store.list_tasks(board_id=self.board.id)), 1)

    async def test_key_reused_for_other_title_is_a_conflict(self) -> None:
        await self.service.create_task(board_id=self.board.id, title="Hallo", idempotency_key="voice-key-3", actor="test")
        with self.assertRaises(ConflictError):
            await self.service.create_task(board_id=self.board.id, title="Anderer Befehl", idempotency_key="voice-key-3", actor="test")

    async def test_without_key_every_call_creates_a_task(self) -> None:
        await self.service.create_task(board_id=self.board.id, title="Hallo", actor="test")
        await self.service.create_task(board_id=self.board.id, title="Hallo", actor="test")
        self.assertEqual(len(await self.runtime.store.list_tasks(board_id=self.board.id)), 2)


if __name__ == "__main__":
    unittest.main()
