"""Lauf-Modell: Ablage, Schwaerzen, Backoff, Ablauf mit einem Testagenten."""

from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.config import NeuConfig
from core.protocol import ErrorCode, Operations
from limbs import agent_base
from limbs.agent_base import AgentLimb, Poll, RunStore, backoff_s, redact
from limbs.base import LimbError

from . import REPO_ROOT


class RedactTest(unittest.TestCase):
    def test_schwaerzt_rekursiv(self):
        data = {"a": "x-geheim-y", "geheim": ["geheim", {"b": 1}], "c": None}
        self.assertEqual(redact(data, ["geheim"]), {"a": "x-[REDACTED]-y", "[REDACTED]": ["[REDACTED]", {"b": 1}], "c": None})

    def test_leeres_geheimnis_aendert_nichts(self):
        self.assertEqual(redact("text", ["", ""]), "text")


class BackoffTest(unittest.TestCase):
    def test_waechst_und_bleibt_gedeckelt(self):
        self.assertGreaterEqual(backoff_s(0.0), 2 * agent_base.MIN_POLL_S)
        self.assertLessEqual(backoff_s(10_000.0), agent_base.MAX_BACKOFF_S * 1.25)


class RunStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = RunStore(Path(self.tmp.name), lambda: ["geheim"])

    def test_lauf_wird_geschwaerzt_gespeichert(self):
        run = self.store.create("demo", note="enthaelt geheim")
        self.store.event(run["run_id"], "probe", detail="geheim")
        folder = self.store.path(run["run_id"])
        self.assertNotIn("geheim", (folder / "state.json").read_text(encoding="utf-8"))
        self.assertNotIn("geheim", (folder / "events.jsonl").read_text(encoding="utf-8"))

    def test_run_id_kann_keinen_pfad_tragen(self):
        for run_id in ("../x", "run_../../etc", "", "run_ABC"):
            with self.subTest(run_id), self.assertRaises(LimbError):
                self.store.load(run_id, "demo")

    def test_fremder_lauf_ist_unbekannt(self):
        run = self.store.create("demo")
        with self.assertRaises(LimbError) as caught:
            self.store.load(run["run_id"], "anderer")
        self.assertEqual(caught.exception.code, ErrorCode.TARGET_NOT_FOUND)


class DemoAgent(AgentLimb):
    """Gefaelschter Agent, der die Betriebsarten aus ``script`` durchlaeuft."""

    name = "demo"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.script: list[Any] = []
        self.halted = 0
        self.halt_error: Exception | None = None

    def handlers(self):
        return self.agent_handlers()

    def launch(self, params: Mapping[str, Any], ctx: Any, run: dict[str, Any]) -> None:
        if params.get("fail"):
            raise agent_base.ServiceDown("kaputt")

    def poll(self, run: dict[str, Any], ctx: Any) -> Poll:
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def over_budget(self, run: dict[str, Any], poll: Poll, ctx: Any) -> str:
        return "zu teuer" if (poll.detail or {}).get("tokens", 0) > 100 else ""

    def halt(self, run: dict[str, Any], ctx: Any) -> None:
        self.halted += 1
        if self.halt_error:
            raise self.halt_error

    def gather(self, run: dict[str, Any], ctx: Any) -> dict[str, Any]:
        return {"text": "fertig"}


class FakeContext:

    def rel(self, path: Path) -> str:
        return str(path)


class AgentRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.limb = DemoAgent.__new__(DemoAgent)
        self.limb.script = []
        self.limb.halted = 0
        self.limb.halt_error = None
        self.limb.config = NeuConfig.load(REPO_ROOT, runtime_dir=Path(self.tmp.name))
        self.limb.operations = Operations.load(self.limb.config.protocol_dir / "operations.json")
        self.ctx = FakeContext()

    def start(self, **params: Any) -> dict[str, Any]:
        return self.limb._start(params, self.ctx)

    def status(self, run_id: str, *script: Any) -> dict[str, Any]:
        self.limb.script = list(script)
        run = self.limb.runs.load(run_id, "demo")
        run["next_poll_s"] = 0.0
        self.limb.runs.save(run)
        return self.limb._status({"run_id": run_id}, self.ctx)

    def test_erfolg_und_abholen(self):
        run_id = self.start()["run_id"]
        self.assertEqual(self.status(run_id, Poll("running"))["state"], "running")
        self.assertEqual(self.status(run_id, Poll("succeeded"))["state"], "succeeded")
        output = self.limb._collect({"run_id": run_id}, self.ctx)
        self.assertEqual(output["text"], "fertig")
        self.assertTrue(output["untrusted"])
        stored = json.loads(Path(output["result_path"]).read_text(encoding="utf-8"))
        self.assertTrue(stored["untrusted"])

    def test_mindestabstand_spart_die_abfrage(self):
        run_id = self.start()["run_id"]
        self.status(run_id, Poll("running"))
        self.limb.script = [AssertionError("darf nicht abfragen")]
        self.assertEqual(self.limb._status({"run_id": run_id}, self.ctx)["state"], "running")

    def test_budget_stoppt_den_lauf(self):
        run_id = self.start()["run_id"]
        view = self.status(run_id, Poll("running", {"tokens": 101}))
        self.assertEqual(view["state"], "budget_stopped")
        self.assertEqual(self.limb.halted, 1)
        self.assertTrue(view["stop_confirmed"])

    def test_stopp_fehlgeschlagen_wird_gemeldet(self):
        self.limb.halt_error = agent_base.ServiceDown("weg")
        run_id = self.start()["run_id"]
        view = self.status(run_id, Poll("running", {"tokens": 101}))
        self.assertEqual(view["state"], "budget_stopped")
        self.assertFalse(view["stop_confirmed"])
        self.assertIn("weiterlaufen", view["error"])

    def test_laufzeit_beendet_den_lauf(self):
        run_id = self.start()["run_id"]
        run = self.limb.runs.load(run_id, "demo")
        run["started_s"] = 0.0
        self.limb.runs.save(run)
        self.assertEqual(self.status(run_id, Poll("running"))["state"], "timeout")
        self.assertEqual(self.limb.halted, 1)

    def test_ausfall_haelt_den_lauf_und_verlaengert_den_abstand(self):
        run_id = self.start()["run_id"]
        view = self.status(run_id, agent_base.ServiceDown("weg"))
        self.assertEqual(view["state"], "running")
        self.assertTrue(view["degraded"])
        self.assertGreater(view["next_poll_after_s"], agent_base.MIN_POLL_S)
        self.assertFalse(self.status(run_id, Poll("running")).get("degraded"))

    def test_laufzeit_greift_auch_bei_ausfall(self):
        run_id = self.start()["run_id"]
        run = self.limb.runs.load(run_id, "demo")
        run["started_s"] = 0.0
        self.limb.runs.save(run)
        view = self.status(run_id, agent_base.ServiceDown("weg"))
        self.assertEqual(view["state"], "timeout")
        self.assertEqual(self.limb.halted, 1)

    def test_rueckfrage_wartet_und_wird_nicht_bestaetigt(self):
        run_id = self.start()["run_id"]
        view = self.status(run_id, Poll("waiting", {"frage": "weiter?"}))
        self.assertEqual(view["state"], "waiting")
        self.assertEqual(view["confirmation"], {"frage": "weiter?"})
        self.assertNotIn("confirmation", self.status(run_id, Poll("running")))

    def test_fehlgeschlagener_start_wird_nicht_wiederholt(self):
        with self.assertRaises(LimbError) as caught:
            self.start(fail=True)
        self.assertEqual(caught.exception.code, ErrorCode.IO)
        runs = list(Path(self.tmp.name, "agents").iterdir())
        self.assertEqual(len(runs), 1)
        self.assertEqual(json.loads((runs[0] / "state.json").read_text(encoding="utf-8"))["state"], "failed")

    def test_collect_erst_nach_dem_ende(self):
        run_id = self.start()["run_id"]
        with self.assertRaises(LimbError) as caught:
            self.limb._collect({"run_id": run_id}, self.ctx)
        self.assertEqual(caught.exception.code, ErrorCode.POLICY_DENIED)

    def test_stop_ist_wiederholbar(self):
        run_id = self.start()["run_id"]
        self.assertEqual(self.limb._stop({"run_id": run_id}, self.ctx)["state"], "stopped")
        self.assertEqual(self.limb._stop({"run_id": run_id}, self.ctx)["state"], "stopped")
        self.assertEqual(self.limb.halted, 1)


if __name__ == "__main__":
    unittest.main()
