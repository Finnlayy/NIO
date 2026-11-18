"""Artifact-Exporter (tools/sync/nio_artifact_exporter.py): Snapshot, Idempotenz, Hash."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from . import REPO_ROOT

_SPEC = importlib.util.spec_from_file_location("nio_artifact_exporter", REPO_ROOT / "tools" / "sync" / "nio_artifact_exporter.py")
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
NioArtifactExporter = _MOD.NioArtifactExporter


class ArtifactExporterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="neu-test-exporter-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _write(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def test_ohne_module_kein_export(self):
        self.assertIsNone(NioArtifactExporter(repo_root=str(self.root)).export_snapshot())

    def test_export_default_dir_liegt_unter_repo_root(self):
        self._write("orchestrator/kanban/dispatcher.py", "x = 1\n")
        out = NioArtifactExporter(repo_root=str(self.root)).export_snapshot("run-1")
        self.assertEqual(out, self.root / "obsidian_vault" / "exports" / "NIO_Latest_Production_Snapshot.md")
        text = out.read_text(encoding="utf-8")
        self.assertIn("`orchestrator/kanban/dispatcher.py`", text)
        self.assertIn("```python\nx = 1\n```", text)
        manifest = json.loads((out.parent / "export_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["exported_modules"], 1)
        self.assertEqual(manifest["trigger_run_id"], "run-1")

    def test_unveraendert_ist_idempotent_aenderung_exportiert_neu(self):
        self._write("orchestrator/kanban/dispatcher.py", "x = 1\n")
        exp = NioArtifactExporter(repo_root=str(self.root))
        self.assertIsNotNone(exp.export_snapshot())
        self.assertIsNone(exp.export_snapshot())
        self._write("orchestrator/kanban/dispatcher.py", "x = 2\n")
        self.assertIsNotNone(exp.export_snapshot())

    def test_geloeschter_snapshot_wird_neu_erzeugt(self):
        self._write("orchestrator/kanban/dispatcher.py", "x = 1\n")
        exp = NioArtifactExporter(repo_root=str(self.root))
        out = exp.export_snapshot()
        out.unlink()
        self.assertEqual(exp.export_snapshot(), out)

    def test_kaputtes_manifest_fuehrt_zu_neuexport(self):
        self._write("orchestrator/kanban/dispatcher.py", "x = 1\n")
        exp = NioArtifactExporter(repo_root=str(self.root))
        exp.export_snapshot()
        exp.manifest_path.write_text("{kaputt", encoding="utf-8")
        self.assertIsNotNone(exp.export_snapshot())

    def test_hash_unterscheidet_verschobene_inhaltsgrenzen(self):
        exp = NioArtifactExporter(repo_root=str(self.root))
        self._write("core/obsidian_memory.py", "ab")
        self._write("limbs/fastmcp_bridge.py", "c")
        files = [self.root / "core/obsidian_memory.py", self.root / "limbs/fastmcp_bridge.py"]
        h1 = exp._compute_bundle_hash(files)
        self._write("core/obsidian_memory.py", "a")
        self._write("limbs/fastmcp_bridge.py", "bc")
        self.assertNotEqual(h1, exp._compute_bundle_hash(files))

    def test_backticks_im_inhalt_brechen_den_codeblock_nicht(self):
        self._write("frontend/src/apollo/commands.ts", "const s = `a ```x``` b`;\n")
        out = NioArtifactExporter(repo_root=str(self.root)).export_snapshot()
        self.assertIn("````typescript\n", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
