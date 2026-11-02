"""OpenManus-Limb: Abschottung, Ablauf und Sperre mit gefaelschtem Docker."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from core.config import NeuConfig
from core.protocol import ErrorCode, Operations
from limbs import openmanus_limb
from limbs.agent_base import ServiceDown
from limbs.base import LimbError
from limbs.openmanus_limb import IMAGE, NETWORK, OpenManusLimb, container_args

from . import REPO_ROOT


class ContainerArgsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.args = container_args("run_x", Path("/j"), 60, 5)

    def test_abschottung(self):
        self.assertIn("--read-only", self.args)
        self.assertEqual(self.args[self.args.index("--cap-drop") + 1], "ALL")
        self.assertEqual(self.args[self.args.index("--network") + 1], NETWORK)
        self.assertNotEqual(self.args[self.args.index("--user") + 1].split(":")[0], "0")
        for flag in ("--memory", "--cpus", "--pids-limit"):
            self.assertIn(flag, self.args)

    def test_mounts_nur_vom_lauf(self):
        mounts = [self.args[i + 1] for i, value in enumerate(self.args) if value == "--volume"]
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(mount.startswith("/j/") for mount in mounts))
        self.assertNotIn("docker.sock", " ".join(self.args))

    def test_keine_geheimnisse_in_der_umgebung(self):
        envs = [self.args[i + 1] for i, value in enumerate(self.args) if value == "--env"]
        self.assertEqual({env.split("=")[0] for env in envs}, {"NIO_MAX_RUNTIME_S", "NIO_MAX_STEPS"})

    def test_image_steht_zuletzt(self):
        self.assertEqual(self.args[-1], IMAGE)


class FakeDocker:
    """Antwortet wie die Docker-CLI und merkt sich die Aufrufe."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.status = "running"
        self.exists = True
        self.network = "true true"
        self.fail_run = False

    def __call__(self, *args: str, timeout: int = 30) -> str:
        self.calls.append(args)
        if args[0] == "network":
            return self.network
        if args[0] == "run" and self.fail_run:
            raise ServiceDown("docker run: kaputt")
        if args[0] == "inspect":
            return self.status
        if args[0] == "ps":
            return "abc" if self.exists else ""
        return ""

    def removed(self) -> bool:
        return any(call[:2] == ("rm", "--force") for call in self.calls)


class FakeContext:
    def rel(self, path: Path) -> str:
        return str(path)

    def record(self, *_: Any) -> None:
        pass


class LimbTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.docker = FakeDocker()
        patches = [
            mock.patch.object(openmanus_limb, "docker", self.docker),
            mock.patch.dict(os.environ, {"FREELLMAPI_KEY": "geheim-123", "OPENMANUS_MODEL": "m"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.limb = OpenManusLimb.__new__(OpenManusLimb)
        self.limb.config = NeuConfig.load(REPO_ROOT, runtime_dir=Path(self.tmp.name))
        self.limb.operations = Operations.load(self.limb.config.protocol_dir / "operations.json")
        self.ctx = FakeContext()

    def start(self, **params: Any) -> str:
        return self.limb._start({"prompt": "tu was", **params}, self.ctx)["run_id"]

    def status(self, run_id: str) -> dict[str, Any]:
        run = self.limb.runs.load(run_id, "openmanus")
        run["next_poll_s"] = 0.0
        self.limb.runs.save(run)
        return self.limb._status({"run_id": run_id}, self.ctx)

    def job(self, run_id: str) -> Path:
        return self.limb._job(run_id)

    def result(self, run_id: str, **data: Any) -> None:
        out = self.job(run_id) / "workspace" / "out"
        out.mkdir(parents=True)
        (out / "result.json").write_text(json.dumps(data), encoding="utf-8")

    def test_ohne_modell_kein_lauf(self):
        with mock.patch.dict(os.environ, {"OPENMANUS_MODEL": ""}), self.assertRaises(LimbError) as caught:
            self.start()
        self.assertEqual(caught.exception.code, ErrorCode.POLICY_DENIED)

    def test_offenes_netz_wird_abgewiesen(self):
        for network in ("false true", "true <no value>", "true false"):
            self.docker.network = network
            with self.subTest(network), self.assertRaises(LimbError):
                self.start()
        self.assertFalse(any(call[0] == "run" for call in self.docker.calls))

    def test_grenzen_werden_gedeckelt(self):
        run_id = self.start(max_runtime_s=999_999, max_steps=999)
        run = self.limb.runs.load(run_id, "openmanus")
        self.assertEqual((run["max_runtime_s"], run["max_steps"]), (openmanus_limb.MAX_RUNTIME_S, openmanus_limb.MAX_STEPS))

    def test_key_liegt_nur_in_der_laufkonfiguration(self):
        run_id = self.start()
        config = self.job(run_id) / "config" / "config.toml"
        self.assertIn("geheim-123", config.read_text(encoding="utf-8"))
        self.assertEqual(config.stat().st_mode & 0o077, 0)
        self.assertNotIn("geheim-123", (self.limb.runs.path(run_id) / "state.json").read_text(encoding="utf-8"))

    def test_erfolg_raeumt_auf_und_liefert_artefakte(self):
        run_id = self.start()
        self.assertEqual(self.status(run_id)["state"], "running")
        self.result(run_id, state="succeeded", summary="fertig", steps=2)
        (self.job(run_id) / "workspace" / "a.txt").write_text("x", encoding="utf-8")
        self.docker.status = "exited"
        self.assertEqual(self.status(run_id)["state"], "succeeded")
        self.assertTrue(self.docker.removed())
        self.assertFalse((self.job(run_id) / "config" / "config.toml").exists())
        output = self.limb._collect({"run_id": run_id}, self.ctx)
        self.assertEqual(output["artifacts"], ["a.txt"])
        self.assertTrue(output["untrusted"])

    def test_unklares_ergebnis_gilt_als_fehlschlag(self):
        for content in (None, "kein json", '["liste"]', '{"state": "vielleicht"}'):
            run_id = self.start()
            if content is not None:
                out = self.job(run_id) / "workspace" / "out"
                out.mkdir(parents=True)
                (out / "result.json").write_text(content, encoding="utf-8")
            self.docker.status = "exited"
            with self.subTest(content):
                self.assertEqual(self.status(run_id)["state"], "failed")
            self.docker.status = "running"

    def test_timeout_aus_dem_container(self):
        run_id = self.start()
        self.result(run_id, state="timeout", error="Laufzeit")
        self.docker.status = "exited"
        self.assertEqual(self.status(run_id)["state"], "timeout")

    def test_stop_entfernt_container_und_key(self):
        run_id = self.start()
        view = self.limb._stop({"run_id": run_id}, self.ctx)
        self.assertEqual(view["state"], "stopped")
        self.assertTrue(view["stop_confirmed"])
        self.assertTrue(self.docker.removed())
        self.assertFalse((self.job(run_id) / "config" / "config.toml").exists())

    def test_fehlgeschlagener_start_entfernt_den_key(self):
        self.docker.fail_run = True
        with self.assertRaises(LimbError):
            self.start()
        run_dir = next(Path(self.tmp.name, "agents").iterdir())
        self.assertFalse((run_dir / "job" / "config" / "config.toml").exists())

    def test_ping(self):
        output = self.limb._ping({}, self.ctx)
        self.assertTrue(output["network_ready"] and output["image_ready"] and output["model_ready"])


class RegistryTest(unittest.TestCase):
    def test_limb_bleibt_gesperrt(self):
        registry = json.loads((REPO_ROOT / "limbs" / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["limbs"]["openmanus"]["status"], "planned")

    def test_start_ist_risk_high(self):
        operations = json.loads((REPO_ROOT / "protocol" / "operations.json").read_text(encoding="utf-8"))
        table = operations.get("operations", operations)
        self.assertEqual(table["openmanus.start"]["risk"], "high")


if __name__ == "__main__":
    unittest.main()
