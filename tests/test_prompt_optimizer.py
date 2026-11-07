"""Tests des Prompt-Optimierers: Moduswahl, Sperren, Stufen-Gate, Coverage.

Die Suite prueft die Invarianten, die den Optimierer ausmachen -- nicht die
sprachliche Qualitaet der Artefakte:

* Modus: ohne Befehl ``NORMAL``, das Wort "Research" allein zaehlt nicht.
* Stufe 1: 0 % Feature-Verlust, Inhalt gesperrt.
* Stufe 2/3: Prompt-Struktur per Fingerprint gesperrt.
* Stufe 4: 0 % Inhaltsverlust, Coverage 100 %, danach unveraenderlich.
* Arbeitskontext wird nach jeder Stufe geleert; jede Stufe liest von der Platte.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.prompt_optimizer import (
    ARTIFACT_NORMAL,
    FINAL_MARKER,
    Mode,
    PromptOptimizer,
    StageDocument,
    StageOrderError,
    StructuralFiller,
    parse_draft,
    resolve_mode,
)
from core.prompt_optimizer.gates import expand_document
from core.prompt_optimizer.model import Feature
from core.prompt_optimizer.model import StageDocument as Doc
from core.prompt_optimizer.pipeline import SYNTHESIS_CONTRACT, ApprovalRequired
from core.prompt_optimizer.research import FixtureProvider, LocalSourceChecker, NullProvider
from core.prompt_optimizer.scorecard import LockViolation, enforce_lock, measure_content, measure_technique

REPO_ROOT = Path(__file__).resolve().parents[1]

DRAFT = """\
# Demo: Widget-Leiste

Der Entwurf beschreibt eine Leiste, die Messwerte anzeigt.

## Anzeige

- Sparkline mit 60fps-Ziel rendern
- Farbcodierung nach Schweregrad
- API-Vertrag fuer die Widget-Daten
- Fehlerfall: fehlende Daten duerfen die Leiste nicht leeren
- Intervall: 250 ms
- Intervall: 500 ms

## Transport

- Off-Heap-Ringpuffer zwischen Worker und UI
- IPC ohne WebSocket
- Backpressure bei Ueberlauf
- Der Transport nutzt WebSocket fuer das Signaling
"""

SMALL_DRAFT = """\
# Klein

## A

- Ein Feature mit API-Vertrag
- Ein Randfall: Timeout bei 200 ms
"""


def chain(tmp: str, draft: str = DRAFT, **kwargs) -> tuple[PromptOptimizer, list]:
    optimizer = PromptOptimizer(draft, out_dir=tmp, mode=Mode.DEEP_CHAIN, auto_approve=True, **kwargs)
    return optimizer, optimizer.run_all()


class TestModeSelection(unittest.TestCase):
    def test_ohne_angabe_ist_normal(self) -> None:
        mode, reason = resolve_mode(None, "Optimiere diesen Prompt.")
        self.assertIs(mode, Mode.NORMAL)
        self.assertIn("Standard", reason)

    def test_research_allein_aktiviert_kein_deep_chain(self) -> None:
        mode, _ = resolve_mode(None, "Bitte Deep Research einbauen und optimieren.")
        self.assertIs(mode, Mode.NORMAL)

    def test_ausdruecklicher_befehl_aktiviert_deep_chain(self) -> None:
        for text in ("Starte 4-Stufen-Kette", "MODUS: Deep-Chain", "Erweiterte Optimierung bitte"):
            mode, _ = resolve_mode(None, text)
            self.assertIs(mode, Mode.DEEP_CHAIN, text)

    def test_explizite_angabe_schlaegt_text(self) -> None:
        mode, _ = resolve_mode("normal", "Deep Optimization")
        self.assertIs(mode, Mode.NORMAL)
        mode, _ = resolve_mode("erweitert", "")
        self.assertIs(mode, Mode.DEEP_CHAIN)


class TestExtraction(unittest.TestCase):
    def test_features_werden_vollstaendig_und_stabil_nummeriert(self) -> None:
        doc = parse_draft(DRAFT)
        self.assertEqual(len(doc.features), 10)
        self.assertEqual(doc.feature_ids[0], "F-01")
        self.assertEqual(doc.feature_ids[-1], "F-10")
        self.assertEqual(len({feature.fid for feature in doc.features}), len(doc.features))

    def test_doppelte_bullets_werden_dedupliziert(self) -> None:
        doc = parse_draft("# X\n\n## A\n\n- Ein Feature\n- Ein  Feature\n")
        self.assertEqual(len(doc.features), 1)

    def test_explizite_ids_bleiben_erhalten(self) -> None:
        doc = parse_draft("# X\n\n## A\n\n- [F-07] Bestehendes Feature\n- Zweites Feature mit Inhalt\n")
        self.assertTrue(doc.features[0].explicit_id)
        self.assertEqual(doc.features[0].fid, "F-07")
        self.assertEqual(len({feature.fid for feature in doc.features}), len(doc.features))

    def test_subsystem_bindung_zeigt_auf_die_id(self) -> None:
        doc = parse_draft(DRAFT)
        self.assertTrue(all(feature.subsystem.startswith("S-") for feature in doc.features))
        self.assertTrue(all(subsystem.features for subsystem in doc.subsystems))

    def test_zahlenwiderspruch_wird_erkannt(self) -> None:
        doc = parse_draft(DRAFT)
        self.assertTrue(any("Zahlenwiderspruch" in conflict for conflict in doc.conflicts))
        self.assertTrue(any("250ms" in conflict for conflict in doc.conflicts))

    def test_ausschlusswiderspruch_wird_erkannt(self) -> None:
        doc = parse_draft(DRAFT)
        self.assertTrue(any("websocket" in conflict.casefold() for conflict in doc.conflicts))

    def test_ohne_widerspruch_bleibt_die_liste_leer(self) -> None:
        self.assertEqual(parse_draft(SMALL_DRAFT).conflicts, [])


class TestDeepChain(unittest.TestCase):
    def test_alle_vier_artefakte_entstehen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, results = chain(tmp)
            self.assertEqual([result.stage for result in results], [0, 1, 2, 3, 4])
            for name in ("stage_1_macro_skeleton.md", "stage_2_domain_expansion.md", "stage_3_verified_research_leaves.md", "stage_4_FINAL_MASTER_PROMPT.md"):
                self.assertTrue((Path(tmp) / name).is_file(), name)

    def test_stufe1_verliert_kein_feature_und_erfindet_keins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _optimizer, results = chain(tmp)
            draft_features = parse_draft(DRAFT).features
            stage1 = json.loads((Path(tmp) / "stage_1.model.json").read_text(encoding="utf-8"))
            titles = [(item["fid"], item["title"]) for item in stage1["features"]]
            self.assertEqual(titles, [(feature.fid, feature.title) for feature in draft_features])
            self.assertEqual(results[1].scorecard.content.before, results[1].scorecard.content.after)

    def test_inhalt_steigt_nur_in_stufe_2_und_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, results = chain(tmp)
            content = [result.scorecard.content.after for result in results]
            self.assertEqual(content[1], content[0])
            self.assertGreaterEqual(content[2], content[1])
            self.assertGreaterEqual(content[3], content[2])
            self.assertEqual(content[4], content[3])

    def test_technik_steigt_nur_in_stufe_1_und_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, results = chain(tmp)
            technique = [result.scorecard.technique.after for result in results]
            self.assertGreater(technique[1], technique[0])
            self.assertEqual(technique[2], technique[1])
            self.assertEqual(technique[3], technique[1])
            self.assertGreaterEqual(technique[4], technique[1])

    def test_gesperrte_achse_traegt_status_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, results = chain(tmp)
            self.assertTrue(results[1].scorecard.content.locked)
            self.assertFalse(results[1].scorecard.technique.locked)
            self.assertTrue(results[2].scorecard.technique.locked)
            self.assertFalse(results[2].scorecard.content.locked)
            self.assertTrue(results[4].scorecard.content.locked)

    def test_telemetrie_tabelle_hat_die_vereinbarten_spalten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, results = chain(tmp)
            table = results[2].scorecard.render()
            for column in ("| Dimension | Status in Stufe 2 | Vorher | Aktuell | Delta (Δ) | Nachweis & Haupttreiber |"):
                self.assertIn(column, table)
            self.assertIn("`[AKTIV]`", table)
            self.assertIn("`[LOCK 🔒]`", table)

    def test_struktur_ist_zwischen_stufe_1_und_3_identisch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chain(tmp)
            one = Doc.from_dict(json.loads((Path(tmp) / "stage_1.model.json").read_text(encoding="utf-8")))
            three = Doc.from_dict(json.loads((Path(tmp) / "stage_3.model.json").read_text(encoding="utf-8")))
            self.assertEqual(one.sections, three.sections)
            self.assertEqual(one.contract, three.contract)
            self.assertEqual(one.technique_fingerprint, three.technique_fingerprint)

    def test_gate_ohne_freigabe_blockiert_die_naechste_stufe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            optimizer = PromptOptimizer(DRAFT, out_dir=tmp, mode=Mode.DEEP_CHAIN)
            optimizer.prepare()
            optimizer.run_stage(1)
            with self.assertRaises(ApprovalRequired):
                optimizer.run_stage(2)
            optimizer.approve()
            result = optimizer.run_stage(2)
            self.assertEqual(result.stage, 2)

    def test_abgebrochener_lauf_wird_fortgesetzt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = PromptOptimizer(DRAFT, out_dir=tmp, mode=Mode.DEEP_CHAIN)
            first.prepare()
            first.run_stage(1)
            first.approve()
            first.run_stage(2)
            resumed = PromptOptimizer(DRAFT, out_dir=tmp, mode=Mode.DEEP_CHAIN)
            self.assertEqual(resumed.current_stage, 2)
            rest = resumed.run_all()
            self.assertEqual([result.stage for result in rest], [3, 4])

    def test_stufe_ausser_der_reihe_fliegt_raus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            optimizer = PromptOptimizer(DRAFT, out_dir=tmp, mode=Mode.DEEP_CHAIN, auto_approve=True)
            optimizer.prepare()
            with self.assertRaises(StageOrderError):
                optimizer.run_stage(3)

    def test_arbeitskontext_wird_geleert_und_von_platte_gelesen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _optimizer, _ = chain(tmp)
            state = json.loads((Path(tmp) / "run_state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["context_empty"])
            for stage in (1, 2, 3, 4):
                raw = (Path(tmp) / f"stage_{stage}.model.json").read_text(encoding="utf-8")
                # Kein Checkpoint traegt den Rohentwurf: die naechste Stufe
                # arbeitet aus dem Modellstand, nicht aus dem Eingabetext.
                self.assertNotIn("## Anzeige", raw)
                self.assertNotIn("draft_text", raw)

    def test_finales_dokument_wird_nicht_neu_geschrieben(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chain(tmp)
            final_path = Path(tmp) / "stage_4_FINAL_MASTER_PROMPT.md"
            before = final_path.read_text(encoding="utf-8")
            self.assertIn(FINAL_MARKER, before)
            again, results = chain(tmp)
            self.assertTrue(results[-1].no_op)
            self.assertEqual(again.run_all()[-1].markdown, before)
            self.assertEqual(final_path.read_text(encoding="utf-8"), before)

    def test_coverage_nachweis_ist_vollstaendig(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, results = chain(tmp)
            coverage = results[-1].coverage
            self.assertTrue(any("Features: 10/10" in item for item in coverage), coverage)
            text = (Path(tmp) / "stage_4_FINAL_MASTER_PROMPT.md").read_text(encoding="utf-8")
            self.assertIn("`[F-01..10] & [R-01..06] = 100 %`", text)

    def test_offene_blaetter_bleiben_ohne_provider_unverifiziert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chain(tmp, provider=NullProvider())
            model = json.loads((Path(tmp) / "stage_3.model.json").read_text(encoding="utf-8"))
            leaves = model["leaves"]
            self.assertTrue(leaves)
            self.assertTrue(all(leaf["status"] == "UNVERIFIZIERT" for leaf in leaves))
            self.assertTrue(all(leaf["uncertainty"].startswith("unbelegt") for leaf in leaves))

    def test_research_blaetter_sind_eindeutig_nummeriert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chain(tmp)
            model = json.loads((Path(tmp) / "stage_2.model.json").read_text(encoding="utf-8"))
            ids = [leaf["rid"] for leaf in model["leaves"]]
            self.assertEqual(ids, [f"R-{index:02d}" for index in range(1, len(ids) + 1)])

    def test_widersprueche_werden_zu_entscheidungen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, results = chain(tmp)
            markdown = results[1].markdown
            self.assertIn("[ENTSCHEIDUNG NÖTIG]", markdown)
            self.assertIn("Widerspruchsfreiheit 25/25", markdown)


class TestVerification(unittest.TestCase):
    def test_lokale_quelle_wird_verifiziert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = FixtureProvider(
                {
                    "R-01": [
                        {
                            "tier": 3,
                            "locator": "repo:protocol/PROTOCOL.md",
                            "quote": "Protokoll-ID: `neu/intent` und `neu/result`, Version `1.2`.",
                            "retrieved_at": "2026-11-07",
                        }
                    ]
                }
            )
            checker = LocalSourceChecker(REPO_ROOT)
            chain(tmp, provider=provider, checker=checker)
            model = json.loads((Path(tmp) / "stage_3.model.json").read_text(encoding="utf-8"))
            first = model["leaves"][0]
            self.assertEqual(first["status"], "VERIFIZIERT")
            self.assertTrue(first["sources"][0]["checked"])

    def test_falsches_zitat_bleibt_unverifiziert(self) -> None:
        checker = LocalSourceChecker(REPO_ROOT)
        from core.prompt_optimizer.model import Source

        source = Source(tier=3, locator="repo:protocol/PROTOCOL.md", quote="Dieser Satz steht dort nicht.")
        checked = checker.check(source)
        self.assertFalse(checked.checked)
        self.assertFalse(checked.verified)

    def test_netzquelle_ohne_pruefung_gilt_nicht_als_verifiziert(self) -> None:
        checker = LocalSourceChecker(REPO_ROOT)
        from core.prompt_optimizer.model import Source

        source = Source(tier=2, locator="https://example.invalid/spec", quote="irgendwas")
        self.assertFalse(checker.check(source).verified)


class TestLockEnforcement(unittest.TestCase):
    def test_manipulierter_inhalt_bricht_die_sperre(self) -> None:
        doc = parse_draft(DRAFT)
        doc.stage = 1
        before = StageDocument.from_dict(doc.to_dict())
        mutated = StageDocument.from_dict(doc.to_dict())
        mutated.stage = 2
        mutated.features[0] = Feature(fid=mutated.features[0].fid, title="Erfundenes Feature", subsystem=mutated.features[0].subsystem)
        with self.assertRaises(LockViolation):
            enforce_lock(mutated, before, "content")

    def test_umbau_der_struktur_bricht_die_technik_sperre(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chain(tmp)
            one = Doc.from_dict(json.loads((Path(tmp) / "stage_1.model.json").read_text(encoding="utf-8")))
            two = Doc.from_dict(json.loads((Path(tmp) / "stage_2.model.json").read_text(encoding="utf-8")))
            two.contract = ["nur noch ein Satz"]
            with self.assertRaises(LockViolation):
                enforce_lock(two, one, "technique")

    def test_synthese_vertrag_ist_eigenstaendig(self) -> None:
        self.assertGreaterEqual(len(SYNTHESIS_CONTRACT), 4)


class TestNormalMode(unittest.TestCase):
    def test_single_pass_erzeugt_genau_ein_dokument(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            optimizer = PromptOptimizer(DRAFT, out_dir=tmp)
            result = optimizer.run_normal()
            self.assertEqual(result.artifact, ARTIFACT_NORMAL)
            self.assertIs(optimizer.mode, Mode.NORMAL)
            self.assertIn("<!-- prompt-optimizer-pass: 1-final; status: NORMAL -->", result.markdown)
            self.assertTrue((Path(tmp) / ARTIFACT_NORMAL).is_file())
            self.assertFalse((Path(tmp) / "stage_4_FINAL_MASTER_PROMPT.md").exists())

    def test_single_pass_beantwortet_alle_vier_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            optimizer = PromptOptimizer(SMALL_DRAFT, out_dir=tmp)
            markdown = optimizer.run_normal().markdown
            for index in (1, 2, 3, 4):
                self.assertIn(f"Hard Gate {index} —", markdown)
            self.assertIn("[F-01]", markdown)


class TestScorecardMath(unittest.TestCase):
    def test_kriterien_sind_auf_25_begrenzt(self) -> None:
        doc = parse_draft(DRAFT)
        body = "irgendein Text"
        content = measure_content(doc, body)
        technique = measure_technique(doc, body)
        self.assertTrue(all(0 <= value <= 25 for value in content.criteria))
        self.assertTrue(all(0 <= value <= 25 for value in technique.criteria))
        self.assertEqual(sum(content.criteria), content.points)
        self.assertEqual(sum(technique.criteria), technique.points)

    def test_fehlende_sections_kosten_topolgiepunkte(self) -> None:
        doc = parse_draft(DRAFT)
        body = "nur Prosa ohne Sektionen"
        technique = measure_technique(doc, body)
        self.assertLess(technique.criteria[0], 25)

    def test_duplikate_senken_signal_to_noise(self) -> None:
        doc = parse_draft(DRAFT)
        line = "Ein ausreichend langer Satz mit Inhalt fuer die Messung."
        unique = measure_technique(doc, "\n".join([line, line.replace("Satz", "Zeile")]))
        duplicated = measure_technique(doc, "\n".join([line] * 4))
        self.assertLess(duplicated.criteria[2], unique.criteria[2])

    def test_verifizierte_blaetter_heben_die_inhaltstiefe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, without = chain(tmp)
            with tempfile.TemporaryDirectory() as tmp2:
                provider = FixtureProvider(
                    {"R-01": [{"tier": 3, "locator": "repo:Makefile", "quote": "check: compile lint types test ui-test e2e"}]}
                )
                _, with_check = chain(tmp2, provider=provider, checker=LocalSourceChecker(REPO_ROOT))
                self.assertGreater(with_check[3].scorecard.content.after, without[3].scorecard.content.after)


class TestExpansion(unittest.TestCase):
    def test_jedes_subsystem_hat_alle_vier_gates(self) -> None:
        doc = expand_document(parse_draft(DRAFT), StructuralFiller())
        for subsystem in doc.subsystems:
            for key in ("G1", "G2", "G3", "G4"):
                answer = subsystem.gates[key]
                self.assertTrue(answer.items, (subsystem.sid, key))
                self.assertTrue(answer.anchor_count >= 1)

    def test_rohmaterial_ist_domaenenspezifisch(self) -> None:
        doc = expand_document(parse_draft(DRAFT), StructuralFiller())
        by_title = {subsystem.title: subsystem for subsystem in doc.subsystems}
        transport = by_title.get("Transport")
        self.assertIsNotNone(transport)
        joined = " ".join(transport.raw_material).casefold()
        self.assertIn("ringpuffer", joined)
        self.assertIn("byte-offset", joined)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
