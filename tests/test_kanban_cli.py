"""Ende-zu-Ende-Tests fuer das Kanban-CLI ueber den orchestrator (WP-07)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


class KanbanCliContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.env = os.environ.copy()
        self.env["NEU_ROOT"] = str(self.root)
        self.env["NIO_KANBAN_WORKSPACE"] = str(self.root / "workspace")
        self.env["NIO_OBSIDIAN_VAULT"] = str(self.root / "vault")
        self.env["NIO_KANBAN_SQLITE_PATH"] = str(self.root / "kanban.db")
        self.env["NIO_KANBAN_STORE"] = "sqlite"
        self.env["NIO_KANBAN_BUS"] = "memory"
        self.env["NIO_KANBAN_SANDBOX"] = "subprocess"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str) -> Any:
        cmd = [sys.executable, "-m", "orchestrator", "--json", "kanban", *args]
        res = subprocess.run(cmd, env=self.env, capture_output=True, text=True, check=True)
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError as e:
            self.fail(f"Could not decode JSON from CLI output:\n{res.stdout}\nError: {e}")

    def test_e2e_scenario(self) -> None:
        # 1. Init
        res = self.run_cli("init")
        self.assertTrue(res.get("ok"))

        # 2. Worker
        w = self.run_cli("worker", "create", "alpha", "--skill", "code")
        self.assertEqual(w.get("uid"), "alpha")

        # 3. Board
        b = self.run_cli("board", "create", "demo")
        board_id = b.get("id")
        self.assertTrue(board_id)

        # 4. Task with checklist
        desc_path = self.root / "desc.md"
        desc_path.write_text("- [ ] First step\n- [ ] Second step", encoding="utf-8")
        t = self.run_cli("task", "create", "--board", board_id, "--title", "E2E Task", "--description-file", str(desc_path))
        self.assertEqual(t.get("status"), "triage")

        # 5. Ticks: zerlegen, befoerdern, zuweisen, ausfuehren, Roll-up.
        for _ in range(4):
            self.run_cli("tick", "--wait")

        tasks = {x["title"]: x for x in self.run_cli("task", "list", "--board", board_id)}
        self.assertEqual({k: v["status"] for k, v in tasks.items()},
                         {"E2E Task": "completed", "First step": "completed", "Second step": "completed"})
        self.assertTrue(tasks["E2E Task"]["is_rollup"])

        experiences = list((self.root / "vault" / "workers" / "alpha" / "experiences").glob("*.md"))
        self.assertEqual(len(experiences), 2)
        self.assertEqual(list(self.root.rglob("*.tmp")), [])

        audit_res = self.run_cli("audit", "verify")
        self.assertTrue(audit_res.get("ok"))

    def test_unknown_task_exits_nonzero(self) -> None:
        cmd = [sys.executable, "-m", "orchestrator", "kanban", "task", "show", "t-000000000000"]
        res = subprocess.run(cmd, env=self.env, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 1)
        self.assertIn("t-000000000000", res.stderr)


if __name__ == "__main__":
    unittest.main()
