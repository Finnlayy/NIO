"""Trading-Limb: Nur das selbst gestartete Sigma gilt als Sigma.

Ein fremder Dienst auf dem Port darf weder als gesund gelten noch Backtests
beantworten, und ``trading.stop`` signalisiert nur einen Prozess, dessen PID,
Startzeit, Kommandozeile und Start-Nonce zum Startnachweis passen.

Kein Netz, kein echtes Sigma: Ein Stdlib-HTTP-Server spielt Sigmas Antworten
nach, ein Fake-``uvicorn``-Modul in der Sandbox laesst ``trading.start`` den
echten Startpfad durchlaufen.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from limbs.trading_limb import NONCE_ENV, SIGMA_VERSION, TradingLimb, _proc_start_ticks

from . import REPO_ROOT
from .test_trading_limb import fresh_intent

HEALTH = {"status": "ok", "kill_switch": False, "tv_worker_ok": True, "blueprint": {}}

FAKE_UVICORN = '''
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

port = int(sys.argv[sys.argv.index("--port") + 1])
version_file = Path(__file__).with_name("version.txt")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        routes = {
            "/api/v1/health": {"status": "ok", "kill_switch": False, "tv_worker_ok": True, "blueprint": {}},
            "/openapi.json": {"info": {"title": "Projekt:Sigma — fake", "version": version_file.read_text().strip()}},
            "/api/lake/summary": {"rows": 1},
        }
        body = json.dumps(routes.get(self.path, {})).encode()
        self.send_response(200 if self.path in routes else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _ForeignHandler(BaseHTTPRequestHandler):
    """Fremder Dienst, der sich Wort fuer Wort wie Sigma ausgibt."""

    seen: ClassVar[list[str]] = []

    def log_message(self, *args) -> None:
        pass

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self.seen.append(f"GET {self.path}")
        if self.path == "/openapi.json":
            self._send({"info": {"title": "Projekt:Sigma — fake", "version": SIGMA_VERSION}})
        else:
            self._send(HEALTH)

    def do_POST(self) -> None:
        self.seen.append(f"POST {self.path}")
        self._send({"pnl": 1_000_000})


class _SandboxCase(unittest.TestCase):
    SANDBOX = "workspace/.test-trading-identity"

    def setUp(self) -> None:
        self.limb = TradingLimb()
        self.root = REPO_ROOT / self.SANDBOX
        shutil.rmtree(self.root, ignore_errors=True)
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        (self.root / "logs").mkdir(parents=True)
        self.port = free_port()

    def run_op(self, operation: str, **params):
        return self.limb.execute(fresh_intent(operation, {"port": self.port, **params}, sandbox=self.SANDBOX))

    def spawn(self, *, env: dict[str, str] | None = None) -> subprocess.Popen:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            env={"PATH": os.environ.get("PATH", ""), **(env or {})},
            start_new_session=True,
        )
        self.addCleanup(self._reap, proc)
        return proc

    @staticmethod
    def _reap(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)

    def write_record(self, **record) -> None:
        (self.root / "logs" / "worker.json").write_text(json.dumps(record))


class ForeignServiceTests(_SandboxCase):
    def setUp(self) -> None:
        super().setUp()
        _ForeignHandler.seen = []
        server = ThreadingHTTPServer(("127.0.0.1", self.port), _ForeignHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        # "Installiert", damit ping und start den Port wirklich pruefen.
        (self.root / "venv" / "bin").mkdir(parents=True)
        (self.root / "venv" / "bin" / "python").symlink_to(sys.executable)

    def test_ping_does_not_treat_foreign_port_as_sigma(self) -> None:
        result = self.run_op("trading.ping")
        self.assertEqual(result.status, "success")
        self.assertFalse(result.output["running"])
        self.assertIsNone(result.output["health"])

    def test_status_and_backtest_fail_closed(self) -> None:
        for op in ("trading.status", "trading.backtest_run", "trading.lake_summary"):
            result = self.run_op(op)
            self.assertEqual(result.status, "failed", op)
            self.assertEqual(result.error["code"], "E_IO", op)
        self.assertNotIn("POST /api/backtest/run", _ForeignHandler.seen)

    def test_start_refuses_occupied_port(self) -> None:
        result = self.run_op("trading.start")
        self.assertEqual(result.status, "failed")
        self.assertIn("nicht verifizierten", result.error["message"])
        self.assertFalse((self.root / "logs" / "worker.json").exists())

    def test_forged_record_without_nonce_is_rejected(self) -> None:
        # Echter Prozess, echte Startzeit, echte argv -- aber ohne Start-Nonce.
        proc = self.spawn()
        time.sleep(0.2)
        argv = [sys.executable, "-c", "import time; time.sleep(60)"]
        self.write_record(pid=proc.pid, start_ticks=_proc_start_ticks(proc.pid), argv=argv,
                          port=self.port, nonce="x" * 32, version=SIGMA_VERSION)
        result = self.run_op("trading.ping")
        self.assertFalse(result.output["running"])
        self.assertIn("Nonce", result.output["unverified_reason"])


class StopFailClosedTests(_SandboxCase):
    ARGV: ClassVar[list[str]] = [sys.executable, "-c", "import time; time.sleep(60)"]

    def _record(self, proc: subprocess.Popen, **overrides) -> None:
        time.sleep(0.2)  # exec abwarten, sonst steht noch die Eltern-argv in /proc
        record = {"pid": proc.pid, "start_ticks": _proc_start_ticks(proc.pid), "argv": self.ARGV,
                  "port": self.port, "nonce": "n" * 32, "version": SIGMA_VERSION}
        record.update(overrides)
        self.write_record(**record)

    def assertAlive(self, proc: subprocess.Popen) -> None:
        time.sleep(0.2)
        self.assertIsNone(proc.poll(), "fremder Prozess wurde signalisiert")

    def test_legacy_pid_file_is_never_signalled(self) -> None:
        proc = self.spawn()
        (self.root / "logs" / "worker.pid").write_text(str(proc.pid))
        result = self.run_op("trading.stop")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "E_POLICY_DENIED")
        self.assertAlive(proc)

    def test_wrong_start_time_is_not_signalled(self) -> None:
        proc = self.spawn(env={NONCE_ENV: "n" * 32})
        self._record(proc, start_ticks=1)
        result = self.run_op("trading.stop")
        self.assertEqual(result.error["code"], "E_POLICY_DENIED")
        self.assertIn("Startzeit", result.error["message"])
        self.assertAlive(proc)

    def test_wrong_cmdline_is_not_signalled(self) -> None:
        proc = self.spawn(env={NONCE_ENV: "n" * 32})
        self._record(proc, argv=["/usr/bin/sigma", "--fake"])
        result = self.run_op("trading.stop")
        self.assertEqual(result.error["code"], "E_POLICY_DENIED")
        self.assertAlive(proc)

    def test_missing_nonce_is_not_signalled(self) -> None:
        proc = self.spawn()
        self._record(proc)
        result = self.run_op("trading.stop")
        self.assertEqual(result.error["code"], "E_POLICY_DENIED")
        self.assertAlive(proc)

    def test_matching_process_is_stopped(self) -> None:
        proc = self.spawn(env={NONCE_ENV: "n" * 32})
        self._record(proc)
        result = self.run_op("trading.stop")
        self.assertEqual(result.status, "success", result.error)
        self.assertTrue(result.output["stopped"])
        proc.wait(timeout=10)
        self.assertFalse((self.root / "logs" / "worker.json").exists())

    def test_dead_process_only_clears_record(self) -> None:
        proc = self.spawn(env={NONCE_ENV: "n" * 32})
        self._record(proc)
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)
        result = self.run_op("trading.stop")
        self.assertEqual(result.status, "success")
        self.assertFalse(result.output["stopped"])
        self.assertFalse((self.root / "logs" / "worker.json").exists())


class OwnWorkerLifecycleTests(_SandboxCase):
    """trading.start -> ping -> status -> stop gegen ein Fake-Sigma im echten Startpfad."""

    def setUp(self) -> None:
        super().setUp()
        install = self.root / "sigma"
        install.mkdir()
        (install / "uvicorn.py").write_text(FAKE_UVICORN)
        (install / "version.txt").write_text(SIGMA_VERSION)
        (self.root / "venv" / "bin").mkdir(parents=True)
        (self.root / "venv" / "bin" / "python").symlink_to(sys.executable)
        self.addCleanup(self._stop_quietly)

    def _stop_quietly(self) -> None:
        record = self.root / "logs" / "worker.json"
        if record.exists():
            pid = json.loads(record.read_text())["pid"]
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_lifecycle(self) -> None:
        started = self.run_op("trading.start")
        self.assertEqual(started.status, "success", started.error)
        self.assertTrue(started.output["started"])
        pid = started.output["pid"]

        record = json.loads((self.root / "logs" / "worker.json").read_text())
        self.assertEqual(record["pid"], pid)
        self.assertEqual(record["port"], self.port)
        self.assertEqual(len(record["nonce"]), 32)

        ping = self.run_op("trading.ping")
        self.assertTrue(ping.output["running"])
        self.assertEqual(ping.output["health"]["identity"]["pid"], pid)

        again = self.run_op("trading.start")
        self.assertTrue(again.output["already_running"])

        status = self.run_op("trading.status")
        self.assertEqual(status.status, "success", status.error)
        self.assertEqual(status.output["lake"], {"rows": 1})

        # Falsche Version -> nicht mehr Sigma, auch wenn es unser Prozess ist.
        (self.root / "sigma" / "version.txt").write_text("sigma-other-9")
        self.assertFalse(self.run_op("trading.ping").output["running"])

        stopped = self.run_op("trading.stop")
        self.assertEqual(stopped.status, "success", stopped.error)
        self.assertTrue(stopped.output["stopped"])
        deadline = time.time() + 5
        while time.time() < deadline and _proc_start_ticks(pid) is not None:
            time.sleep(0.1)
        self.assertIsNone(_proc_start_ticks(pid))


if __name__ == "__main__":
    unittest.main()
