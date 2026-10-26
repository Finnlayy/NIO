"""REA-Subagent-Limb: Vertrag, Grenzen und Timer-Verhalten.

Diese Suite prueft genau die Stellen, an denen ein werkzeugausfuehrender Limb
still kaputtgeht:

1. **Register-Drift** -- der Limb darf nur Operationen anbieten, die in
   ``limbs/registry.json`` *und* in ``protocol/operations.json`` stehen.
2. **Allowlist** -- ``rea.analyze`` ist kein Shell-Proxy: unbekannte Kommandos,
   Optionen und Argumentzahlen werden abgewiesen, bevor ein Prozess startet.
3. **Sandbox** -- Pfade werden von der Policy aufgeloest; ``..`` und absolute
   Pfade sind schon im Pre-Flight ein Fehler.
4. **Uhr** -- laeuft ein REA-Kind in die Frist, wird die Prozessgruppe beendet
   und der Limb liefert einen Statusbericht statt zu haengen.
5. **Belege** -- jede Analyse hinterlaesst ein Artefakt mit sha256, und das
   Result bleibt klein (Zusammenfassung statt 8 MB JSON).
"""

from __future__ import annotations

import json
import time
import unittest

from core.protocol import PROTOCOL_VERSION, ErrorCode, ProtocolError, sha256_file
from limbs.rea_limb import COMMANDS, ReaLimb, summarize_evidence

from . import REPO_ROOT
from .support_rea import ReaCase, node_available


@unittest.skipUnless(node_available(), "Node.js wird fuer den Stub-Einstiegspunkt gebraucht")
class TestReaLimbVertrag(ReaCase):
    def setUp(self) -> None:
        super().setUp()
        self.limb = ReaLimb(self.config, self.operations)

    # ------------------------------------------------------------- Handshake
    def test_ping_ohne_installation_ist_ein_befund_kein_crash(self):
        result = self.limb.execute(self.build("rea.ping"))
        self.assertEqual(result.status, "success")
        self.assertFalse(result.output["installed"])
        self.assertIn("install_hint", result.output)
        self.assertEqual(result.output["sandbox_root"], self.sandbox_rel())

    def test_ping_meldet_installation_layout_und_faehigkeiten(self):
        self.fake_install()
        result = self.limb.execute(self.build("rea.ping"))
        self.assertTrue(result.output["installed"])
        self.assertEqual(result.output["rea"]["version"], "9.9.9")
        self.assertEqual(result.output["rea"]["entrypoint"], "stub.mjs")
        self.assertTrue(result.output["layout"]["install"].endswith("/rea"))
        self.assertEqual(sorted(result.output["operations"]), sorted(self.limb.handlers()))
        self.assertIn("analyze-javascript-application", result.output["commands"])
        self.assertEqual(result.output["protocol"], PROTOCOL_VERSION)

    # ------------------------------------------------------------- Install
    def test_install_ohne_netz_wird_abgelehnt(self):
        result = self.limb.execute(self.build("rea.install", {"source": "git"}))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], ErrorCode.POLICY_DENIED)
        self.assertIn("allow_network", result.error["message"])
        # Kein Prozess, kein Verzeichnis: die Ablehnung passiert vor der Arbeit.
        self.assertFalse((self.sandbox() / "rea" / ".rea-install.json").exists())

    def test_install_dry_run_plant_ohne_prozess_und_ohne_bytes(self):
        result = self.limb.execute(
            self.build(
                "rea.install",
                {"source": "npm", "with_pwntools": True, "package_version": "6.0.0"},
                allow_network=True,
                dry_run=True,
            )
        )
        self.assertEqual(result.status, "success")
        self.assertTrue(result.output["dry_run"])
        self.assertEqual(result.output["would"]["source"], "npm")
        self.assertTrue(result.output["would"]["with_pwntools"])
        self.assertFalse((self.sandbox() / "rea" / ".rea-install.json").exists())

    def test_install_ist_idempotent_und_meldet_wiederverwendung(self):
        self.fake_install()
        result = self.limb.execute(self.build("rea.install", {"source": "git"}, allow_network=True))
        self.assertEqual(result.status, "success")
        self.assertTrue(result.output["reused"])
        self.assertEqual(result.output["version"], "9.9.9")

    # ------------------------------------------------------------- Analyze
    def test_analyze_fuehrt_freigegebenes_kommando_aus_und_legt_beleg_ab(self):
        self.fake_install()
        result = self.limb.execute(
            self.build(
                "rea.analyze",
                {"command": "analyze-javascript-application", "target": "targets/app"},
            )
        )
        self.assertEqual(result.status, "success")
        output = result.output
        self.assertEqual(output["evidence_id"], "ev_stub_0001")
        self.assertEqual(output["summary"]["application_graph"]["nodes"], 3)
        self.assertEqual(output["summary"]["semantic_graph"]["kinds"]["function"], 1)
        self.assertEqual(output["summary"]["semantic_graph"]["unknown_reasons"]["dynamic-call"], 2)
        self.assertIn("limitations", output["summary"])

        artifact = REPO_ROOT / output["raw"]["path"]
        self.assertTrue(artifact.is_file(), "der Rohbeleg muss als Datei existieren")
        self.assertEqual(artifact.stat().st_size, output["raw"]["bytes"])
        self.assertEqual(sha256_file(artifact), output["raw"]["sha256"])
        self.assertTrue(any(item.path == output["raw"]["path"] for item in result.artifacts))

    def test_analyze_argv_ist_eine_liste_ohne_shell_interpolation(self):
        self.fake_install()
        result = self.limb.execute(
            self.build(
                "rea.analyze",
                {
                    "command": "analyze",
                    "target": "targets/app",
                    "options": {"provider": "pwntools-elf"},
                },
            )
        )
        self.assertEqual(result.status, "success")
        # Der Stub schreibt seine argv zurueck -- damit ist die Reihenfolge pruefbar.
        raw = json.loads((REPO_ROOT / result.output["raw"]["path"]).read_text(encoding="utf-8"))
        argv = raw["argv"]
        self.assertEqual(argv[0], "analyze")
        self.assertTrue(argv[1].endswith("targets/app"))
        self.assertIn("--provider", argv)
        self.assertIn("pwntools-elf", argv)
        self.assertEqual(argv[-2:], ["--format", "json"])

    def test_analyze_weist_unbekanntes_kommando_ab(self):
        self.fake_install()
        result = self.limb.execute(self.build("rea.analyze", {"command": "rm -rf /", "target": "targets/app"}))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], ErrorCode.UNSUPPORTED_OP)
        self.assertIn("analyze-javascript-application", result.error["hint"])

    def test_analyze_weist_nicht_freigegebene_option_ab(self):
        self.fake_install()
        result = self.limb.execute(
            self.build(
                "rea.analyze",
                {"command": "analyze", "target": "targets/app", "options": {"exec": "/bin/sh"}},
            )
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], ErrorCode.SCHEMA_INVALID)

    def test_analyze_weist_falsche_argumentzahl_ab(self):
        self.fake_install()
        result = self.limb.execute(
            self.build("rea.analyze", {"command": "function", "target": "targets/app"})
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], ErrorCode.SCHEMA_INVALID)
        self.assertIn("Literal", result.error["message"])

    def test_analyze_verlaesst_die_sandbox_nicht(self):
        with self.assertRaises(ProtocolError) as caught:
            self.build("rea.analyze", {"command": "analyze", "target": "../fremd"})
        self.assertEqual(caught.exception.code, ErrorCode.SANDBOX_ESCAPE)

    def test_analyze_verweigert_absoluten_pfad(self):
        with self.assertRaises(ProtocolError) as caught:
            self.build("rea.analyze", {"command": "analyze", "target": "/etc/passwd"})
        self.assertEqual(caught.exception.code, ErrorCode.SANDBOX_ESCAPE)

    def test_analyze_meldet_providerfehler_mit_hinweis(self):
        self.fake_install()
        result = self.limb.execute(
            self.build("rea.analyze", {"command": "analyze", "target": "targets/broken-app"})
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], ErrorCode.TARGET_NOT_FOUND)
        self.assertIn("provider_unavailable", result.error["message"])
        self.assertIn("Engine installieren", result.error["hint"])

    def test_analyze_dry_run_startet_keinen_prozess(self):
        self.fake_install()
        result = self.limb.execute(
            self.build("rea.analyze", {"command": "analyze", "target": "targets/app"}, dry_run=True)
        )
        self.assertEqual(result.status, "success")
        self.assertTrue(result.output["dry_run"])
        self.assertIn("stub.mjs", result.output["argv"][0])
        self.assertFalse(list((self.sandbox() / "out").glob("*.json")))

    def test_analyze_beendet_das_kind_bei_timer_ablauf(self):
        self.fake_install()
        started = time.time()
        result = self.limb.execute(
            self.build(
                "rea.analyze",
                {"command": "analyze", "target": "targets/slow-app"},
                deadline_s=8.0,
                soft_deadline_s=4.0,
            )
        )
        elapsed = time.time() - started
        self.assertEqual(result.status, "timeout", "ein haengendes REA-Kind darf den Limb nicht blockieren")
        self.assertLess(elapsed, 20.0, "die Prozessgruppe muss beendet werden, nicht auslaufen")
        self.assertIsNotNone(result.status_report)
        self.assertTrue(result.status_report.remaining)

    def test_zusammenfassung_bleibt_klein(self):
        payload = {
            "evidence_id": "ev_x",
            "normalized_result": {
                "graph": {"nodes": [{"kind": "artifact"} for _ in range(5000)], "edges": [{} for _ in range(5000)]},
                "semantic_graph": {
                    "nodes": [{"kind": "expression"} for _ in range(5000)],
                    "relations": [{} for _ in range(5000)],
                    "unknowns": [{"reason": "dynamic-call"} for _ in range(5000)],
                },
            },
            "limitations": ["x" * 500 for _ in range(50)],
        }
        summary = summarize_evidence(payload)
        encoded = json.dumps(summary)
        self.assertLess(len(encoded), 20_000, "eine Zusammenfassung ist kein zweiter Rohbeleg")
        self.assertEqual(summary["application_graph"]["nodes"], 5000)
        self.assertEqual(summary["semantic_graph"]["unknown_reasons"]["dynamic-call"], 5000)


class TestReaRegister(unittest.TestCase):
    """Register, Protokoll und Implementierung muessen dasselbe sagen."""

    def test_register_bildet_den_rea_limb_exakt_ab(self):
        registry = json.loads((REPO_ROOT / "limbs" / "registry.json").read_text(encoding="utf-8"))
        entry = registry["limbs"]["rea"]
        self.assertEqual(sorted(entry["operations"]), sorted(ReaLimb().handlers()))
        self.assertEqual(entry["version"], ReaLimb.version)
        self.assertEqual(entry["status"], "active")
        self.assertEqual(entry["entrypoint"], "limbs/rea_limb.py")
        self.assertTrue((REPO_ROOT / "limbs" / "rea_limb.py").is_file())

    def test_jede_operation_steht_im_protokollregister(self):
        from core.protocol import Operations

        operations = Operations.load(REPO_ROOT / "protocol" / "operations.json")
        for name in ReaLimb().handlers():
            self.assertTrue(operations.known(name), f"{name} fehlt in protocol/operations.json")
            spec = operations.spec(name)
            self.assertIn("rea", spec.implemented_by)
            self.assertLessEqual(spec.phase, 3)

    def test_kommando_allowlist_ist_nicht_leer_und_hat_formen(self):
        self.assertGreaterEqual(len(COMMANDS), 15)
        for name, spec in COMMANDS.items():
            self.assertEqual(spec.name, name)
            self.assertLessEqual(spec.path_args, 2)
            self.assertGreaterEqual(spec.path_args, 0)
            for flag in spec.flags:
                self.assertRegex(flag, r"^[a-z][a-z0-9_]*$", "Optionsschluessel muessen snake_case sein")

    def test_analyze_deklariert_seine_pfadparameter_im_register(self):
        from core.protocol import Operations

        spec = Operations.load(REPO_ROOT / "protocol" / "operations.json").spec("rea.analyze")
        self.assertIn("target", spec.path_params)
        self.assertIn("out", spec.path_params)


if __name__ == "__main__":
    unittest.main()
