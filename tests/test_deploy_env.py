"""Deploy: Jeder Dienst bekommt nur seine eigene Umgebungsdatei.

``deploy/write_env.sh`` schreibt ``kanban.env`` und ``apollo.env``. Apollo darf
weder das Operator-Token noch den Freigabeschluessel sehen; eine alte
gemeinsame ``nio.env`` wird ohne Verlust von Geheimnissen aufgeteilt.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from . import REPO_ROOT

WRITE_ENV = REPO_ROOT / "deploy" / "write_env.sh"
UNITS = REPO_ROOT / "deploy" / "systemd"
FORBIDDEN_IN_APOLLO = ("NIO_KANBAN_API_TOKEN", "NIO_APPROVAL_KEY")


def parse(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out


@unittest.skipUnless(shutil.which("bash"), "bash fehlt")
class WriteEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config = Path(self._tmp.name) / "nio"
        self.vault = Path(self._tmp.name) / "vault"

    def run_script(self) -> tuple[dict[str, str], dict[str, str]]:
        subprocess.run(
            ["bash", str(WRITE_ENV), str(REPO_ROOT), str(self.config), str(self.vault)],
            check=True, capture_output=True, text=True, timeout=60,
        )
        return parse(self.config / "kanban.env"), parse(self.config / "apollo.env")

    def assert_private(self, path: Path) -> None:
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path)

    def test_fresh_install_splits_secrets(self) -> None:
        kanban, apollo = self.run_script()
        for key in ("NIO_KANBAN_API_TOKEN", "NIO_APPROVAL_KEY", "NIO_KANBAN_APOLLO_TOKEN"):
            self.assertGreaterEqual(len(kanban[key]), 32, key)
        for key in FORBIDDEN_IN_APOLLO:
            self.assertNotIn(key, apollo)
            self.assertNotIn(kanban[key], (self.config / "apollo.env").read_text())
        self.assertEqual(apollo["NIO_KANBAN_APOLLO_TOKEN"], kanban["NIO_KANBAN_APOLLO_TOKEN"])
        self.assertNotEqual(kanban["NIO_KANBAN_APOLLO_TOKEN"], kanban["NIO_KANBAN_API_TOKEN"])
        self.assertRegex(apollo["NIO_APOLLO_APPROVAL_PIN"], r"^\d{8}$")
        self.assertNotIn("NIO_APOLLO_APPROVAL_PIN", kanban)
        self.assertEqual(kanban["NIO_REPO_ROOT"], str(REPO_ROOT))
        self.assertEqual(apollo["NIO_OBSIDIAN_VAULT"], str(self.vault))
        self.assert_private(self.config / "kanban.env")
        self.assert_private(self.config / "apollo.env")
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o700)

    def test_rerun_keeps_secrets(self) -> None:
        first = self.run_script()
        self.assertEqual(self.run_script(), first)

    def test_hand_added_backend_secrets_are_removed_from_apollo(self) -> None:
        self.run_script()
        with (self.config / "apollo.env").open("a") as handle:
            handle.write("NIO_KANBAN_API_TOKEN=leak\nNIO_APPROVAL_KEY=leak\n")
        _, apollo = self.run_script()
        for key in FORBIDDEN_IN_APOLLO:
            self.assertNotIn(key, apollo)

    def test_legacy_nio_env_is_migrated(self) -> None:
        self.config.mkdir(mode=0o700)
        legacy = self.config / "nio.env"
        legacy.write_text(
            "NIO_KANBAN_API_TOKEN=old-operator-token-000000000000000\n"
            "NIO_APPROVAL_KEY=old-approval-key-0000000000000000000\n"
            "NIO_APOLLO_APPROVAL_PIN=12345678\n"
            "FREELLMAPI_KEY=gateway-key\n"
            "NIO_OBSIDIAN_VAULT=/srv/vault\n"
        )
        kanban, apollo = self.run_script()
        self.assertEqual(kanban["NIO_KANBAN_API_TOKEN"], "old-operator-token-000000000000000")
        self.assertEqual(kanban["NIO_APPROVAL_KEY"], "old-approval-key-0000000000000000000")
        self.assertEqual(apollo["NIO_APOLLO_APPROVAL_PIN"], "12345678")
        self.assertEqual(apollo["FREELLMAPI_KEY"], "gateway-key")
        self.assertEqual(apollo["NIO_OBSIDIAN_VAULT"], "/srv/vault")
        for key in FORBIDDEN_IN_APOLLO:
            self.assertNotIn(key, apollo)
        self.assertFalse(legacy.exists())
        self.assert_private(self.config / "nio.env.migriert")


class UnitTests(unittest.TestCase):
    def test_each_service_reads_only_its_own_file(self) -> None:
        apollo = (UNITS / "nio-apollo.service").read_text()
        kanban = (UNITS / "nio-kanban.service").read_text()
        self.assertIn("EnvironmentFile=%h/.config/nio/apollo.env", apollo)
        self.assertIn("EnvironmentFile=%h/.config/nio/kanban.env", kanban)
        for unit in (apollo, kanban):
            self.assertNotIn("nio.env", unit)
        self.assertNotIn("kanban.env", apollo)

    def test_apollo_template_has_no_backend_secrets(self) -> None:
        template = parse(REPO_ROOT / "deploy" / "apollo.env.example")
        for key in FORBIDDEN_IN_APOLLO:
            self.assertNotIn(key, template)


if __name__ == "__main__":
    unittest.main()
