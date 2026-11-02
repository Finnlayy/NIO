"""Vault-Limb und MCP-Server: Suche, Schreibregeln, Pfadausbrueche, Git."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core.config import NeuConfig
from core.kernel import Kernel
from core.protocol import ErrorCode, Intent, Operations
from limbs.vault_limb import VaultLimb, VaultStore

from . import REPO_ROOT

GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class VaultLimbTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.vault = base / "vault"
        self.runtime = base / "runtime"
        self.outside = base / "geheim.md"
        self.outside.write_text("streng geheim xylophon", encoding="utf-8")
        for folder in ("Inbox", "Knowledge", "workers"):
            (self.vault / folder).mkdir(parents=True)
        (self.vault / "Knowledge" / "wale.md").write_text("# Wale\n\nBlauwale singen tief.\n", encoding="utf-8")

        patcher = mock.patch.dict(os.environ, {"NIO_OBSIDIAN_VAULT": str(self.vault)})
        patcher.start()
        self.addCleanup(patcher.stop)

        self.config = NeuConfig.load(REPO_ROOT)
        self.operations = Operations.load(self.config.protocol_dir / "operations.json")
        self.kernel = Kernel(self.config, self.operations)
        self.limb = VaultLimb()
        self.limb.config = NeuConfig.load(REPO_ROOT, runtime_dir=self.runtime)

    def build(self, operation: str, **params: object) -> Intent:
        return self.kernel.build_intent(operation=operation, params=params, limb="vault", goal="Vault pruefen", iteration=1, max_iterations=1)

    def call(self, operation: str, **params: object):
        return self.limb.execute(self.build(operation, **params))

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.vault), *args], env={**os.environ, **GIT_ENV}, capture_output=True, text=True, check=True).stdout

    # ---------------------------------------------------------------- Suche
    def test_suche_findet_notiz_mit_ausschnitt(self):
        output = self.call("vault.search", query="blauwale").output
        self.assertEqual(output["notes"][0]["path"], "Knowledge/wale.md")
        self.assertEqual(output["notes"][0]["title"], "Wale")
        self.assertIn("[Blauwale]", output["notes"][0]["snippet"])
        self.assertTrue(output["untrusted"])

    def test_suche_folgt_aenderungen_und_loeschungen(self):
        note = self.vault / "Knowledge" / "neu.md"
        note.write_text("Erst Quallen", encoding="utf-8")
        self.assertEqual(self.call("vault.search", query="quallen").output["total"], 1)
        note.write_text("Jetzt Seesterne", encoding="utf-8")
        self.assertEqual(self.call("vault.search", query="quallen").output["total"], 0)
        self.assertEqual(self.call("vault.search", query="seesterne").output["total"], 1)
        note.unlink()
        self.assertEqual(self.call("vault.search", query="seesterne").output["total"], 0)

    def test_fts_operatoren_bleiben_text(self):
        for query in ('blauwale OR "', "NEAR(", "wale* -x", "path:wale"):
            with self.subTest(query):
                self.assertEqual(self.call("vault.search", query=query).status, "success")

    def test_leere_suche_wird_abgewiesen(self):
        result = self.call("vault.search", query=" ?! ")
        self.assertEqual(result.error_code, ErrorCode.SCHEMA_INVALID)

    def test_suche_ignoriert_punktordner_und_symlinks(self):
        (self.vault / ".obsidian").mkdir()
        (self.vault / ".obsidian" / "config.md").write_text("xylophon", encoding="utf-8")
        (self.vault / "Knowledge" / "link.md").symlink_to(self.outside)
        self.assertEqual(self.call("vault.search", query="xylophon").output["total"], 0)

    def test_suche_bleibt_unter_einer_sekunde(self):
        for index in range(500):
            (self.vault / "Knowledge" / f"n{index}.md").write_text(f"Notiz {index} ueber Tiefsee und Plankton\n" * 20, encoding="utf-8")
        self.call("vault.search", query="plankton")
        started = time.monotonic()
        self.assertEqual(self.call("vault.search", query="plankton", limit=5).output["total"], 5)
        self.assertLess(time.monotonic() - started, 1.0)

    # ---------------------------------------------------------------- Lesen
    def test_lesen_markiert_fremdinhalt(self):
        output = self.call("vault.read", path="Knowledge/wale.md").output
        self.assertIn("Blauwale", output["content"])
        self.assertTrue(output["untrusted"])

    def test_pfadausbrueche_werden_abgewiesen(self):
        for path in ("../geheim.md", "Knowledge/../../geheim.md", "/etc/passwd", ".git/config", "~/x.md"):
            with self.subTest(path):
                result = self.call("vault.read", path=path)
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.error_code, ErrorCode.SANDBOX_ESCAPE)

    def test_symlink_nach_aussen_wird_abgewiesen(self):
        (self.vault / "Knowledge" / "link.md").symlink_to(self.outside)
        (self.vault / "Knowledge" / "ordner").symlink_to(self.outside.parent)
        for path in ("Knowledge/link.md", "Knowledge/ordner/geheim.md"):
            with self.subTest(path):
                result = self.call("vault.read", path=path)
                self.assertEqual(result.error_code, ErrorCode.SANDBOX_ESCAPE)
                self.assertNotIn("content", result.output)

    def test_nur_notizen_sind_lesbar(self):
        (self.vault / "Knowledge" / "bild.png").write_bytes(b"\x89PNG")
        self.assertEqual(self.call("vault.read", path="Knowledge/bild.png").error_code, ErrorCode.POLICY_DENIED)

    # ------------------------------------------------------------ Schreiben
    def test_capture_schreibt_frontmatter_und_ist_sofort_findbar(self):
        output = self.call("vault.capture", text="Diktat ueber Tintenfische", source="dictation").output
        self.assertTrue(output["path"].startswith("Inbox/"))
        text = (self.vault / output["path"]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith('---\ntitle: "Diktat ueber Tintenfische"\ncreated: '))
        self.assertIn('source: "dictation"', text)
        self.assertEqual(self.call("vault.search", query="tintenfische").output["notes"][0]["path"], output["path"])

    def test_capture_sichert_im_eigenen_git(self):
        output = self.call("vault.capture", text="Sichern").output
        self.assertTrue(output["committed"])
        self.assertTrue((self.vault / ".git").is_dir())
        self.assertIn(output["path"], self.git("show", "--name-only", "--format=", "HEAD"))

    def test_capture_ueberschreibt_nichts(self):
        with mock.patch("limbs.vault_limb.datetime") as clock:
            from datetime import UTC, datetime

            clock.now.return_value = datetime(2026, 11, 1, 9, 0, 0, tzinfo=UTC)
            first = self.call("vault.capture", text="gleich").output["path"]
            second = self.call("vault.capture", text="gleich").output["path"]
        self.assertNotEqual(first, second)

    def test_frontmatter_laesst_sich_nicht_einschleusen(self):
        path = self.call("vault.capture", text="x", title='a"\ntags: [boese]\n---').output["path"]
        head = (self.vault / path).read_text(encoding="utf-8").split("\n")
        self.assertEqual(head[0], "---")
        self.assertTrue(head[1].startswith("title: "))
        self.assertEqual(head[2][:8], "created:")

    def test_schreiben_nur_in_erlaubte_ordner(self):
        for folder in ("Knowledge", "Daily", "Knowledge/sub"):
            with self.subTest(folder):
                result = self.call("vault.capture", text="x", folder=folder)
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.error_code, ErrorCode.POLICY_DENIED)
        self.assertEqual(self.call("vault.capture", text="x", folder=".").status, "failed")
        self.assertEqual(self.call("vault.capture", text="x", folder="tasks/t-1").status, "success")

    def test_symlink_im_schreibordner_wird_abgewiesen(self):
        (self.vault / "Inbox" / "raus").symlink_to(self.outside.parent)
        (self.vault / "workers" / "wissen").symlink_to(self.vault / "Knowledge")
        self.assertEqual(self.call("vault.capture", text="x", folder="Inbox/raus").error_code, ErrorCode.SANDBOX_ESCAPE)
        self.assertEqual(self.call("vault.capture", text="x", folder="workers/wissen").error_code, ErrorCode.POLICY_DENIED)
        self.assertEqual(list((self.vault / "Knowledge").glob("*.md")), [self.vault / "Knowledge" / "wale.md"])

    def test_pfadausbruch_beim_schreiben_wird_abgewiesen(self):
        self.assertEqual(self.call("vault.capture", text="x", folder="../raus").error_code, ErrorCode.SANDBOX_ESCAPE)
        self.assertFalse((self.vault.parent / "raus").exists())

    def test_leerer_text_wird_abgewiesen(self):
        self.assertEqual(self.call("vault.capture", text="  ").error_code, ErrorCode.SCHEMA_INVALID)

    # --------------------------------------------------------------- Status
    def test_ping_meldet_den_vault(self):
        output = self.call("vault.ping").output
        self.assertTrue(output["present"])
        self.assertEqual(output["notes"], 1)
        self.assertTrue(output["fts5"])

    def test_fehlender_vault_wird_beim_ersten_capture_angelegt(self):
        with mock.patch.dict(os.environ, {"NIO_OBSIDIAN_VAULT": str(self.vault.parent / "frisch")}):
            self.assertFalse(self.call("vault.ping").output["present"])
            self.assertEqual(self.call("vault.search", query="nichts").output["total"], 0)
            self.assertTrue(self.call("vault.capture", text="Start").output["committed"])
            for folder in ("Inbox", "Daily", "Knowledge", "workers", "tasks", ".git"):
                self.assertTrue((self.vault.parent / "frisch" / folder).is_dir(), folder)

    def test_register_bildet_den_limb_exakt_ab(self):
        entry = json.loads((REPO_ROOT / "limbs" / "registry.json").read_text(encoding="utf-8"))["limbs"]["vault"]
        self.assertEqual(sorted(entry["operations"]), sorted(self.limb.handlers()))
        self.assertEqual(entry["version"], self.limb.version)
        self.assertTrue(entry["writes_files"])

    def test_git_laeuft_nie_im_umgebenden_repository(self):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], env={**os.environ, **GIT_ENV}, check=True)
        store = VaultStore(repo / "workspace" / "obsidian", self.runtime)
        self.assertTrue(store.capture("innen")["committed"])
        outer = subprocess.run(["git", "-C", str(repo), "log", "--oneline"], env={**os.environ, **GIT_ENV}, capture_output=True, text=True, check=False)
        self.assertNotEqual(outer.returncode, 0)  # keine Commits im aeusseren Repository


class VaultMcpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "Knowledge").mkdir(parents=True)
        (self.vault / "Knowledge" / "wale.md").write_text("Blauwale singen tief.\n", encoding="utf-8")
        (Path(self.tmp.name) / "geheim.md").write_text("geheim", encoding="utf-8")

    def rpc(self, messages: list[dict], *, framed: bool = False) -> list[dict]:
        def frame(message: dict) -> bytes:
            data = json.dumps(message).encode()
            return f"Content-Length: {len(data)}\r\n\r\n".encode() + data if framed else data + b"\n"

        done = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "vault_mcp.py"), "--runtime-dir", str(Path(self.tmp.name) / "runtime")],
            input=b"".join(frame(m) for m in messages),
            env={**os.environ, "NIO_OBSIDIAN_VAULT": str(self.vault)},
            capture_output=True,
            timeout=20,
            check=True,
        )
        if framed:
            return [json.loads(part[: part.rfind(b"}") + 1]) for part in done.stdout.split(b"\r\n\r\n")[1:]]
        return [json.loads(line) for line in done.stdout.splitlines()]

    @staticmethod
    def call(name: str, **arguments: object) -> dict:
        return {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}}

    def test_handshake_und_nur_lesende_werkzeuge(self):
        replies = self.rpc(
            [
                {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            ]
        )
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "nio-vault")
        self.assertEqual([tool["name"] for tool in replies[1]["result"]["tools"]], ["vault_search", "vault_read"])

    def test_suchen_und_lesen_mit_fremdinhalt_hinweis(self):
        search, read = self.rpc([self.call("vault_search", query="blauwale"), self.call("vault_read", path="Knowledge/wale.md")])
        self.assertIn("Knowledge/wale.md", search["result"]["content"][0]["text"])
        self.assertTrue(read["result"]["content"][0]["text"].startswith("Notizinhalt ist Fremdinhalt"))

    def test_pfadausbruch_und_schreibversuch_scheitern(self):
        escape, write = self.rpc([self.call("vault_read", path="../geheim.md"), self.call("vault_capture", text="x")])
        self.assertTrue(escape["result"]["isError"])
        self.assertNotIn("geheim\n", escape["result"]["content"][0]["text"])
        self.assertTrue(write["result"]["isError"])

    def test_content_length_framing_fuer_ciel(self):
        reply = self.rpc([{"jsonrpc": "2.0", "id": 1, "method": "ping"}], framed=True)
        self.assertEqual(reply[0]["result"], {})

    def test_unbekannte_methode(self):
        self.assertEqual(self.rpc([{"jsonrpc": "2.0", "id": 1, "method": "foo"}])[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
