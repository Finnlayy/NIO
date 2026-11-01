"""Speech-Limb gegen einen gefaelschten Dienst: Erfolg, Ausfall, Timeout, Lokal-Pflicht."""

from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from unittest import mock

from core.config import NeuConfig
from core.kernel import Kernel
from core.protocol import ErrorCode, Intent, Operations
from limbs import speech_limb
from limbs.speech_limb import SpeechLimb

from . import REPO_ROOT


class FakeSpeaches(BaseHTTPRequestHandler):
    """Antwortet wie speaches; ``mode`` steuert die Fehlpfade."""

    mode = "ok"
    requests: ClassVar[list[bytes]] = []

    def _reply(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._reply(200, b"OK")

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        FakeSpeaches.requests.append(self.headers["Content-Type"].encode() + b"\n" + body)
        if FakeSpeaches.mode == "error":
            self._reply(500, b"boom")
        elif FakeSpeaches.mode == "garbage":
            self._reply(200, b"<html>")
        elif FakeSpeaches.mode == "redirect":
            self.send_response(307)
            self.send_header("Location", "http://198.51.100.1/steal")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif FakeSpeaches.mode == "slow":
            time.sleep(2.5)
        else:
            self._reply(200, json.dumps({"text": "  Apollo, Status  "}).encode())

    def log_message(self, *args: object) -> None:
        pass


class SpeechLimbTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeSpeaches.mode = "ok"
        FakeSpeaches.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSpeaches)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

        self.config = NeuConfig.load(REPO_ROOT)
        self.operations = Operations.load(self.config.protocol_dir / "operations.json")
        self.kernel = Kernel(self.config, self.operations)
        self.limb = SpeechLimb()

        self.config.workspace_dir.mkdir(exist_ok=True)
        self.audio_dir = Path(tempfile.mkdtemp(prefix="speech-test-", dir=self.config.workspace_dir))
        self.addCleanup(shutil.rmtree, self.audio_dir, True)
        self.audio = self.audio_dir / "notiz.ogg"
        self.audio.write_bytes(b"OggS-fake-audio")
        self.rel_audio = f"{self.audio_dir.name}/notiz.ogg"

        patcher = mock.patch.dict(os.environ, {"STT_ENDPOINT_URL": f"http://127.0.0.1:{self.server.server_port}/v1/audio/transcriptions"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def build(self, operation: str, **params: object) -> Intent:
        return self.kernel.build_intent(operation=operation, params=params, limb="speech", goal="Sprache pruefen", iteration=1, max_iterations=1)

    def call(self, operation: str, **params: object):
        return self.limb.execute(self.build(operation, **params))

    def test_transkript_kommt_als_fremdinhalt_zurueck(self):
        result = self.call("speech.transcribe", path=self.rel_audio)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.output["text"], "Apollo, Status")
        self.assertTrue(result.output["untrusted"])

    def test_ogg_geht_unveraendert_an_die_engine(self):
        self.call("speech.transcribe", path=self.rel_audio, language="en")
        sent = FakeSpeaches.requests[0]
        self.assertIn(b"OggS-fake-audio", sent)
        self.assertIn(b"Content-Type: audio/ogg", sent)
        self.assertIn(b'name="language"\r\n\r\nen', sent)
        self.assertIn(b'name="vad_filter"\r\n\r\ntrue', sent)
        self.assertIn(b"Apollo", sent)

    def test_ausfall_ergibt_fehler_statt_text(self):
        self.server.shutdown()
        self.server.server_close()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with mock.patch.dict(os.environ, {"STT_ENDPOINT_URL": f"http://127.0.0.1:{port}/v1/audio/transcriptions"}):
            result = self.call("speech.transcribe", path=self.rel_audio)
            ping = self.call("speech.ping")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, ErrorCode.IO)
        self.assertNotIn("text", result.output)
        self.assertEqual(ping.status, "success")
        self.assertEqual(ping.output["engine"], "offline")

    def test_fehlerantworten_erfinden_keinen_text(self):
        for mode in ("error", "garbage"):
            FakeSpeaches.mode = mode
            with self.subTest(mode):
                result = self.call("speech.transcribe", path=self.rel_audio)
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.error_code, ErrorCode.IO)
                self.assertNotIn("text", result.output)

    def test_timeout_wird_gemeldet(self):
        FakeSpeaches.mode = "slow"
        with mock.patch.object(speech_limb, "TRANSCRIBE_TIMEOUT_S", 0.3):
            with mock.patch.object(speech_limb.LimbContext, "remaining_s", return_value=None):
                result = self.call("speech.transcribe", path=self.rel_audio)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, ErrorCode.IO)

    def test_weiterleitung_wird_nicht_verfolgt(self):
        FakeSpeaches.mode = "redirect"
        result = self.call("speech.transcribe", path=self.rel_audio)
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(FakeSpeaches.requests), 1)

    def test_fremder_host_wird_abgewiesen(self):
        with mock.patch.dict(os.environ, {"STT_ENDPOINT_URL": "https://stt.example.com/v1/audio/transcriptions"}):
            result = self.call("speech.transcribe", path=self.rel_audio)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, ErrorCode.POLICY_DENIED)
        self.assertEqual(FakeSpeaches.requests, [])

    def test_symlink_aus_der_sandbox_wird_abgewiesen(self):
        intent = self.build("speech.transcribe", path=f"{self.audio_dir.name}/raus.ogg")
        (self.audio_dir / "raus.ogg").symlink_to(REPO_ROOT / "neu.config.json")
        result = self.limb.execute(intent)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.error_code, ErrorCode.SANDBOX_ESCAPE)
        self.assertEqual(FakeSpeaches.requests, [])

    def test_unbekanntes_format_wird_abgewiesen(self):
        (self.audio_dir / "text.txt").write_text("kein audio", encoding="utf-8")
        result = self.call("speech.transcribe", path=f"{self.audio_dir.name}/text.txt")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, ErrorCode.SCHEMA_INVALID)

    def test_ping_meldet_laufende_engine(self):
        output = self.call("speech.ping").output
        self.assertEqual(output["engine"], "running")

    def test_register_bildet_den_limb_exakt_ab(self):
        entry = json.loads((REPO_ROOT / "limbs" / "registry.json").read_text(encoding="utf-8"))["limbs"]["speech"]
        self.assertEqual(sorted(entry["operations"]), sorted(self.limb.handlers()))
        self.assertEqual(entry["version"], self.limb.version)
        self.assertFalse(entry["writes_files"])
        for operation in entry["operations"]:
            self.assertEqual(self.operations.spec(operation).implemented_by, ("speech",))

    def test_speaches_ist_fest_gepinnt(self):
        text = (REPO_ROOT / "docs" / "SPEECH.md").read_text(encoding="utf-8")
        self.assertIn("speaches:0.8.3-cpu@sha256:", text)
        self.assertNotIn("speaches:latest", text)


if __name__ == "__main__":
    unittest.main()
