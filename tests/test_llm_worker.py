"""Real worker subprocesses against local fixtures, NOT external provider evidence."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import KanbanTask, Worker
from orchestrator.kanban.sandbox import LLMRequestSandbox, SandboxSpec, SubprocessSandbox


class LLMWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = KanbanConfig(repo_root=self.root, sandbox="llm-http", heartbeat_s=0.05, stop_grace_s=0.1)
        for name in ("in", "out", "work"):
            (self.root / name).mkdir()
        self.task = KanbanTask(id="test-task", board_id="test-board", title="Reply with OK")
        self.worker = Worker(uid="llm-test", name="LLM test", soul_md="---\nruntime: llm\n---\nAnswer concisely.")
        (self.root / "in/task.json").write_text(json.dumps(self.task.to_dict()))
        (self.root / "in/SOUL.md").write_text(self.worker.soul_md)

    async def asyncTearDown(self) -> None:
        self.tmp.cleanup()

    def spec(self, secrets: dict[str, str]) -> SandboxSpec:
        return SandboxSpec(run_id="test-run", task=self.task, worker=self.worker, run_dir=self.root,
                           env={}, secrets=secrets, image="", deadline_s=5)

    async def run_child(self, secrets: dict[str, str]) -> tuple[int | None, dict]:
        async def heartbeat() -> None:
            pass

        result = await LLMRequestSandbox(self.config).run(self.spec(secrets), on_heartbeat=heartbeat)
        return result.exit_code, json.loads((self.root / "out/result.json").read_text())

    async def test_real_child_reports_missing_secret_not_completion(self) -> None:
        code, result = await self.run_child({"NIO_LLM_ERROR": "missing_secret"})
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "missing_secret")
        self.assertEqual(result["result_payload"], {})

    async def test_http_transport_and_child_both_refuse_command_runtime(self) -> None:
        self.worker.soul_md = '---\nruntime: command\ncommand: ["/usr/bin/true"]\n---'
        with self.assertRaisesRegex(ValueError, "only|nur"):
            LLMRequestSandbox(self.config)._prepare(self.spec({}))
        self.worker.soul_md = "---\nruntime: llm\n---"
        # Tampered input must still be refused inside the child.
        (self.root / "in/SOUL.md").write_text('---\nruntime: command\ncommand: ["/usr/bin/true"]\n---')
        code, result = await self.run_child({})
        self.assertEqual(code, 1)
        self.assertEqual(result["reason"], "llm_transport_refuses_non_llm_runtime")
        with self.assertRaisesRegex(ValueError, "noop"):
            SubprocessSandbox(replace(self.config, sandbox="subprocess"))._prepare(self.spec({}))

    async def _http_case(self, http_status: int) -> tuple[int | None, dict, list]:
        requests: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                pass

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append({"body": body, "auth": self.headers.get("Authorization")})
                self.send_response(http_status)
                if http_status == 302:
                    self.send_header("Location", "http://127.0.0.1:1/must-not-follow")
                self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": "OK worker-fixture-credential"}}]}).encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            code, result = await self.run_child({"NIO_LLM_PROVIDER": "freellm", "NIO_LLM_API_KEY": "worker-fixture-credential",
                                                 "NIO_LLM_MODEL": "fixture-model", "NIO_LLM_PROTOCOL": "openai",
                                                 "NIO_LLM_ENDPOINT": f"http://127.0.0.1:{server.server_port}/v1/chat/completions"})
            return code, result, requests
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    async def test_real_http_child_uses_only_one_small_request_and_redacts_output(self) -> None:
        code, result, requests = await self._http_case(200)
        self.assertEqual(code, 0)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["auth"], "Bearer worker-fixture-credential")
        self.assertEqual(requests[0]["body"]["max_tokens"], 64)
        self.assertEqual(result["result_payload"]["text"], "OK [REDACTED]")

    async def test_auth_failure_and_redirect_never_fall_back_or_retry(self) -> None:
        for http_status in (401, 302):
            code, result, requests = await self._http_case(http_status)
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "failed")
            self.assertIn(f"HTTP {http_status}", result["reason"])
            self.assertEqual(len(requests), 1)
            self.assertNotIn("worker-fixture-credential", json.dumps(result))
