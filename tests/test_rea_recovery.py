"""Akzeptanztest: die Rekonstruktion muss das Original reproduzieren.

Zwei Ebenen:

* **Immer (ohne REA-Lauf):** Der Python-Port des Spiels wird gegen das
  Original-Bundle (``app/cli.cjs``) verglichen. Die Konstanten sind die Werte,
  die aus der REA-Evidence zurueckgewonnen wurden -- hier festgehalten, damit
  ein Drift zwischen Fixture, Port und Bericht auffaellt, auch ohne Netz und
  ohne Installation.
* **Wenn eine Evidence vorliegt:** Das Gate-Skript muss aus der Evidence
  dieselben Konstanten ziehen und alle Faelle bestehen.

Der Test ist damit die Absicherung des Meilensteins "bereit fuer ein kleines
Spiel" -- nicht die Behauptung, dass eine Analyse stattgefunden hat.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest

from . import REPO_ROOT

SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rea_recover_orbit import (  # noqa: E402  (Pfad-Bootstrap oben ist Absicht)
    DEFAULT_EVIDENCE,
    DEFAULT_GAME,
    DEFAULT_NATIVE,
    OrbitDodge,
    compare,
    load_evidence,
    native_check,
    recover_constants,
)

#: Aus der Evidence zurueckgewonnene Konstanten (Rollenname -> Wert). Der
#: Differenztest unten beweist, dass sie das Verhalten vollstaendig erklaeren.
RECOVERED = {
    "width": 480,
    "height": 640,
    "gravity": 0.28,
    "thrust": 0.55,
    "drag": 0.992,
    "maxSpeed": 6.5,
    "shipRadius": 9,
    "asteroidRadius": 14,
    "spawnEveryMs": 900,
    "comboWindowMs": 1400,
    "comboStep": 0.35,
    "maxCombo": 5,
    "startLives": 3,
}


@unittest.skipUnless(shutil.which("node"), "Node.js wird fuer den Differenztest gebraucht")
class TestPortReproduziertOriginal(unittest.TestCase):
    def setUp(self) -> None:
        self.port = OrbitDodge(RECOVERED)

    def test_port_trifft_das_original_ueber_mehrere_seeds(self):
        results = compare(self.port, DEFAULT_GAME, [1, 2, 42, 1337], [300, 900])
        failures = [item for item in results if not item["ok"]]
        self.assertEqual(failures, [], f"Port weicht ab: {failures}")

    def test_port_trifft_auch_kurze_und_lange_laeufe(self):
        results = compare(self.port, DEFAULT_GAME, [20260101], [60, 1500])
        self.assertTrue(all(item["ok"] for item in results), results)

    def test_mulberry32_ist_bitgenau(self):
        """Der PRNG ist die Stelle, an der ein Port typischerweise kippt."""
        rng = self.port._mulberry32(1337)
        values = [round(rng(), 12) for _ in range(3)]
        node = shutil.which("node")
        script = (
            "let a=1337>>>0;function n(){a=(a+0x6d2b79f5)>>>0;let t=a;"
            "t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);"
            "return ((t^(t>>>14))>>>0)/4294967296;}"
            "console.log(JSON.stringify([n(),n(),n()]));"
        )
        done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        expected = [round(value, 12) for value in json.loads(done.stdout)]
        self.assertEqual(values, expected)

    def test_native_endformel_stimmt(self):
        for item in native_check(DEFAULT_NATIVE, self.port):
            self.assertTrue(item["ok"], item)


class TestEvidenceGate(unittest.TestCase):
    """Laeuft nur, wenn der Subagent wirklich analysiert hat (workspace/ ist gitignored)."""

    def setUp(self) -> None:
        if not DEFAULT_EVIDENCE.is_file():
            self.skipTest(f"keine Evidence vorhanden: {DEFAULT_EVIDENCE}")

    def test_evidence_liefert_dieselben_konstanten(self):
        values = recover_constants(load_evidence(DEFAULT_EVIDENCE))["values"]
        for name, expected in RECOVERED.items():
            self.assertIn(name, values, f"{name} fehlt in der Evidence")
            self.assertEqual(values[name], expected, f"{name} weicht ab")

    @unittest.skipUnless(shutil.which("node"), "Node.js fehlt")
    def test_gate_skript_besteht(self):
        done = subprocess.run(
            [sys.executable, str(SCRIPTS / "rea_recover_orbit.py"), "--json"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])
        report = json.loads(done.stdout)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["failures"], 0)
        self.assertGreaterEqual(report["cases"], 9)


if __name__ == "__main__":
    unittest.main()
