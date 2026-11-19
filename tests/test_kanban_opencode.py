"""Tests fuer den OpenCode-Runtime (ADR-001 Phase 3).

Getestet werden ``worker_entry._run_opencode`` (Aufruf, Zeitlimit, strukturierte Ausgabe),
``DockerSandbox.build_argv`` fuer das Netz des OpenCode-Workers, die Konfiguration unter
``config/opencode/opencode.json`` und die Routen des Modell-Relays. Bestehende Tests fuer die
Sandbox liegen in ``test_kanban_sandbox.py``; OpenCode war dort bisher nicht abgedeckt.

Keine Netz- und Dienstzugriffe: OpenCode wird durch ein Fake-Skript ersetzt, das ueber
``NIO_KANBAN_OPENCODE_BIN`` eingehaengt wird. Jeder Lauf nutzt ein eigenes temporaeres Verzeichnis.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.models import KanbanTask, Worker
from orchestrator.kanban.sandbox import DockerSandbox, SandboxSpec
from orchestrator.kanban.worker_entry import (
    _opencode_env,
    _parse_opencode_events,
    _run_opencode,
)

REPO = Path(__file__).resolve().parent.parent
OPENCODE_CONFIG = REPO / "config" / "opencode" / "opencode.json"
GIT_ID = ["-c", "user.name=test", "-c", "user.email=test@nio.invalid"]

_FAKE_TEMPLATE = """#!/usr/bin/env python3
import json, subprocess, sys, time
MODE = {mode!r}
print(json.dumps({{"type": "step_start", "part": {{"type": "step-start"}}}}), flush=True)
if MODE == "commit":
    print(json.dumps({{"type": "text", "part": {{"type": "text", "text": "Datei geaendert"}}}}), flush=True)
    print(json.dumps({{"type": "tool_use", "part": {{"type": "tool", "tool": "write", "state": {{"status": "completed"}}}}}}), flush=True)
    with open("aenderung.txt", "w", encoding="utf-8") as handle:
        handle.write("ok\\n")
    subprocess.run(["git", "add", "aenderung.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "Testaufgabe"], check=True)
elif MODE == "sleep":
    time.sleep(30)
elif MODE == "exit3":
    sys.stderr.write("fehler\\n")
    sys.exit(3)
"""


def _fake_opencode(directory: Path, mode: str) -> Path:
    script = directory / f"fake-opencode-{mode}"
    script.write_text(_FAKE_TEMPLATE.format(mode=mode), encoding="utf-8")
    script.chmod(0o755)
    return script


def _git_repo(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", *GIT_ID, "init", "-q"], cwd=directory, check=True)
    (directory / "README.md").write_text("start\n", encoding="utf-8")
    subprocess.run(["git", *GIT_ID, "add", "README.md"], cwd=directory, check=True)
    subprocess.run(["git", *GIT_ID, "commit", "-q", "-m", "init"], cwd=directory, check=True)


class TestRunOpencode(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)
        self.work = self.tmp / "work"
        _git_repo(self.work)
        self.patch = mock.patch.dict(
            os.environ,
            {
                "NIO_KANBAN_OPENCODE_HOME": str(self.tmp / "home"),
                "NIO_KANBAN_OPENCODE_TIMEOUT_S": "20",
            },
        )
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.tmp_obj.cleanup()

    def _run(self, mode: str | None, workdir: Path | None = None) -> tuple[str, str, dict]:
        if mode is not None:
            os.environ["NIO_KANBAN_OPENCODE_BIN"] = str(_fake_opencode(self.tmp, mode))
        return _run_opencode("Mission", {"title": "T", "description": "D"}, workdir or self.work)

    def test_commit_lauf_ist_strukturiert_und_committet(self) -> None:
        status, reason, payload = self._run("commit")
        self.assertEqual((status, reason), ("completed", ""))
        self.assertEqual(payload["exit_code"], 0)
        self.assertFalse(payload["timed_out"])
        self.assertTrue(payload["committed"])
        self.assertNotEqual(payload["head_before"], payload["head_after"])
        self.assertEqual(payload["text"], "Datei geaendert")
        self.assertEqual(payload["tools"], [{"tool": "write", "status": "completed"}])
        self.assertEqual(payload["events"], 3)
        log = subprocess.run(
            ["git", "log", "--format=%an <%ae>", "-1"], cwd=self.work, capture_output=True, text=True, check=True
        )
        self.assertEqual(log.stdout.strip(), "nio-opencode <opencode@nio.invalid>")

    def test_zeitlimit_beendet_haengenden_lauf(self) -> None:
        os.environ["NIO_KANBAN_OPENCODE_TIMEOUT_S"] = "1"
        started = time.monotonic()
        status, reason, payload = self._run("sleep")
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual((status, reason), ("failed", "opencode_timeout"))
        self.assertTrue(payload["timed_out"])
        self.assertFalse(payload["committed"])

    def test_exitcode_und_stderr_werden_gemeldet(self) -> None:
        status, reason, payload = self._run("exit3")
        self.assertEqual((status, reason), ("failed", "opencode_exit_3"))
        self.assertEqual(payload["exit_code"], 3)
        self.assertIn("fehler", payload["stderr_tail"])

    def test_ohne_git_repo_startet_nichts(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        status, reason, payload = self._run("commit", workdir=plain)
        self.assertEqual((status, reason), ("failed", "workdir_not_git_repo"))
        self.assertFalse((plain / "aenderung.txt").exists())
        self.assertFalse(payload["committed"])

    def test_fehlendes_binary_wird_gemeldet(self) -> None:
        os.environ["NIO_KANBAN_OPENCODE_BIN"] = str(self.tmp / "gibt-es-nicht")
        status, reason, _ = _run_opencode("Mission", {}, self.work)
        self.assertEqual((status, reason), ("failed", "opencode_not_found"))


class TestOpencodeEnv(unittest.TestCase):
    def test_nur_benannte_secrets_gehen_durch(self) -> None:
        with mock.patch.dict(os.environ, {"FREELLMAPI_KEY": "k-test", "OPENAI_API_KEY": "sk-geheim"}):
            env = _opencode_env()
        self.assertEqual(env["FREELLMAPI_KEY"], "k-test")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("sk-geheim", json.dumps(env))
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")

    def test_konfiguration_zeigt_auf_container_pfad(self) -> None:
        with mock.patch.dict(os.environ, {}):
            os.environ.pop("NIO_KANBAN_OPENCODE_CONFIG", None)
            self.assertEqual(_opencode_env()["OPENCODE_CONFIG"], "/nio/opencode/opencode.json")


class TestParseEvents(unittest.TestCase):
    def test_zaehlt_text_und_werkzeuge_und_ignoriert_muell(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"type": "step_start", "part": {}}),
                "keine json zeile",
                json.dumps({"type": "text", "part": {"text": "eins"}}),
                json.dumps({"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error"}}}),
                json.dumps(["kein", "objekt"]),
            ]
        )
        events, texts, tools = _parse_opencode_events(stdout)
        self.assertEqual(events, 3)
        self.assertEqual(texts, ["eins"])
        self.assertEqual(tools, [{"tool": "bash", "status": "error"}])


class TestOpencodeConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = OPENCODE_CONFIG.read_text(encoding="utf-8")
        self.cfg = json.loads(self.raw)

    def test_provider_zeigen_nur_auf_den_relay(self) -> None:
        for name, provider in self.cfg["provider"].items():
            with self.subTest(provider=name):
                self.assertTrue(provider["options"]["baseURL"].startswith("http://nio-model-relay:"))

    def test_keine_literalen_keys(self) -> None:
        self.assertEqual(self.cfg["provider"]["freellmapi"]["options"]["apiKey"], "{env:FREELLMAPI_KEY}")
        self.assertEqual(self.cfg["provider"]["ollama"]["options"]["apiKey"], "ollama")
        self.assertNotIn("sk-", self.raw)

    def test_push_env_und_runtime_sind_gesperrt(self) -> None:
        perm = self.cfg["permission"]
        self.assertEqual(perm["bash"]["*"], "deny")
        self.assertEqual(perm["bash"]["git push*"], "deny")
        self.assertEqual(perm["edit"]["**/.env"], "deny")
        self.assertEqual(perm["read"]["**/.env.*"], "deny")
        self.assertEqual(perm["edit"]["runtime/**"], "deny")
        self.assertEqual(perm["read"]["runtime/**"], "deny")

    def test_vault_mcp_ist_eingebunden(self) -> None:
        self.assertEqual(self.cfg["mcp"]["vault"]["command"], ["python3", "/nio/mcp/scripts/vault_mcp.py"])


class TestOpencodeSandboxArgv(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_obj.name)
        self.config = KanbanConfig(repo_root=REPO, workspace_dir=self.tmp, sandbox="docker")

    def tearDown(self) -> None:
        self.tmp_obj.cleanup()

    def _spec(self, runtime: str) -> SandboxSpec:
        worker = Worker.from_dict(
            {"uid": "w1", "name": "w1", "status": "busy", "soul_md": f"---\nruntime: {runtime}\n---\n"}
        )
        task = KanbanTask.from_dict({"id": "t1", "board_id": "b1", "title": "T", "status": "in_progress"})
        return SandboxSpec(
            run_id="t1-a1",
            task=task,
            worker=worker,
            run_dir=self.tmp,
            env={},
            secrets={"FREELLMAPI_KEY": "k-geheim"},
            image="python:3.12-slim",
            deadline_s=60.0,
        )

    @staticmethod
    def _network(argv: list[str]) -> str:
        return argv[argv.index("--network") + 1]

    def test_opencode_nutzt_internes_netz_ohne_host_gateway(self) -> None:
        argv = DockerSandbox.build_argv(self._spec("opencode"), self.config)
        self.assertEqual(self._network(argv), "nio-opencode-model")
        self.assertNotIn("host.docker.internal:host-gateway", argv)
        self.assertIn("nio-opencode-worker:latest", argv)
        self.assertNotIn("python:3.12-slim", argv)
        joined = " ".join(argv)
        self.assertIn(f"{OPENCODE_CONFIG}:/nio/opencode/opencode.json:ro", joined)
        self.assertIn("/nio/mcp/scripts/vault_mcp.py:ro", joined)
        self.assertNotIn("k-geheim", joined)

    def test_noop_llm_und_command_bleiben_bei_none(self) -> None:
        for runtime in ("noop", "llm", "command"):
            with self.subTest(runtime=runtime):
                argv = DockerSandbox.build_argv(self._spec(runtime), self.config)
                self.assertEqual(self._network(argv), "none")
                self.assertNotIn("nio-opencode-worker:latest", argv)

    def test_opencode_verweigert_offene_netze(self) -> None:
        for network in ("none", "host", "bridge", ""):
            with self.subTest(network=network):
                cfg = KanbanConfig(repo_root=REPO, workspace_dir=self.tmp, opencode_network=network)
                with self.assertRaises(ValueError):
                    DockerSandbox.build_argv(self._spec("opencode"), cfg)


class TestModelRelayRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("relay", REPO / "docker" / "model-relay" / "relay.py")
        assert spec is not None and spec.loader is not None
        cls.relay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.relay)

    def test_nur_feste_ziele(self) -> None:
        routes = self.relay.parse_routes("3001=host.docker.internal:3001, 11434=host.docker.internal:11434")
        self.assertEqual(
            routes,
            [(3001, ("host.docker.internal", 3001)), (11434, ("host.docker.internal", 11434))],
        )

    def test_leer_oder_kaputt_bricht_ab(self) -> None:
        for raw in ("", "abc=host:1", "3001=kein-port", "3001=:3001"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.relay.parse_routes(raw)


if __name__ == "__main__":
    unittest.main()
