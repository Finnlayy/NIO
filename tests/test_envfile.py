"""Betreiber-Datei ~/.config/nio/nio.env wird beim Start automatisch geladen."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.envfile import load_env_file, parse_env_text


class EnvFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "nio.env"

    def tearDown(self) -> None:
        self._dir.cleanup()

    def _write(self, text: str, mode: int = 0o600) -> None:
        self.path.write_text(text, encoding="utf-8")
        self.path.chmod(mode)

    def test_parse_ignores_comments_and_strips_quotes(self) -> None:
        parsed = parse_env_text('# x\n\nA=1\nexport B="zwei"\nC=\'drei\'\nkaputt\n')
        self.assertEqual(parsed, {"A": "1", "B": "zwei", "C": "drei"})

    def test_fills_missing_keys_and_keeps_existing(self) -> None:
        self._write("NIO_KANBAN_API_TOKEN=aus-datei\nNIO_APPROVAL_KEY=k\n")
        env = {"NIO_ENV_FILE": str(self.path), "NIO_APPROVAL_KEY": "aus-shell"}
        loaded = load_env_file(env)
        self.assertEqual(loaded, ["NIO_KANBAN_API_TOKEN"])
        self.assertEqual(env["NIO_KANBAN_API_TOKEN"], "aus-datei")
        self.assertEqual(env["NIO_APPROVAL_KEY"], "aus-shell")

    def test_skips_checkout_bound_paths(self) -> None:
        self._write("NEU_ROOT=/alt\nNIO_REPO_ROOT=/alt\nNIO_PYTHON=/alt/python\nX=1\n")
        env = {"NIO_ENV_FILE": str(self.path)}
        self.assertEqual(load_env_file(env), ["X"])
        self.assertNotIn("NEU_ROOT", env)

    def test_refuses_group_or_world_readable_file(self) -> None:
        self._write("X=1\n", mode=0o644)
        env = {"NIO_ENV_FILE": str(self.path)}
        self.assertEqual(load_env_file(env), [])
        self.assertNotIn("X", env)

    def test_missing_file_and_off_switch_load_nothing(self) -> None:
        self.assertEqual(load_env_file({"NIO_ENV_FILE": str(self.path)}), [])
        self._write("X=1\n")
        env = {"NIO_ENV_FILE": "off"}
        self.assertEqual(load_env_file(env), [])

    def test_cli_main_loads_only_on_real_start(self) -> None:
        from orchestrator import cli

        with patch.object(cli, "load_env_file") as loader, patch.dict(os.environ, {}, clear=False):
            with self.assertRaises(SystemExit):
                cli.main(["--help"])
            loader.assert_not_called()
            with patch("sys.argv", ["neu", "--help"]), self.assertRaises(SystemExit):
                cli.main()
            loader.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
