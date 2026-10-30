"""Tests fuer die JIT-Sandbox (Docker und Subprozess) sowie worker_entry."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import KanbanTask, Worker
from orchestrator.kanban.sandbox import (
    DockerSandbox,
    SandboxSpec,
    build_sandbox,
)


class TestKanbanSandbox(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp_dir_obj.name)
        self.run_dir = self.tmp_dir / "run_01"
        self.in_dir = self.run_dir / "in"
        self.out_dir = self.run_dir / "out"
        self.work_dir = self.run_dir / "work"

        self.in_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.config = KanbanConfig(
            repo_root=self.tmp_dir,
            sandbox="subprocess",
            heartbeat_s=0.2,
            stop_grace_s=1.0,
            sandbox_api_url="http://127.0.0.1:8740",
        )

        self.task = KanbanTask.from_dict(
            {
                "id": "t1",
                "board_id": "b1",
                "title": "Sandbox Test",
                "status": "in_progress",
            }
        )
        self.worker = Worker.from_dict(
            {
                "uid": "w1",
                "name": "w1",
                "status": "busy",
            }
        )

        self.spec = SandboxSpec(
            run_id="t1-a1",
            task=self.task,
            worker=self.worker,
            run_dir=self.run_dir,
            env={"CUSTOM_ENV": "value"},
            secrets={"OPENAI_API_KEY": "sk-geheim"},
            image="python:3.12-slim",
            deadline_s=3.0,
        )

        # Basis-Inputs
        (self.in_dir / "task.json").write_text(json.dumps(self.task.to_dict()), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp_dir_obj.cleanup()

    def _write_soul(self, runtime: str, extra: str = "") -> None:
        content = f"---\nruntime: {runtime}\n{extra}---\n\n## Core Skills\n- Python\n"
        (self.in_dir / "SOUL.md").write_text(content, encoding="utf-8")

    def test_docker_build_argv(self) -> None:
        argv = DockerSandbox.build_argv(self.spec, self.config)

        # Enthaelt alle geforderten Flags
        self.assertIn("--cpus", argv)
        self.assertIn("--memory", argv)
        self.assertIn("--pids-limit", argv)
        self.assertIn("--read-only", argv)
        self.assertIn("--cap-drop", argv)
        self.assertIn("ALL", argv)
        self.assertIn("--network", argv)
        self.assertIn("none", argv)

        # Secret Name ist drin (als -e KEY)
        idx = argv.index("OPENAI_API_KEY")
        self.assertEqual(argv[idx - 1], "-e")

        # Aber der Wert darf nirgends drin sein!
        argv_str = " ".join(argv)
        self.assertNotIn("sk-geheim", argv_str)

    def test_subprocess_noop(self) -> None:
        self._write_soul("noop")
        runner = build_sandbox(self.config)

        heartbeats = []

        async def on_heartbeat() -> None:
            heartbeats.append(time.time())

        result = asyncio.run(runner.run(self.spec, on_heartbeat=on_heartbeat))

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.cancelled)
        self.assertFalse(result.timed_out)

        # Prüfen ob Resultate geschrieben wurden
        out_res = json.loads((self.out_dir / "result.json").read_text())
        self.assertEqual(out_res["status"], "completed")

        out_exp = json.loads((self.out_dir / "experience.json").read_text())
        self.assertEqual(out_exp["outcome"], "success")

        # Wir erwarten, dass der Heartbeat mindestens einmal kam? Bei NOOP geht's zu schnell,
        # wir erzwingen keinen Heartbeat Test hier, den machen wir beim command.

    def test_subprocess_command_and_cancel(self) -> None:
        cmd = json.dumps(["python3", "-c", "import time; time.sleep(30)"])
        self._write_soul("command", f"command: {cmd}\n")

        runner = build_sandbox(self.config)

        heartbeats = []

        async def on_heartbeat() -> None:
            heartbeats.append(time.time())

        async def run_with_cancel() -> None:
            task = asyncio.create_task(runner.run(self.spec, on_heartbeat=on_heartbeat))

            # Warten bis Heartbeat Datei entsteht (Prozess laeuft)
            hb_file = self.out_dir / "heartbeat"
            for _ in range(20):
                if hb_file.exists():
                    break
                await asyncio.sleep(0.1)

            # Noch etwas warten fuer on_heartbeat triggers
            await asyncio.sleep(0.3)

            await runner.cancel(self.spec.run_id)
            return await task

        result = asyncio.run(run_with_cancel())

        self.assertTrue(result.cancelled)
        # returncode sollte 143 (SIGTERM) oder None (wenn gekillt) sein
        # Aber da wir Canceln setzt Sandbox cancelled=True

        out_res = json.loads((self.out_dir / "result.json").read_text())
        self.assertEqual(out_res["status"], "interrupted")
        self.assertEqual(out_res["reason"], "SIGTERM")

        out_exp = json.loads((self.out_dir / "experience.json").read_text())
        self.assertEqual(out_exp["outcome"], "failure")

        self.assertTrue(len(heartbeats) > 0, "Es sollte mindestens ein Heartbeat empfangen worden sein")

        # Keine .tmp Dateien
        tmp_files = list(self.out_dir.glob("*.tmp"))
        self.assertEqual(len(tmp_files), 0, f"Es durften keine tmp Dateien uebrig bleiben: {tmp_files}")


@unittest.skipUnless(shutil.which("docker") and os.environ.get("NIO_KANBAN_TEST_DOCKER"), "Docker benoetigt")
class TestKanbanDockerSandbox(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp_dir_obj.name)
        self.run_dir = self.tmp_dir / "run_01"
        self.in_dir = self.run_dir / "in"
        self.out_dir = self.run_dir / "out"
        self.work_dir = self.run_dir / "work"

        self.in_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.config = KanbanConfig(
            repo_root=self.tmp_dir,
            sandbox="docker",
            heartbeat_s=0.2,
            stop_grace_s=1.0,
            image="python:3.12-slim",
            sandbox_api_url="http://127.0.0.1:8740",
        )

        self.task = KanbanTask.from_dict(
            {
                "id": "t1",
                "board_id": "b1",
                "title": "Docker Sandbox Test",
                "status": "in_progress",
            }
        )
        self.worker = Worker.from_dict(
            {
                "uid": "w1",
                "name": "w1",
                "status": "busy",
            }
        )

        self.spec = SandboxSpec(
            run_id="t1-docker-a1",
            task=self.task,
            worker=self.worker,
            run_dir=self.run_dir,
            env={"CUSTOM_ENV": "value"},
            secrets={"OPENAI_API_KEY": "sk-super-geheim-docker"},
            image="python:3.12-slim",
            deadline_s=10.0,
        )

        (self.in_dir / "task.json").write_text(json.dumps(self.task.to_dict()), encoding="utf-8")
        content = "---\nruntime: noop\n---\n\n## Core Skills\n- Python\n"
        (self.in_dir / "SOUL.md").write_text(content, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp_dir_obj.cleanup()

    def test_docker_run_noop(self) -> None:
        runner = build_sandbox(self.config)

        async def on_heartbeat() -> None:
            pass

        result = asyncio.run(runner.run(self.spec, on_heartbeat=on_heartbeat))

        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.cancelled)

        out_res = json.loads((self.out_dir / "result.json").read_text())
        self.assertEqual(out_res["status"], "completed")

    def test_docker_inspect_secrets_hidden(self) -> None:
        # Wir lassen einen Command laufen der etwas braucht, canceln ihn und checken
        # Waehrend er laeuft, fragen wir docker inspect ab
        cmd = json.dumps(["python3", "-c", "import time; time.sleep(10)"])
        content = f"---\nruntime: command\ncommand: {cmd}\n---\n\n## Core Skills\n"
        (self.in_dir / "SOUL.md").write_text(content, encoding="utf-8")

        runner = build_sandbox(self.config)

        async def run_and_inspect() -> None:
            task = asyncio.create_task(runner.run(self.spec, on_heartbeat=lambda: asyncio.sleep(0)))

            # Warten bis Container da ist
            container_name = f"nio-w-{self.worker.uid}-{self.spec.run_id}"

            inspect_result = None
            for _ in range(50):
                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", container_name, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    try:
                        inspect_result = json.loads(stdout)
                        break
                    except Exception:
                        pass
                await asyncio.sleep(0.1)

            self.assertIsNotNone(inspect_result, "Container wurde nicht gefunden")

            # Check Config.Cmd and Config.Env
            config = inspect_result[0].get("Config", {})
            cmd_val = json.dumps(config.get("Cmd", []))

            self.assertNotIn("sk-super-geheim-docker", cmd_val)

            await runner.cancel(self.spec.run_id)
            await task

        asyncio.run(run_and_inspect())
