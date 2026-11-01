"""Manus-Limb gegen einen gefaelschten Dienst. Kein Test spricht mit dem echten Manus."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from core.config import NeuConfig
from core.kernel import Kernel
from core.protocol import ErrorCode, Intent, Operations
from limbs import manus_limb
from limbs.manus_limb import TASK_DEFAULTS, ManusLimb, blocked_reason

from . import REPO_ROOT

API_KEY = "manus-test-key-5f3a91c2"
TASK_ID = "task_fake_0001"


class FakeManus(BaseHTTPRequestHandler):
    """Antwortet wie die API v2; Formate laut openapi_v2.json. ``answers`` ueberschreibt Einzelne."""

    calls: ClassVar[list[dict[str, Any]]] = []
    task: ClassVar[dict[str, Any]] = {}
    messages: ClassVar[list[dict[str, Any]]] = []
    artifacts: ClassVar[list[dict[str, Any]]] = []
    usage: ClassVar[list[dict[str, Any]]] = []
    answers: ClassVar[dict[str, list[Any]]] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls = []
        cls.task = {"id": TASK_ID, "status": "running", "has_running_background_jobs": False}
        cls.messages = []
        cls.artifacts = []
        cls.usage = []
        cls.answers = {}

    def _send(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self) -> None:
        parts = urlsplit(self.path)
        operation = parts.path.removeprefix("/v2/")
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        FakeManus.calls.append({"op": operation, "method": self.command, "query": parse_qs(parts.query), "body": body, "key": self.headers.get("x-manus-api-key")})

        queued = FakeManus.answers.get(operation)
        if queued:
            answer = queued.pop(0)
            if answer == "slow":
                time.sleep(1.2)
                return
            if isinstance(answer, int):
                self._send(answer, {"ok": False, "error": {"code": "rate_limited"}})
                return
            if isinstance(answer, tuple):
                self._send(answer[0], {"ok": False}, answer[1])
                return

        replies: dict[str, dict[str, Any]] = {
            "user.me": {"user_id": "u1"},
            "task.create": {"task_id": TASK_ID, "task_title": "t", "task_url": "https://manus.test/x"},
            "task.detail": {"task": FakeManus.task},
            "task.stop": {},
            "task.listMessages": {"task_id": TASK_ID, "messages": FakeManus.messages, "has_more": False},
            "artifact.list": {"data": FakeManus.artifacts, "has_more": False},
            "usage.list": {"data": FakeManus.usage, "has_more": False},
        }
        if operation in replies:
            self._send(200, {"ok": True, "request_id": "req_1", **replies[operation]})
        else:
            self._send(404, {"ok": False, "error": {"code": "not_found"}})

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *args: object) -> None:
        pass


class ManusLimbBase(unittest.TestCase):
    def setUp(self) -> None:
        FakeManus.reset()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeManus)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = Path(self.tmp.name)

        self.env = {
            "MANUS_API_BASE": f"http://127.0.0.1:{self.server.server_port}",
            "MANUS_API_KEY": API_KEY,
            "MANUS_BUDGET_RUN": "100",
            "MANUS_BUDGET_DAY": "500",
        }
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.config = NeuConfig.load(REPO_ROOT)
        self.operations = Operations.load(self.config.protocol_dir / "operations.json")
        self.kernel = Kernel(self.config, self.operations)
        self.limb = ManusLimb()
        self.limb.config = NeuConfig.load(REPO_ROOT, runtime_dir=self.runtime)

    def build(self, operation: str, **params: object) -> Intent:
        return self.kernel.build_intent(operation=operation, params=params, limb="manus", goal="Manus pruefen", iteration=1, max_iterations=1)

    def call(self, operation: str, **params: object):
        return self.limb.execute(self.build(operation, **params))

    def start(self) -> str:
        result = self.call("manus.start", prompt="Fasse den Markt zusammen", locale="de")
        self.assertEqual(result.status, "success", result.error)
        return result.output["run_id"]

    def status(self, run_id: str):
        """Fragt ab, ohne den Mindestabstand abzuwarten."""
        run = self.limb.runs.load(run_id, "manus")
        run["next_poll_s"] = 0.0
        self.limb.runs.save(run)
        return self.call("manus.status", run_id=run_id).output

    def ops(self) -> list[str]:
        return [call["op"] for call in FakeManus.calls]

    def stored(self) -> str:
        return "\n".join(p.read_text(encoding="utf-8") for p in self.runtime.rglob("*") if p.is_file())


class ErfolgTest(ManusLimbBase):
    def test_voller_lauf(self):
        FakeManus.task.update(credit_usage=12)
        run_id = self.start()
        self.assertEqual(self.status(run_id)["credits"], 12)

        FakeManus.task["status"] = "stopped"
        FakeManus.messages.extend(
            [
                {"id": "1", "type": "user_message", "user_message": {"content": "frage"}},
                {"id": "2", "type": "assistant_message", "assistant_message": {"content": "Antwort von Manus"}},
            ]
        )
        FakeManus.artifacts.extend(
            [
                {"id": "a1", "task_id": TASK_ID, "filename": "report.pdf", "type": "documents", "url": "https://files.test/report.pdf"},
                {"id": "a2", "task_id": "task_anderer", "filename": "fremd.pdf"},
            ]
        )
        self.assertEqual(self.status(run_id)["state"], "succeeded")

        output = self.call("manus.collect", run_id=run_id).output
        self.assertEqual(output["text"], "Antwort von Manus")
        self.assertEqual([item["id"] for item in output["artifacts"]], ["a1"])
        self.assertTrue(output["untrusted"])
        self.assertTrue(json.loads((self.runtime / "agents" / run_id / "result.json").read_text(encoding="utf-8"))["untrusted"])

    def test_auftrag_traegt_die_festen_vorgaben(self):
        self.start()
        sent = next(call for call in FakeManus.calls if call["op"] == "task.create")
        self.assertEqual(sent["body"], {"message": {"content": "Fasse den Markt zusammen"}, "locale": "de", **TASK_DEFAULTS})
        self.assertEqual(TASK_DEFAULTS, {"clear_connectors": True, "share_visibility": "private", "agent_profile": "lite", "interactive_mode": False})

    def test_aufrufer_kann_vorgaben_nicht_aendern(self):
        self.call("manus.start", prompt="x", share_visibility="public", connectors=["gmail"], project_id="p", agent_profile="max", locale="de;drop")
        sent = next(call for call in FakeManus.calls if call["op"] == "task.create")["body"]
        self.assertEqual(set(sent), {"message", *TASK_DEFAULTS})
        self.assertEqual(sent["share_visibility"], "private")

    def test_ping(self):
        self.assertEqual(self.call("manus.ping").output["service"], "running")

    def test_hintergrundarbeit_haelt_den_lauf_offen(self):
        run_id = self.start()
        FakeManus.task.update(status="stopped", has_running_background_jobs=True)
        self.assertEqual(self.status(run_id)["state"], "running")

    def test_mindestabstand_von_zehn_sekunden(self):
        run_id = self.start()
        self.status(run_id)
        before = self.ops().count("task.detail")
        output = self.call("manus.status", run_id=run_id).output
        self.assertEqual(self.ops().count("task.detail"), before)
        self.assertGreaterEqual(output["next_poll_after_s"], 9.0)

    def test_fehlerstatus_wird_gemeldet(self):
        run_id = self.start()
        FakeManus.task["status"] = "error"
        FakeManus.messages.append({"id": "9", "type": "error_message", "error_message": {"content": "kaputt"}})
        view = self.status(run_id)
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["error"], "kaputt")


class RueckfragenTest(ManusLimbBase):
    def waiting(self, event_type: str = "gmailSendAction") -> dict[str, Any]:
        run_id = self.start()
        FakeManus.task["status"] = "waiting"
        FakeManus.messages.append(
            {
                "id": "s1",
                "type": "status_update",
                "status_update": {
                    "agent_status": "waiting",
                    "status_detail": {"waiting_for_event_id": "e1", "waiting_for_event_type": event_type, "waiting_description": "Mail senden"},
                },
            }
        )
        return self.status(run_id)

    def test_rueckfrage_geht_an_den_menschen(self):
        view = self.waiting()
        self.assertEqual(view["state"], "waiting")
        self.assertEqual(view["confirmation"], {"event_type": "gmailSendAction", "description": "Mail senden", "needs_human": True})

    def test_nie_automatisch_bestaetigen(self):
        for event_type in ("gmailSendAction", "apiHighCreditNotice", "terminalExecute"):
            with self.subTest(event_type):
                FakeManus.reset()
                self.waiting(event_type)
                self.assertNotIn("task.confirmAction", self.ops())
                self.assertNotIn("task.sendMessage", self.ops())

    def test_limb_kennt_keine_bestaetigung(self):
        self.assertEqual(sorted(self.limb.handlers()), ["manus.collect", "manus.ping", "manus.start", "manus.status", "manus.stop", "manus.usage"])
        source = (REPO_ROOT / "limbs" / "manus_limb.py").read_text(encoding="utf-8")
        self.assertNotIn('"task.confirmAction"', source)
        self.assertNotIn('"task.sendMessage"', source)


class FehlerTest(ManusLimbBase):
    def test_429_beim_status_wartet_und_erholt_sich(self):
        run_id = self.start()
        FakeManus.answers["task.detail"] = [429]
        first = self.status(run_id)
        self.assertEqual(first["state"], "running")
        self.assertGreaterEqual(first["next_poll_after_s"], 19.0)
        self.assertEqual(self.status(run_id)["state"], "running")
        self.assertEqual(self.limb.runs.load(run_id, "manus")["backoff_s"], 0.0)

    def test_backoff_waechst_und_achtet_retry_after(self):
        run_id = self.start()
        FakeManus.answers["task.detail"] = [429, 429, (429, {"Retry-After": "120"})]
        self.status(run_id)
        first = self.limb.runs.load(run_id, "manus")["backoff_s"]
        self.status(run_id)
        second = self.limb.runs.load(run_id, "manus")["backoff_s"]
        self.assertGreater(second, first)
        self.status(run_id)
        self.assertGreaterEqual(self.limb.runs.load(run_id, "manus")["backoff_s"], 120.0)

    def test_429_beim_start_wird_nicht_wiederholt(self):
        FakeManus.answers["task.create"] = [429]
        result = self.call("manus.start", prompt="x")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, ErrorCode.IO)
        self.assertEqual(self.ops().count("task.create"), 1)

    def test_ausfall_beim_status_haelt_den_lauf(self):
        run_id = self.start()
        FakeManus.answers["task.detail"] = [503]
        view = self.status(run_id)
        self.assertEqual(view["state"], "running")
        self.assertTrue(view["degraded"])
        self.assertNotIn("degraded", self.status(run_id))

    def test_toter_dienst_laesst_den_lauf_bestehen(self):
        run_id = self.start()
        self.server.shutdown()
        self.server.server_close()
        view = self.status(run_id)
        self.assertEqual(view["state"], "running")
        self.assertTrue(view["degraded"])

    def test_ausfall_beim_start_schlaegt_fehl(self):
        FakeManus.answers["usage.list"] = [502]
        result = self.call("manus.start", prompt="x")
        self.assertEqual(result.status, "failed")
        self.assertNotIn("task.create", self.ops())

    def test_antwort_ohne_json_gilt_als_ausfall(self):
        run_id = self.start()
        with mock.patch.object(manus_limb, "_OPENER") as opener:
            opener.open.return_value.__enter__.return_value.read.return_value = b"<html>"
            view = self.status(run_id)
        self.assertTrue(view["degraded"])

    def test_timeout_der_anfrage_gilt_als_ausfall(self):
        run_id = self.start()
        FakeManus.answers["task.detail"] = ["slow"]
        with mock.patch.object(ManusLimb, "client", staticmethod(lambda: manus_limb.ManusClient(self.env["MANUS_API_BASE"], API_KEY, timeout_s=0.2))):
            view = self.status(run_id)
        self.assertEqual(view["state"], "running")
        self.assertTrue(view["degraded"])

    def test_laufzeit_stoppt_den_auftrag(self):
        run_id = self.start()
        run = self.limb.runs.load(run_id, "manus")
        run["started_s"] -= 7200
        self.limb.runs.save(run)
        view = self.status(run_id)
        self.assertEqual(view["state"], "timeout")
        self.assertIn("task.stop", self.ops())
        self.assertTrue(view["stop_confirmed"])

    def test_laufzeit_bei_ausfall_meldet_den_unbestaetigten_stopp(self):
        run_id = self.start()
        run = self.limb.runs.load(run_id, "manus")
        run["started_s"] -= 7200
        self.limb.runs.save(run)
        FakeManus.answers["task.detail"] = [503]
        FakeManus.answers["task.stop"] = [503]
        view = self.status(run_id)
        self.assertEqual(view["state"], "timeout")
        self.assertFalse(view["stop_confirmed"])

    def test_stop_vom_aufrufer(self):
        run_id = self.start()
        self.assertEqual(self.call("manus.stop", run_id=run_id).output["state"], "stopped")
        stopped = next(call for call in FakeManus.calls if call["op"] == "task.stop")
        self.assertEqual(stopped["body"], {"task_id": TASK_ID})

    def test_unbekannter_lauf(self):
        result = self.call("manus.status", run_id="run_00000000000000000000")
        self.assertEqual(result.error_code, ErrorCode.TARGET_NOT_FOUND)


class BudgetTest(ManusLimbBase):
    def test_laufbudget_stoppt(self):
        run_id = self.start()
        FakeManus.task["credit_usage"] = 100
        view = self.status(run_id)
        self.assertEqual(view["state"], "budget_stopped")
        self.assertIn("task.stop", self.ops())
        self.assertIn("Laufbudget", view["error"])

    def test_tagesbudget_stoppt_laufenden_lauf(self):
        run_id = self.start()
        FakeManus.usage.append({"task_id": "x", "credits": -500, "created_at": int(time.time()), "type": "cost"})
        self.assertEqual(self.status(run_id)["state"], "budget_stopped")

    def test_tagesbudget_verhindert_den_start(self):
        FakeManus.usage.append({"task_id": "x", "credits": -500, "created_at": int(time.time()), "type": "cost"})
        result = self.call("manus.start", prompt="x")
        self.assertEqual(result.error_code, ErrorCode.BUDGET_EXHAUSTED)
        self.assertNotIn("task.create", self.ops())

    def test_verbrauch_rechnet_rueckerstattung_und_ignoriert_alte_tage(self):
        now = int(time.time())
        FakeManus.usage.extend(
            [
                {"task_id": "a", "credits": -30, "created_at": now, "type": "cost"},
                {"task_id": "a", "credits": 10, "created_at": now, "type": "refund"},
                {"task_id": "g", "credits": 9000, "created_at": now, "type": "grant"},
                {"task_id": "b", "credits": -999, "created_at": now - 3 * 86400, "type": "cost"},
            ]
        )
        self.assertEqual(self.call("manus.usage").output["credits_today"], 20)

    def test_ohne_budget_startet_nichts(self):
        for name in ("MANUS_BUDGET_RUN", "MANUS_BUDGET_DAY"):
            for value in ("", "0", "viel"):
                with self.subTest(name=name, value=value), mock.patch.dict(os.environ, {name: value}):
                    result = self.call("manus.start", prompt="x")
                    self.assertEqual(result.error_code, ErrorCode.BUDGET_EXHAUSTED)
        self.assertNotIn("task.create", self.ops())


class SendefilterTest(ManusLimbBase):
    def test_gesperrte_inhalte(self):
        blocked = [
            "siehe runtime/agents/x",
            "lies workspace/sigma/app",
            "lies workspace/obsidian/Inbox/a.md",
            "die Datei .env",
            "frontend/.env.local",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "key sk-abcdefghijklmnopqrstuvwx",
            "ghp_abcdefghijklmnopqrstuvwxyz",
            "KRAKEN_API_KEY=abcdef12",
            f"der Key ist {API_KEY}",
        ]
        for text in blocked:
            with self.subTest(text):
                result = self.call("manus.start", prompt=text)
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.error_code, ErrorCode.POLICY_DENIED)
        self.assertEqual(self.ops(), [])

    def test_harmlose_texte_passieren(self):
        for text in ("Runtime von 3 Stunden", "Wie funktioniert environment.yml?", "Schreibe ueber Tokens in LLMs", "workspace aufraeumen"):
            with self.subTest(text):
                self.assertEqual(blocked_reason(text, {}), "")

    def test_wert_jeder_geheimen_variable_wird_erkannt(self):
        self.assertIn("SIGMA_OPERATOR_TOKEN", blocked_reason("x abcdef0123 y", {"SIGMA_OPERATOR_TOKEN": "abcdef0123"}))
        self.assertEqual(blocked_reason("x abcdef0123 y", {"HOSTNAME": "abcdef0123"}), "")

    def test_zu_langer_auftrag(self):
        self.assertEqual(self.call("manus.start", prompt="x" * 16_001).error_code, ErrorCode.SCHEMA_INVALID)


class SperreTest(ManusLimbBase):
    def test_echter_host_bleibt_gesperrt(self):
        for base in ("", "https://api.manus.ai", "https://evil.example"):
            with self.subTest(base), mock.patch.dict(os.environ, {"MANUS_API_BASE": base}), mock.patch.object(manus_limb, "_OPENER") as opener:
                for operation, params in (("manus.ping", {}), ("manus.start", {"prompt": "x"}), ("manus.usage", {})):
                    result = self.call(operation, **params)
                    self.assertEqual(result.status, "failed")
                    self.assertEqual(result.error_code, ErrorCode.POLICY_DENIED)
                opener.open.assert_not_called()

    def test_stop_eines_laufs_ruft_den_echten_host_nicht(self):
        run_id = self.start()
        with mock.patch.dict(os.environ, {"MANUS_API_BASE": "https://api.manus.ai"}), mock.patch.object(manus_limb, "_OPENER") as opener:
            view = self.call("manus.stop", run_id=run_id).output
        opener.open.assert_not_called()
        self.assertFalse(view["stop_confirmed"])

    def test_register_haelt_den_limb_inaktiv(self):
        entry = json.loads((REPO_ROOT / "limbs" / "registry.json").read_text(encoding="utf-8"))["limbs"]["manus"]
        self.assertEqual(entry["status"], "planned")
        self.assertEqual(sorted(entry["operations"]), sorted(self.limb.handlers()))
        self.assertEqual(self.operations.spec("manus.start").risk, "external")

    def test_ohne_key_kein_aufruf(self):
        with mock.patch.dict(os.environ, {"MANUS_API_KEY": ""}):
            self.assertEqual(self.call("manus.ping").error_code, ErrorCode.POLICY_DENIED)
        self.assertEqual(self.ops(), [])


class KeyTest(ManusLimbBase):
    def test_key_steht_nur_im_header(self):
        run_id = self.start()
        FakeManus.task.update(status="stopped")
        self.status(run_id)
        self.call("manus.collect", run_id=run_id)
        self.assertTrue(all(call["key"] == API_KEY for call in FakeManus.calls))
        self.assertNotIn(API_KEY, json.dumps([{**call, "key": None} for call in FakeManus.calls]))

    def test_key_steht_in_keinem_artefakt_und_keiner_ausgabe(self):
        FakeManus.messages.append({"id": "2", "type": "assistant_message", "assistant_message": {"content": f"Echo: {API_KEY}"}})
        FakeManus.task.update(status="stopped")
        run_id = self.start()
        view = self.status(run_id)
        collected = self.call("manus.collect", run_id=run_id)
        self.assertNotIn(API_KEY, json.dumps(view))
        self.assertNotIn(API_KEY, collected.to_json())
        self.assertIn("[REDACTED]", collected.output["text"])
        self.assertNotIn(API_KEY, self.stored())

    def test_kein_redirect_mit_key(self):
        class Target(FakeManus):
            hits: ClassVar[list[str]] = []

            def _handle(self) -> None:
                Target.hits.append(self.headers.get("x-manus-api-key") or "")
                self._send(200, {"ok": True})

            do_GET = _handle
            do_POST = _handle

        target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
        threading.Thread(target=target.serve_forever, daemon=True).start()
        self.addCleanup(target.server_close)
        self.addCleanup(target.shutdown)
        FakeManus.answers["user.me"] = [(302, {"Location": f"http://127.0.0.1:{target.server_port}/steal"})]
        self.assertEqual(self.call("manus.ping").status, "failed")
        self.assertEqual(Target.hits, [])

    def test_echter_prozess_ohne_key_in_stdout_und_stderr(self):
        intent = self.build("manus.start", prompt="Fasse zusammen")
        path = self.runtime / "intent.json"
        path.write_text(intent.to_json(), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(REPO_ROOT / "limbs" / "manus_limb.py"), "--intent", str(path)],
            env={**os.environ, **self.env},
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        output = json.loads(done.stdout)
        self.assertEqual(output["status"], "success", output["error"])
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(self.config.runtime_dir / "agents" / output["output"]["run_id"])], check=False))
        self.assertNotIn(API_KEY, done.stdout + done.stderr)
        self.assertIn("task.create", self.ops())


if __name__ == "__main__":
    unittest.main()
