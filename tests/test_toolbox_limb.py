"""Toolbox-Limb: Katalog, Suche, Detail und Register-Abbild."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.config import NeuConfig
from core.kernel import Kernel
from core.protocol import ErrorCode, Intent, Operations
from limbs.toolbox_limb import ToolboxLimb

from . import REPO_ROOT

LEAF_COUNT = len(list((REPO_ROOT / "docs" / "knowledge" / "tradingview-mcp" / "tools").glob("*.md")))


class ToolboxLimbTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = NeuConfig.load(REPO_ROOT)
        self.operations = Operations.load(self.config.protocol_dir / "operations.json")
        self.kernel = Kernel(self.config, self.operations)
        self.limb = ToolboxLimb()
        self.op_count = len(json.loads((REPO_ROOT / "protocol" / "operations.json").read_text(encoding="utf-8"))["operations"])

    def build(self, operation: str, **params: object) -> Intent:
        return self.kernel.build_intent(
            operation=operation,
            params=params,
            limb="toolbox",
            goal="Werkzeugkiste pruefen",
            iteration=1,
            max_iterations=1,
        )

    def call(self, operation: str, **params: object):
        return self.limb.execute(self.build(operation, **params))

    def test_katalog_enthaelt_alle_operationen_und_leafs(self):
        output = self.call("toolbox.ping").output
        self.assertEqual(output["tools"], self.op_count + LEAF_COUNT)
        self.assertEqual(output["sources"], {"neu": self.op_count, "tradingview-mcp": LEAF_COUNT})

    def test_suche_liefert_nur_kurzzeilen(self):
        output = self.call("toolbox.search", query="ohlcv").output
        self.assertEqual(output["tools"][0]["tool"], "get_ohlcv")
        self.assertNotIn("detail", output["tools"][0])

    def test_suche_begrenzt_und_filtert(self):
        output = self.call("toolbox.search", source="tradingview-mcp", access="write", limit=3).output
        self.assertEqual(len(output["tools"]), 3)
        self.assertTrue(output["truncated"])
        self.assertEqual({tool["access"] for tool in output["tools"]}, {"write"})

    def test_schreibende_operationen_sind_markiert(self):
        tools = self.call("toolbox.search", query="fs.write_file").output["tools"]
        self.assertEqual(tools[0]["access"], "write")

    def test_describe_liefert_das_volle_leaf(self):
        output = self.call("toolbox.describe", tool="create_alert").output
        self.assertEqual(output["access"], "write")
        self.assertIn("nur nach ausdrücklicher Freigabe", output["detail"])

    def test_describe_kennt_neu_operationen(self):
        output = self.call("toolbox.describe", tool="fs.read_file").output
        self.assertEqual(output["detail"]["risk"], "read")

    def test_unbekanntes_werkzeug_schlaegt_klassifiziert_fehl(self):
        result = self.call("toolbox.describe", tool="gibt_es_nicht")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, ErrorCode.TARGET_NOT_FOUND)

    def test_neues_leaf_landet_ohne_codeaenderung_im_katalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "protocol").mkdir()
            (root / "protocol" / "operations.json").write_text('{"operations": {}}', encoding="utf-8")
            tools = root / "docs" / "knowledge" / "demo" / "tools"
            tools.mkdir(parents=True)
            (tools / "demo_tool.md").write_text(
                "---\ntool: demo_tool\ngroup: demo\naccess: read-only\n---\n\n# `demo_tool`\n\nDemo · nur lesend\n\nTut etwas.\n",
                encoding="utf-8",
            )
            limb = ToolboxLimb(root=root)
            output = limb.execute(self.build("toolbox.search", query="demo")).output
        self.assertEqual(output["tools"][0]["summary"], "Tut etwas.")

    def test_register_bildet_den_limb_exakt_ab(self):
        entry = json.loads((REPO_ROOT / "limbs" / "registry.json").read_text(encoding="utf-8"))["limbs"]["toolbox"]
        self.assertEqual(sorted(entry["operations"]), sorted(self.limb.handlers()))
        self.assertEqual(entry["version"], self.limb.version)
        self.assertFalse(entry["writes_files"])


if __name__ == "__main__":
    unittest.main()
