"""Not-Aus, Prozessgruppen und Umgebung der Limbs, mit echten Prozessen."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from core.config import NeuConfig
from core.protocol import ErrorCode, ProtocolError
from limbs.base import LimbError
from orchestrator.cli import main as neu_main
from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.dispatcher import Dispatcher
from orchestrator.runner import LimbRegistry, Orchestrator, _parse_env_allow

from . import REPO_ROOT
from .test_agent_base import DemoAgent, FakeContext

# Startet einen Kindprozess, schreibt dessen PID und schlaeft. Beide ignorieren nichts.
PARENT_WITH_CHILD = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
print(child.pid, flush=True)
open(sys.argv[1], "w").write(str(child.pid))
time.sleep(30)
"""
# Dieser Kindprozess ignoriert SIGTERM und muss trotzdem verschwinden.
STUBBORN_CHILD = """
import subprocess, sys, time
code = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
child = subprocess.Popen([sys.executable, "-c", code])
time.sleep(0.5)
open(sys.argv[1], "w").write(str(child.pid))
time.sleep(30)
"""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    if not stat.exists():
        return True
    try:
        text = stat.read_text()
    except OSError:  # Zwischen kill und read beendet
        return False
    return text.rsplit(")", 1)[1].split()[0] != "Z"


class StopCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="neu-stop-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.config = NeuConfig.load(REPO_ROOT, runtime_dir=self.tmp / "runtime", workspace_dir=self.tmp / "workspace")
        self.config.ensure_dirs()
        self.stop_file = self.config.runtime_dir / "STOP"
        self.orch = Orchestrator(self.config, quiet=True)

    def intent(self, **kwargs):
        base = {"goal": "Not-Aus", "operation": "sys.ping", "params": {}, "limb": "echo"}
        base.update(kwargs)
        return self.orch.kernel.build_intent(**base)

    def sleeper(self):
        return self.intent(operation="sys.simulate", params={"mode": "timeout", "seconds": 20})

    def wait_for_pid(self, path: Path) -> int:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if path.is_file() and path.read_text():
                return int(path.read_text())
            time.sleep(0.05)
        self.fail("Kindprozess hat sich nicht gemeldet")

    def assertGone(self, pid: int) -> None:
        deadline = time.monotonic() + 5
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(alive(pid), f"Prozess {pid} lebt noch")


class TestNeueLaeufe(StopCase):
    def test_dispatch_wird_abgelehnt_und_kein_limb_startet(self):
        self.stop_file.touch()
        with mock.patch("subprocess.Popen") as popen:
            attempt = self.orch.dispatch(self.intent())
        popen.assert_not_called()
        self.assertEqual(attempt.result.error["code"], ErrorCode.STOPPED)

    def test_spawn_async_wird_abgelehnt(self):
        self.stop_file.touch()
        outcome = self.orch.spawn_async(self.intent())
        self.assertEqual(outcome.result.error["code"], ErrorCode.STOPPED)

    def test_inbox_bleibt_liegen_bis_zum_resume(self):
        intent = self.intent()
        pending = self.orch.transport.inbox_dir("echo") / "auftrag.json"
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(intent.to_json(), encoding="utf-8")
        self.stop_file.touch()
        self.assertEqual(self.orch.run_inbox_once(), [])
        self.assertTrue(pending.exists())

        self.stop_file.unlink()
        attempts = self.orch.run_inbox_once()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].result.status, "success")

    def test_dispatcher_nimmt_nichts_und_bricht_laufende_ab(self):
        stop_file = self.tmp / "STOP"
        stop_file.touch()
        store = mock.AsyncMock()
        dispatcher = Dispatcher.__new__(Dispatcher)
        dispatcher.config = KanbanConfig(stop_file=stop_file)
        dispatcher.store = store
        dispatcher._active = {"task-1": mock.Mock()}
        dispatcher.cancel = mock.AsyncMock()
        report = asyncio.run(dispatcher.tick())
        self.assertEqual((report.assigned, report.spawned), (0, 0))
        store.list_tasks.assert_not_called()
        dispatcher.cancel.assert_awaited_once_with("task-1")


class TestLaufendeLaeufe(StopCase):
    def test_synchroner_lauf_endet_in_fuenf_sekunden(self):
        timer = threading.Timer(0.5, self.stop_file.touch)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        attempt = self.orch.dispatch(self.sleeper())
        self.assertLess(time.monotonic() - started, 5.5)
        self.assertEqual(attempt.result.error["code"], ErrorCode.STOPPED)

    def test_ueberwachter_lauf_endet_in_fuenf_sekunden(self):
        intent = self.sleeper()
        handle = self.orch.spawn_async(intent)
        timer = threading.Timer(0.5, self.stop_file.touch)
        timer.start()
        self.addCleanup(timer.cancel)
        started = time.monotonic()
        attempt, _ = self.orch._supervise(handle, job_id=intent.job_id)
        self.assertLess(time.monotonic() - started, 5.5)
        self.assertEqual(attempt.result.error["code"], ErrorCode.STOPPED)
        self.assertGone(handle.pid)


class TestProzessgruppe(StopCase):
    def run_child(self, script: str, *, timeout: float | None = None):
        pid_file = self.tmp / "kind.pid"
        result: dict[str, object] = {}

        def run() -> None:
            result["out"] = self.orch._run_child([sys.executable, "-c", script, str(pid_file)], {"PATH": os.environ["PATH"]}, timeout)

        worker = threading.Thread(target=run)
        worker.start()
        child = self.wait_for_pid(pid_file)
        return child, worker, result

    def test_timeout_trifft_auch_kindprozesse(self):
        child, worker, result = self.run_child(PARENT_WITH_CHILD, timeout=1.0)
        worker.join(10)
        self.assertEqual(result["out"][3], "timeout")
        self.assertGone(child)

    def test_stop_trifft_auch_kindprozesse(self):
        child, worker, result = self.run_child(PARENT_WITH_CHILD)
        self.stop_file.touch()
        worker.join(10)
        self.assertEqual(result["out"][3], "stop")
        self.assertGone(child)

    def test_kind_das_sigterm_ignoriert_stirbt_trotzdem(self):
        child, worker, result = self.run_child(STUBBORN_CHILD)
        self.stop_file.touch()
        worker.join(10)
        self.assertEqual(result["out"][3], "stop")
        self.assertGone(child)


class TestUmgebung(StopCase):
    def env_for(self, limb: str) -> dict[str, str]:
        return self.orch._limb_env(self.orch.registry.get(limb))

    def test_geheimnisse_bleiben_draussen(self):
        secrets = {"KRAKEN_API_KEY": "x", "NIO_APPROVAL_KEY": "x", "NIO_KANBAN_API_TOKEN": "x", "FREELLMAPI_KEY": "x"}
        with mock.patch.dict(os.environ, secrets):
            env = self.env_for("echo")
        self.assertFalse(set(secrets) & set(env))

    def test_nur_die_erlaubten_namen_kommen_durch(self):
        with mock.patch.dict(os.environ, {"NIO_OBSIDIAN_VAULT": "/v", "STT_MODEL": "m"}):
            env = self.env_for("vault")
        self.assertEqual(env["NIO_OBSIDIAN_VAULT"], "/v")
        self.assertNotIn("STT_MODEL", env)

    def test_home_und_tmpdir_liegen_in_der_sandbox(self):
        env = self.env_for("echo")
        self.assertEqual(env["HOME"], env["TMPDIR"])
        self.assertTrue(Path(env["HOME"]).is_dir())
        self.assertTrue(Path(env["HOME"]).is_relative_to(self.config.workspace_dir))

    def test_jeder_limb_hat_eine_liste(self):
        raw = json.loads((REPO_ROOT / "limbs" / "registry.json").read_text(encoding="utf-8"))
        for name, body in raw["limbs"].items():
            self.assertIn("env_allow", body, name)
        self.assertIsNotNone(LimbRegistry(self.config).get("openmanus"))

    def test_geheimnisse_in_env_allow_scheitern_beim_laden(self):
        for bad in (["KRAKEN_API_KEY"], ["NIO_APPROVAL_KEY"], ["A_TOKEN"], ["MY_SECRET"], ["DB_PASSWORD"], ["klein"], "PATH"):
            with self.subTest(bad=bad), self.assertRaises(ProtocolError):
                _parse_env_allow("demo", bad)
        self.assertEqual(_parse_env_allow("demo", ["FREELLMAPI_KEY", "STT_MODEL"]), ("FREELLMAPI_KEY", "STT_MODEL"))


class TestCli(StopCase):
    def test_stop_und_resume(self):
        self.assertEqual(neu_main(["--runtime-dir", str(self.config.runtime_dir), "stop"]), 0)
        self.assertTrue(self.stop_file.exists())
        self.assertEqual(neu_main(["--runtime-dir", str(self.config.runtime_dir), "resume"]), 0)
        self.assertFalse(self.stop_file.exists())
        self.assertEqual(neu_main(["--runtime-dir", str(self.config.runtime_dir), "resume"]), 0)


class TestAgentLaeufe(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.runtime = Path(self._tmp.name)
        self.limb = DemoAgent.__new__(DemoAgent)
        self.limb.script = []
        self.limb.halted = 0
        self.limb.halt_error = None
        self.limb.config = NeuConfig.load(REPO_ROOT, runtime_dir=self.runtime)
        self.ctx = FakeContext()

    def test_start_wird_abgelehnt(self):
        (self.runtime / "STOP").touch()
        with self.assertRaises(LimbError) as ctx:
            self.limb._start({}, self.ctx)
        self.assertEqual(ctx.exception.code, ErrorCode.STOPPED)

    def test_status_beendet_den_lauf(self):
        run = self.limb._start({}, self.ctx)
        (self.runtime / "STOP").touch()
        view = self.limb._status({"run_id": run["run_id"]}, self.ctx)
        self.assertEqual(view["state"], "stopped")
        self.assertEqual(self.limb.halted, 1)


if __name__ == "__main__":
    unittest.main()
