"""Subagent-Knoten: Identitaet, Sandbox-Isolation, Import und Lauf-Ledger.

Der Subagent ist die einzige Stelle im System, an der ein fremdes Werkzeug
(REA) mit *eigenem* Dateibestand laeuft. Vier Zusagen muessen halten:

* **Identitaet** -- IDs sind streng, ``..`` und Pfadtrenner sind keine IDs.
* **Isolation** -- Sandbox A kann Sandbox B nicht adressieren; das ist kein
  Kommentar, sondern eine Policy-Entscheidung, die hier geprueft wird.
* **Provenienz** -- ein importiertes Ziel bleibt byte-identisch, sein Manifest
  liegt daneben (nicht darin) und traegt Hashes.
* **Nachvollziehbarkeit** -- jeder Lauf steht als Job im Ledger des Subagenten.
"""

from __future__ import annotations

import hashlib
import unittest

from core.protocol import ErrorCode, ProtocolError
from orchestrator.subagent import SubagentManager, SubagentStore

from .support_rea import ReaCase, node_available


class TestSubagentVerwaltung(ReaCase):
    def setUp(self) -> None:
        super().setUp()
        self.manager = SubagentManager(self.config)

    # ------------------------------------------------------------- Anlegen
    def test_create_legt_layout_an_und_ist_idempotent(self):
        record = self.manager.ensure("rea-lab")
        sandbox = self.sandbox("rea-lab")
        for name in ("rea", "targets", "out", "logs", "tmp", "home", "cache", ".subagent"):
            self.assertTrue((sandbox / name).is_dir(), f"{name}/ fehlt in der Sandbox")
        self.assertTrue((sandbox / ".subagent" / "state.json").is_file())
        again = self.manager.ensure("rea-lab")
        self.assertEqual(again.created_at, record.created_at, "ensure darf den Zustand nicht neu schreiben")
        self.assertEqual(again.limb, "rea")

    def test_ids_mit_pfadanteilen_werden_abgewiesen(self):
        for bad in ("../evil", "a/b", "", "Ab", "-x", "x" * 60, "agent..x/../../y"):
            with self.assertRaises(ProtocolError, msg=f"{bad!r} haette abgelehnt werden muessen"):
                self.manager.ensure(bad)

    def test_list_findet_angelegte_subagenten(self):
        self.manager.ensure("agent-a")
        self.manager.ensure("agent-b", limb="echo")
        records = self.manager.list()
        self.assertEqual([r.agent_id for r in records], ["agent-a", "agent-b"])
        self.assertEqual(records[1].limb, "echo")

    # ------------------------------------------------------------- Import
    def test_import_kopiert_byte_identisch_und_manifest_liegt_daneben(self):
        source = self.workspace / "quelle"
        (source / "nested").mkdir(parents=True)
        (source / "app.js").write_text("console.log('orbit')\n", encoding="utf-8")
        (source / "nested" / "data.bin").write_bytes(bytes(range(32)))
        digest = hashlib.sha256((source / "app.js").read_bytes()).hexdigest()

        manifest = self.manager.import_target("agent-a", source, name="orbit")
        target = self.sandbox("agent-a") / "targets" / "orbit"
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["app.js", "nested"])
        self.assertEqual((target / "app.js").read_bytes(), (source / "app.js").read_bytes())
        self.assertEqual(manifest["files"], 2)
        self.assertEqual(manifest["entry"], self.config.relative(target))
        self.assertTrue((self.sandbox("agent-a") / "targets" / ".manifests" / "orbit.json").is_file())
        self.assertFalse((target / ".target.json").exists(), "das Ziel darf kein Manifest im Baum tragen")
        self.assertIn({"path": "app.js", "bytes": len(b"console.log('orbit')\n"), "sha256": digest}, manifest["entries"])

    def test_import_einzeldatei_wird_in_container_gelegt(self):
        single = self.workspace / "bundle.min.js"
        single.write_text("var a=1\n", encoding="utf-8")
        manifest = self.manager.import_target("agent-a", single)
        self.assertEqual(manifest["kind"], "file")
        self.assertTrue((self.sandbox("agent-a") / "targets" / "bundle.min.js" / "bundle.min.js").is_file())
        self.assertTrue(manifest["entry"].endswith("targets/bundle.min.js/bundle.min.js"))

    def test_import_ueberschreibt_nicht_ohne_replace(self):
        source = self.workspace / "quelle"
        source.mkdir()
        (source / "a.js").write_text("1\n", encoding="utf-8")
        self.manager.import_target("agent-a", source, name="dup")
        with self.assertRaises(ProtocolError) as caught:
            self.manager.import_target("agent-a", source, name="dup")
        self.assertEqual(caught.exception.code, ErrorCode.ALREADY_EXISTS)
        replaced = self.manager.import_target("agent-a", source, name="dup", replace=True)
        self.assertEqual(replaced["name"], "dup")

    def test_import_weist_boese_namen_ab(self):
        source = self.workspace / "quelle"
        source.mkdir()
        (source / "a.js").write_text("1\n", encoding="utf-8")
        with self.assertRaises(ProtocolError) as caught:
            self.manager.import_target("agent-a", source, name="../ausbruch")
        self.assertEqual(caught.exception.code, ErrorCode.SCHEMA_INVALID)

    def test_import_fehlende_quelle_ist_ein_protokollfehler(self):
        with self.assertRaises(ProtocolError) as caught:
            self.manager.import_target("agent-a", self.workspace / "gibtsnicht")
        self.assertEqual(caught.exception.code, ErrorCode.PATH_NOT_FOUND)

    # ------------------------------------------------------------- Status
    def test_status_meldet_installation_und_inventar(self):
        self.manager.ensure("agent-a")
        self.fake_install()
        status = self.manager.status("agent-a")
        self.assertTrue(status["rea"]["installed"])
        self.assertEqual(status["rea"]["version"], "9.9.9")
        self.assertEqual(status["rea"]["source"], "test")
        self.assertIn("rea", status["dirs"])
        self.assertGreater(status["dirs"]["rea"]["files"], 0)

    def test_status_unbekannter_agent_ist_ein_protokollfehler(self):
        with self.assertRaises(ProtocolError) as caught:
            self.manager.status("gibtsnicht")
        self.assertEqual(caught.exception.code, ErrorCode.PATH_NOT_FOUND)

    # ------------------------------------------------------------- Laeufe
    def test_run_landet_als_job_im_ledger_und_in_der_sandbox(self):
        outcome = self.manager.run(
            "agent-a",
            goal="Echo im Subagenten",
            operation="sys.echo",
            params={"message": "hallo sandbox"},
            limb="echo",
            deadline_s=15.0,
            soft_deadline_s=10.0,
        )
        self.assertTrue(outcome.ok, f"Job status={outcome.status}")
        record = self.manager.store.load("agent-a")
        self.assertIsNotNone(record)
        self.assertEqual(len(record.runs), 1)
        self.assertEqual(record.runs[0]["job_id"], outcome.job.job_id)
        self.assertEqual(record.runs[0]["operation"], "sys.echo")
        self.assertEqual(record.runs[0]["status"], "resolved")
        intent = outcome.attempts[-1].intent
        self.assertEqual(intent.constraints.sandbox_root, self.sandbox_rel("agent-a"))
        self.assertTrue((self.runtime / "jobs" / f"{outcome.job.job_id}.json").is_file())

    @unittest.skipUnless(node_available(), "Node.js fehlt")
    def test_run_mit_rea_analyze_schreibt_evidence_in_das_ledger(self):
        self.fake_install()
        outcome = self.manager.run(
            "agent-a",
            goal="Stub analysieren",
            operation="rea.analyze",
            params={"command": "analyze-javascript-application", "target": "targets/app"},
            deadline_s=30.0,
            soft_deadline_s=25.0,
        )
        self.assertTrue(outcome.ok, f"Job status={outcome.status}")
        record = self.manager.store.load("agent-a")
        assert record is not None
        entry = record.runs[-1]
        self.assertEqual(entry["evidence_id"], "ev_stub_0001")
        self.assertTrue(entry["raw"].startswith(self.sandbox_rel("agent-a")), entry["raw"])
        self.assertTrue((self.config.repo_root / entry["raw"]).is_file())

    @unittest.skipUnless(node_available(), "Node.js fehlt")
    def test_run_install_aktualisiert_installationszustand(self):
        self.fake_install()
        outcome = self.manager.run(
            "agent-a",
            goal="Installation nachweisen",
            operation="rea.install",
            params={"source": "git"},
            allow_network=True,
            deadline_s=20.0,
            soft_deadline_s=15.0,
        )
        self.assertTrue(outcome.ok)
        record = self.manager.store.load("agent-a")
        assert record is not None
        self.assertEqual(record.install["version"], "9.9.9")
        self.assertEqual(record.install["source"], "test")

    # ------------------------------------------------------------- Isolation
    def test_zwei_subagenten_haben_getrennte_sandboxen(self):
        self.manager.ensure("agent-a")
        self.manager.ensure("agent-b")
        self.assertNotEqual(self.manager.sandbox("agent-a"), self.manager.sandbox("agent-b"))
        self.assertTrue(str(self.manager.sandbox("agent-a")).endswith("agent-a"))

    def test_sandbox_a_kann_sandbox_b_nicht_adressieren(self):
        self.fake_install("agent-a")
        self.fake_install("agent-b")
        with self.assertRaises(ProtocolError) as caught:
            self.kernel.build_intent(
                operation="rea.analyze",
                params={"command": "analyze", "target": "../agent-b/targets/app"},
                limb="rea",
                goal="Ausbruchsversuch",
                constraints={"sandbox_root": self.sandbox_rel("agent-a")},
            )
        self.assertEqual(caught.exception.code, ErrorCode.SANDBOX_ESCAPE)

    def test_zustand_ueberlebt_einen_neuen_manager(self):
        self.manager.ensure("agent-a")
        fresh = SubagentManager(self.config, store=SubagentStore(self.config))
        record = fresh.store.load("agent-a")
        assert record is not None
        self.assertEqual(record.sandbox, self.sandbox_rel("agent-a"))
        self.assertEqual(record.limb, "rea")


if __name__ == "__main__":
    unittest.main()
