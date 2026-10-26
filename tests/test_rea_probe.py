"""Tests fuer die Rekonstruktion eines fremden Spiel-Bundles.

Der eigentliche Nachweis (``scripts/rea_probe_tetris.py``) braucht Netz, Node
und eine REA-Installation im Subagenten -- das gehoert nicht in die
Standard-Suite. Hier steht der Teil, der ohne all das falsch sein kann:
Rollen-Keys lesen, die Baustein-Tabelle aus einem Bundle erkennen, und die
Spielregeln, die der Port nachbildet (Raeumung, Punkte, Tempo, PRNG).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rea_probe_tetris import (  # noqa: E402  (Pfad-Bootstrap ist Absicht)
    Mulberry32,
    PieceTable,
    Tetris,
    cross_check,
    js_round,
    recover_piece_roles,
    recover_pieces,
    role_name,
)

SYNTHETIC = (
    'var i={size:4,blocks:[3840,8738,240,17476],color:"cyan"},'
    'o={size:2,blocks:[52224,52224,52224,52224],color:"yellow"};'
    "var pieces=[];function randomPiece(){pieces.length==0&&(pieces=[i,i,o,o])}"
)


def table() -> PieceTable:
    return PieceTable(
        order=["i", "o"],
        sizes={"i": 4, "o": 2},
        masks={"i": [0x0F00, 0x2222, 0x00F0, 0x4444], "o": [0xCC00] * 4},
        colors={"i": "cyan", "o": "yellow"},
    )


def model(**kwargs) -> Tetris:
    base = {"nx": 10, "ny": 20, "start": 0.6, "decrement": 0.005, "minimum": 0.1, "seed": 7, "table": table()}
    base.update(kwargs)
    return Tetris(**base)  # type: ignore[arg-type]


class TestRoleKeys(unittest.TestCase):
    def test_eigenschaft_gewinnt_gegen_bindung(self):
        self.assertEqual(role_name("literal:scope:program:0:6258:binding:speed:property:decrement:0.005"), "decrement")
        self.assertEqual(role_name("literal:scope:program:0:6258:binding:speed:property:start:0.6"), "start")
        self.assertEqual(role_name("literal:scope:program:0:6258:binding:nx:binding:10"), "nx")
        self.assertEqual(role_name("literal:scope:function:61:4100:binding:b:property:r:48"), "r")

    def test_ohne_namen_kein_raten(self):
        self.assertIsNone(role_name("literal:scope:program:0:6258:binding:10"))


class TestPieceTable(unittest.TestCase):
    def test_tabelle_aus_dem_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "game.min.js"
            bundle.write_text(SYNTHETIC, encoding="utf-8")
            recovered = recover_pieces(bundle)
        self.assertEqual(recovered.order, ["i", "o"])
        self.assertEqual(recovered.sizes, {"i": 4, "o": 2})
        self.assertEqual(recovered.masks["i"], [0x0F00, 0x2222, 0x00F0, 0x4444])
        self.assertEqual(recovered.colors["o"], "yellow")

    def test_evidence_und_artefakt_muessen_uebereinstimmen(self):
        evidence = {"normalized_result": {"semantic_graph": {"nodes": [
            {"kind": "literal", "identity": {"role_key": "literal:scope:program:0:1:binding:o:property:size:2"},
             "properties": {"value": 2}},
            {"kind": "literal", "identity": {"role_key": "literal:scope:program:0:1:binding:o:property:color:'yellow'"},
             "properties": {"value": "yellow"}},
        ]}}}
        report = cross_check(table(), recover_piece_roles(evidence))
        self.assertEqual(report["mismatches"], 0)
        self.assertGreaterEqual(report["checked"], 2)

    def test_widerspruch_wird_abgelehnt(self):
        evidence = {"normalized_result": {"semantic_graph": {"nodes": [
            {"kind": "literal", "identity": {"role_key": "literal:scope:program:0:1:binding:o:property:size:3"},
             "properties": {"value": 3}},
        ]}}}
        with self.assertRaises(SystemExit):
            cross_check(table(), recover_piece_roles(evidence))


class TestSpielregeln(unittest.TestCase):
    def test_prng_ist_bitgleich_zu_js(self):
        rng = Mulberry32(7)
        self.assertEqual(
            [rng() for _ in range(5)],
            [0.011704753153026104, 0.06195825757458806, 0.97690763277933,
             0.6990287057124078, 0.5214452685322613],
        )

    def test_js_round_rundet_halbe_auf(self):
        self.assertEqual(js_round(2.5), 3)
        self.assertEqual(js_round(2.4), 2)
        self.assertEqual(js_round(-2.5), -2)

    def test_eine_reihe_gibt_hundert(self):
        game = model()
        for x in range(10):
            game.set_block(x, 19, "i")
        game.remove_lines()
        self.assertEqual(game.score, 100)
        self.assertEqual(game.rows, 1)
        self.assertIsNone(game.get_block(0, 19))

    def test_vier_reihen_geben_achthundert(self):
        game = model()
        for y in range(16, 20):
            for x in range(10):
                game.set_block(x, y, "i")
        game.remove_lines()
        self.assertEqual(game.rows, 4)
        self.assertEqual(game.score, 800)
        self.assertEqual(game.step, 0.58)  # 0.6 - 0.005*4

    def test_reihe_null_wird_nie_geprueft(self):
        """Eigenheit des Originals: die Schleife laeuft nur bis y>0."""
        game = model()
        for x in range(10):
            game.set_block(x, 0, "i")
        game.remove_lines()
        self.assertEqual(game.rows, 0)
        self.assertEqual(game.score, 0)
        self.assertEqual(game.get_block(5, 0), "i")

    def test_tempo_ist_nach_oben_begrenzt(self):
        game = model()
        game.set_rows(10)
        self.assertAlmostEqual(game.step, 0.55)
        game.set_rows(500)
        self.assertEqual(game.step, 0.1)

    def test_kollision_an_den_raendern(self):
        game = model()
        self.assertTrue(game.can_place("o", 0, 18, 0))
        self.assertFalse(game.can_place("o", 0, 19, 0))  # 2 hoch -> ragt unten hinaus
        self.assertFalse(game.can_place("o", 9, 0, 0))   # 2 breit -> ragt rechts hinaus
        self.assertFalse(game.can_place("i", 0, 19, 1))  # 4 hoch -> ragt unten hinaus

    def test_landung_und_digest_sind_stabil(self):
        game = model()
        game.set_block(0, 19, "i")
        self.assertEqual(game.landing_y("o", 0, 0), 17)
        self.assertEqual(game.digest(), game.digest())
        self.assertEqual(len(game.digest()), 16)

    def test_plan_beginnt_mit_rotation_dann_bewegung(self):
        game = model()
        game.current = game.random_piece()
        plan = game.plan_for(game.current.key)
        self.assertTrue(plan)
        self.assertEqual(set(plan) - {0, 1, 2, 3}, set())

    def test_zustand_ist_json_faehig(self):
        game = model()
        game.play()
        json.dumps({"score": game.score, "rows": game.rows, "board": game.digest()})


if __name__ == "__main__":
    unittest.main()
