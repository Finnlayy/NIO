"""Trading-Limb: Vertrags-, Isolations- und Proxy-Tests.

Der Limb ist ein *Adapter*: Er besitzt keine Handelslogik. Sigma
(https://github.com/Finnlayy/Sigma) bleibt der Vertrag -- mit seiner eigenen,
deterministischen Suite. Was hier bewacht wird, ist deshalb genau die Naht:

1. **Protokolltreue.** Jeder Handler ist in ``protocol/operations.json``
   deklariert, heisst gemaess ``^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$`` und steht
   im Register -- sonst startet der Orchestrator einen Limb, den er nicht kennt.
2. **Sandbox-Isolation.** ``HOME``, ``TMPDIR``, ``XDG_CACHE_HOME`` und
   ``SIGMA_DATA_DIR`` zeigen in die eigene Sandbox. Ein Lauf darf das
   Host-Home nicht anfassen; Sigma schreibt sonst in echtes ``~/.cache``.
3. **Fail-closed statt Fantasie.** Ist der Worker tot, gibt es ``E_IO`` mit
   Hinweis -- keine erfundenen Zahlen. Unbekannte Ports werden abgewiesen.
4. **Nur dokumentierte Felder.** ``trading.backtest_run`` reicht ausschliesslich
   die deklarierten Parameter an Sigma weiter.

Die Tests brauchen **kein Netz und keinen laufenden Worker**: Sie pruefen den
Adapter, nicht Sigma. Der End-to-End-Lauf (install -> start -> backtest) ist
bewusst kein Unit-Test; er dauert ~35 s und haengt am Netz.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from core.config import NeuConfig
from core.protocol import Intent, Operations
from limbs.trading_limb import (
    DEFAULT_PORT,
    INSTALL_MARKER,
    SIGMA_REF,
    SIGMA_REPOSITORY,
    Layout,
    TradingLimb,
)

from . import REPO_ROOT

REGISTRY_PATH = REPO_ROOT / "limbs" / "registry.json"
OPERATIONS_PATH = REPO_ROOT / "protocol" / "operations.json"
LIMB_SCRIPT = REPO_ROOT / "limbs" / "trading_limb.py"
INTENT_EXAMPLE = REPO_ROOT / "protocol" / "examples" / "intent.sys_echo.json"

#: Das Protokoll erlaubt genau einen Punkt -- 'trading.lake.summary' ist ungueltig.
OP_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def fresh_intent(
    operation: str,
    params: dict | None = None,
    *,
    seconds: int = 60,
    sandbox: str = "workspace",
) -> Intent:
    """Beispiel-Intent mit *frischen* Timern -- das Fixture ist auf 2026-09-03 datiert.

    Ein abgelaufener Timer macht das Result ungueltig (negatives remaining_ms);
    das ist korrektes Protokollverhalten, aber kein sinnvoller Testfall.
    """
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"  # noqa: E731
    payload = json.loads(INTENT_EXAMPLE.read_text(encoding="utf-8"))
    payload["target"]["limb"] = "trading"
    payload["task"]["operation"] = operation
    payload["task"]["params"] = params or {}
    payload["constraints"]["sandbox_root"] = sandbox
    payload["created_at"] = iso(now)
    payload["timer"]["deadline_s"] = float(seconds)
    payload["timer"]["soft_deadline_s"] = float(max(1, seconds - 10))
    payload["timer"]["armed_at"] = iso(now)
    payload["timer"]["soft_expires_at"] = iso(now + dt.timedelta(seconds=max(1, seconds - 10)))
    payload["timer"]["expires_at"] = iso(now + dt.timedelta(seconds=seconds))
    return Intent.from_dict(payload)


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_operations() -> dict:
    return json.loads(OPERATIONS_PATH.read_text(encoding="utf-8"))["operations"]


class TradingLimbContractTests(unittest.TestCase):
    """Der Limb muss ohne laufenden Worker importierbar und pruefbar sein."""

    def setUp(self) -> None:
        self.limb = TradingLimb()

    def test_identity(self) -> None:
        self.assertEqual(self.limb.name, "trading")
        self.assertTrue(self.limb.version)

    def test_every_handler_matches_protocol_pattern(self) -> None:
        for operation in self.limb.handlers():
            self.assertRegex(operation, OP_PATTERN, f"ungueltiger Operationsname: {operation}")

    def test_every_handler_is_declared(self) -> None:
        declared = load_operations()
        missing = sorted(set(self.limb.handlers()) - set(declared))
        self.assertEqual(missing, [], "Handler ohne Eintrag in protocol/operations.json")

    def test_declared_operations_are_implemented(self) -> None:
        declared = load_operations()
        claimed = {name for name, spec in declared.items() if "trading" in spec.get("implemented_by", [])}
        missing = sorted(claimed - set(self.limb.handlers()))
        self.assertEqual(missing, [], "operations.json verspricht Operationen, die fehlen")

    def test_registry_lists_exactly_the_handlers(self) -> None:
        entry = load_registry()["limbs"]["trading"]
        self.assertEqual(sorted(entry["operations"]), sorted(self.limb.handlers()))

    def test_registry_entry_points_at_this_script(self) -> None:
        entry = load_registry()["limbs"]["trading"]
        self.assertEqual(entry["entrypoint"], "limbs/trading_limb.py")
        self.assertTrue(LIMB_SCRIPT.is_file())

    def test_operations_are_declared_read_or_write(self) -> None:
        declared = load_operations()
        for operation in self.limb.handlers():
            spec = declared[operation]
            self.assertIn(spec["risk"], {"none", "read", "write", "destructive", "high"})
            self.assertIn("phase", spec)
            self.assertTrue(spec.get("description"))


class TradingSandboxIsolationTests(unittest.TestCase):
    """Sigma darf nur in die Sandbox schreiben -- nie ins Host-Home."""

    def setUp(self) -> None:
        self.limb = TradingLimb()
        self.config = NeuConfig.load()
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.layout = Layout(
            install=root / "sigma",
            venv=root / "venv",
            data=root / "data",
            logs=root / "logs",
            tmp=root / "tmp",
            home=root / "home",
            cache=root / "cache",
        )

    def test_env_redirects_every_home_like_variable(self) -> None:
        env = self.limb._env(self.layout, DEFAULT_PORT)
        expected = {
            "HOME": self.layout.home,
            "TMPDIR": self.layout.tmp,
            "XDG_CACHE_HOME": self.layout.cache,
            "SIGMA_DATA_DIR": self.layout.data,
        }
        for key, path in expected.items():
            self.assertIn(key, env, f"{key} fehlt -- Sigma wuerde ins Host-Home schreiben")
            self.assertEqual(Path(env[key]), path)
        self.assertNotEqual(Path(env["HOME"]), Path.home())

    def test_env_keeps_python_deterministic(self) -> None:
        env = self.limb._env(self.layout, DEFAULT_PORT)
        self.assertEqual(env["PYTHONUNBUFFERED"], "1")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_pid_file_and_marker_live_in_the_sandbox(self) -> None:
        self.assertEqual(self.layout.marker, self.layout.install / INSTALL_MARKER)
        self.assertEqual(self.layout.pid_file.parent, self.layout.logs)
        self.assertEqual(self.layout.log.parent, self.layout.logs)

    def test_pinned_ref_is_a_full_sha(self) -> None:
        self.assertRegex(SIGMA_REF, r"^[0-9a-f]{40}$", "ohne vollen Pin ist die Suite nicht der Vertrag")

    def test_repository_is_the_sigma_remote(self) -> None:
        self.assertTrue(SIGMA_REPOSITORY.endswith("/Sigma.git"))


class TradingFailClosedTests(unittest.TestCase):
    """Ohne Worker gibt es einen Fehler mit Hinweis -- keine erfundenen Zahlen."""

    #: Eigene Sandbox pro Testlauf -- sonst bekaeme der Test die PID-Datei eines
    #: echt laufenden Workers zu fassen und wuerde ihn abschiessen.
    SANDBOX = "workspace/.test-trading-failclosed"

    def setUp(self) -> None:
        import shutil

        self.limb = TradingLimb()
        shutil.rmtree(REPO_ROOT / self.SANDBOX, ignore_errors=True)
        self.addCleanup(lambda: shutil.rmtree(REPO_ROOT / self.SANDBOX, ignore_errors=True))

    def _intent(self, operation: str, params: dict | None = None) -> Intent:
        return fresh_intent(operation, params, sandbox=self.SANDBOX)

    def test_unknown_port_is_rejected(self) -> None:
        intent = self._intent("trading.ping", {"port": 80})
        result = self.limb.execute(intent)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "E_SCHEMA_INVALID")

    def test_non_numeric_port_is_rejected(self) -> None:
        intent = self._intent("trading.ping", {"port": "vorne"})
        result = self.limb.execute(intent)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "E_SCHEMA_INVALID")

    def test_ping_on_empty_sandbox_reports_not_installed(self) -> None:
        intent = self._intent("trading.ping", {"port": 65500})
        result = self.limb.execute(intent)
        self.assertEqual(result.status, "success")
        self.assertFalse(result.output["installed"])
        self.assertFalse(result.output["running"])

    def test_status_without_worker_fails_with_hint(self) -> None:
        intent = self._intent("trading.status", {"port": 65500})
        result = self.limb.execute(intent)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "E_IO")
        self.assertIn("trading.start", result.error.get("hint", ""))

    def test_lake_summary_without_worker_fails_closed(self) -> None:
        intent = self._intent("trading.lake_summary", {"port": 65500})
        result = self.limb.execute(intent)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "E_IO")

    def test_stop_without_pid_file_is_a_no_op(self) -> None:
        intent = self._intent("trading.stop", {"port": 65500})
        result = self.limb.execute(intent)
        self.assertEqual(result.status, "success")
        self.assertFalse(result.output["stopped"])

    def test_kill_group_ignores_a_dead_pid(self) -> None:
        self.assertTrue(self.limb._kill_group(2_147_483_000))


class TradingBacktestParamsTests(unittest.TestCase):
    """Nur deklarierte Felder gehen an Sigma -- kein Durchreichen von Fremdem."""

    def setUp(self) -> None:
        self.limb = TradingLimb()
        self.sent: list[dict] = []
        limb = self.limb

        def fake_request(ctx, method, path, *, body=None, timeout_s=30.0):  # noqa: ANN001
            self.sent.append({"method": method, "path": path, "body": body})
            return {"ok": True}

        self._original = limb._request
        limb._request = fake_request  # type: ignore[method-assign]
        self.addCleanup(lambda: setattr(limb, "_request", self._original))

    def _ctx(self):  # noqa: ANN202
        import tempfile

        from base import LimbContext
        from core.policy import Policy

        config = NeuConfig.load()
        operations = Operations.load(OPERATIONS_PATH)
        policy = Policy(config, operations)
        intent = fresh_intent(
            "trading.backtest_run",
            {
                "strategy": "sma_cross",
                "pair": "ETH/USD",
                "interval": 15,
                "candleCount": 500,
                "initialBalance": 5000,
                "params": {"fast": 9},
                "evil": "DROP TABLE",
            },
        )
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return LimbContext(intent=intent, config=config, policy=policy, sandbox_root=Path(tmp.name))

    def test_only_declared_fields_reach_the_worker(self) -> None:
        self.limb._backtest_run(self._ctx().intent.task.params, self._ctx())
        body = self.sent[-1]["body"]
        self.assertEqual(self.sent[-1]["path"], "/api/backtest/run")
        self.assertNotIn("evil", body)
        self.assertEqual(body["strategyType"], "sma_cross")
        self.assertEqual(body["assetPair"], "ETH/USD")
        self.assertEqual(body["interval"], 15)
        self.assertEqual(body["candleCount"], 500)
        self.assertEqual(body["initialBalance"], 5000)

    def test_defaults_are_sane(self) -> None:
        ctx = self._ctx()
        self.limb._backtest_run({}, ctx)
        body = self.sent[-1]["body"]
        self.assertEqual(body["assetPair"], "BTC/USD")
        self.assertEqual(body["interval"], 60)
        self.assertGreaterEqual(body["candleCount"], 100)
        self.assertEqual(body["initialBalance"], 10_000.0)

    def test_lake_summary_hits_the_documented_route(self) -> None:
        self.limb._lake_summary({}, self._ctx())
        self.assertEqual(self.sent[-1]["method"], "GET")
        self.assertEqual(self.sent[-1]["path"], "/api/lake/summary")


class TradingScriptContractTests(unittest.TestCase):
    """Der Skript-Aufrufweg muss denselben Limb treffen wie der Import."""

    def test_script_emits_exactly_one_json_object(self) -> None:
        import tempfile

        intent = fresh_intent("trading.ping", {"port": 65500})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(intent.to_dict() if hasattr(intent, "to_dict") else intent.__dict__, handle, default=str)
            path = handle.name

        proc = subprocess.run(
            [sys.executable, str(LIMB_SCRIPT), "--intent", path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(result["protocol"], "neu/result")
        self.assertEqual(result["limb"]["name"], "trading")
        self.assertEqual(result["status"], "success")
        self.assertIn("installed", result["output"])


if __name__ == "__main__":
    unittest.main()
