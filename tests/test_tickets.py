"""Freigabe-Tickets: Signatur, Bindung, Ablauf, Einmaligkeit, Register und Wege zum Ausstellen."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from pathlib import Path
from unittest import mock

from core.config import NeuConfig
from core.kernel import Kernel
from core.policy import Policy
from core.protocol import (
    ErrorCode,
    Intent,
    Operations,
    ProtocolError,
    format_timestamp,
    hash_intent,
    issue_ticket,
    sign_ticket,
    ticket_marker,
    utc_now,
)
from orchestrator.cli import main as neu_main
from orchestrator.runner import Orchestrator

from . import REPO_ROOT

KEY = "test-schluessel"
PROBE = "tests/_ticket_probe.txt"


def gated_body(**overrides):
    body = {
        "protocol": "neu/intent",
        "version": "1.2",
        "intent_id": "int_20260101T000000Z_abcdef",
        "trace_id": "int_20260101T000000Z_abcdef",
        "created_at": "2026-01-01T00:00:00Z",
        "source": {"role": "core", "node_id": "core.kernel"},
        "target": {"limb": "bootstrap"},
        "job": {"job_id": "job_20260101T000000Z_abcdef", "iteration": 1, "max_iterations": 1},
        "timer": {"mode": "deadline", "deadline_s": 20.0},
        "task": {
            "operation": "fs.write_file",
            "params": {"path": PROBE, "content": "x", "mode": "overwrite"},
        },
        "elevation": {
            "level": "repo_write",
            "reason": "Testfreigabe fuer genau diesen Auftrag.",
            "requested_paths": [PROBE],
        },
        "constraints": {"sandbox_root": ".", "dry_run": True},
    }
    body.update(overrides)
    return body


class TicketCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="neu-ticket-")
        tmp = Path(self._tmp.name)
        self.config = NeuConfig.load(REPO_ROOT, runtime_dir=tmp / "runtime", workspace_dir=tmp / "workspace")
        self.config.ensure_dirs()
        self.operations = Operations.load(self.config.protocol_dir / "operations.json")
        self.policy = Policy(self.config, self.operations)
        env = mock.patch.dict(os.environ, {"NIO_APPROVAL_KEY": KEY})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self._tmp.cleanup)

    def parse(self, body) -> Intent:
        return Intent.from_dict(body, operations=self.operations)

    def signed(self, body=None, *, key=KEY, ttl=900) -> dict:
        body = body or gated_body()
        issued = issue_ticket(key, self.parse(body), ttl)
        out = json.loads(json.dumps(body))
        out["elevation"].update(ticket=issued["ticket"], expires_at=issued["expires_at"], approved_by="human")
        return out

    def assertDenied(self, body) -> None:
        decision = self.policy.check(self.parse(body))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, ErrorCode.TICKET_INVALID)


class TestPruefung(TicketCase):
    def test_gueltiges_ticket_passiert(self):
        self.assertTrue(self.policy.check(self.parse(self.signed())).allowed)

    def test_pruefen_verbraucht_nicht(self):
        intent = self.parse(self.signed())
        self.assertTrue(self.policy.check(intent).allowed)
        self.assertTrue(self.policy.check(intent).allowed)

    def test_ohne_ticket(self):
        self.assertDenied(gated_body())

    def test_mensch_ohne_ticket_ist_kein_beweis(self):
        body = gated_body()
        body["elevation"]["approved_by"] = "human"
        self.assertDenied(body)

    def test_gefaelscht(self):
        body = self.signed()
        body["elevation"]["ticket"] = "0" * 64
        self.assertDenied(body)

    def test_fremder_schluessel(self):
        self.assertDenied(self.signed(key="anderer-schluessel"))

    def test_abgelaufen(self):
        body = gated_body()
        expires = format_timestamp(utc_now() - timedelta(seconds=1))
        ticket = sign_ticket(KEY, hash_intent(self.parse(body).to_dict()), "fs.write_file", expires)
        body["elevation"].update(ticket=ticket, expires_at=expires)
        self.assertDenied(body)

    def test_ablauf_verlaengert_macht_das_ticket_ungueltig(self):
        body = self.signed()
        body["elevation"]["expires_at"] = "2099-01-01T00:00:00Z"
        self.assertDenied(body)

    def test_anderer_auftrag(self):
        body = self.signed()
        body["task"]["params"]["content"] = "anderer Inhalt"
        self.assertDenied(body)

    def test_verbrauchte_marke(self):
        body = self.signed()
        marker = ticket_marker(self.config.runtime_dir, body["elevation"]["ticket"])
        marker.parent.mkdir(parents=True)
        marker.touch()
        self.assertDenied(body)

    def test_schluessel_fehlt(self):
        body = self.signed()
        with mock.patch.dict(os.environ):
            del os.environ["NIO_APPROVAL_KEY"]
            self.assertDenied(body)

    def test_limb_laufzeit_braucht_keinen_schluessel(self):
        intent = self.parse(self.signed())
        with mock.patch.dict(os.environ):
            del os.environ["NIO_APPROVAL_KEY"]
            self.assertTrue(self.policy.check_runtime(intent).allowed)

    def test_ticket_auf_freier_operation(self):
        body = gated_body(
            target={"limb": "echo"},
            task={"operation": "sys.echo", "params": {"message": "x"}},
            elevation={"level": "none", "ticket": "a" * 64},
            constraints={},
        )
        self.assertDenied(body)


class TestTicketFormat(TicketCase):
    def test_fremdzeichen_werden_beim_parsen_abgewiesen(self):
        for ticket in ("../../x", "A" * 64, "a" * 63, "a" * 64 + "\n"):
            body = gated_body()
            body["elevation"]["ticket"] = ticket
            with self.subTest(ticket=ticket), self.assertRaises(ProtocolError):
                self.parse(body)

    def test_marke_bleibt_im_ordner(self):
        marker = ticket_marker(Path("/x/runtime"), "../../boese")
        self.assertEqual(marker.parent, Path("/x/runtime/approvals/used"))
        self.assertRegex(marker.name, r"^[0-9a-f]{64}$")

    def test_laufzeit_ist_begrenzt(self):
        for ttl in (0, 3601):
            with self.subTest(ttl=ttl), self.assertRaises(ProtocolError):
                issue_ticket(KEY, self.parse(gated_body()), ttl)


class TestRegister(unittest.TestCase):
    def write(self, tmp: Path, body: dict) -> Path:
        path = tmp / "operations.json"
        path.write_text(json.dumps({"operations": {"x.y": body}}), encoding="utf-8")
        return path

    def test_register_prueft_risiko_und_schluessel(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            self.assertEqual(Operations.load(self.write(tmp, {"risk": "external"})).spec("x.y").risk, "external")
            for body in ({"risk": "gross"}, {}, {"risk": "read", "riks": "high"}):
                with self.subTest(body=body), self.assertRaises(ProtocolError):
                    Operations.load(self.write(tmp, body))


class TestEinmaligkeit(TicketCase):
    def test_orchestrator_verbraucht_genau_einmal(self):
        orch = Orchestrator(self.config, quiet=True)
        self.addCleanup(lambda: Path(REPO_ROOT, PROBE).unlink(missing_ok=True))
        body = self.signed()

        first = orch.dispatch(self.parse(body))
        self.assertTrue(ticket_marker(self.config.runtime_dir, body["elevation"]["ticket"]).exists())
        self.assertNotEqual((first.result.error or {}).get("code"), ErrorCode.TICKET_INVALID)

        second = orch.dispatch(self.parse(body))
        self.assertEqual(second.result.error["code"], ErrorCode.TICKET_INVALID)

    def test_marke_nicht_schreibbar_startet_keinen_limb(self):
        orch = Orchestrator(self.config, quiet=True)
        (self.config.runtime_dir / "approvals").write_text("kein Ordner", encoding="utf-8")
        attempt = orch.dispatch(self.parse(self.signed()))
        self.assertEqual(attempt.result.error["code"], ErrorCode.TICKET_INVALID)


class TestAusloeser(TicketCase):
    def test_hohes_risiko_passt_nicht_in_einen_ausloeser(self):
        kernel = Kernel(self.config, self.operations)
        trigger = {"id": "spaeter", "action": "check", "every_s": 1.0, "payload": {"operation": "fs.delete", "limb": "bootstrap"}}
        with self.assertRaises(ProtocolError) as ctx:
            kernel.build_intent(goal="Ausloeser", operation="sys.echo", params={"message": "x"}, limb="echo", schedule=[trigger])
        self.assertEqual(ctx.exception.code, ErrorCode.TRIGGER_INVALID)
        self.assertIn(ErrorCode.TICKET_INVALID, str(ctx.exception))


class TestCli(TicketCase):
    def run_cli(self, *argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out), redirect_stderr(err):
            code = neu_main(["--runtime-dir", str(self.config.runtime_dir), *argv])
        return code, out.getvalue(), err.getvalue()

    def test_approve_stellt_aus_und_protokolliert_ohne_ticket(self):
        path = Path(self._tmp.name) / "intent.json"
        path.write_text(json.dumps(gated_body()), encoding="utf-8")
        code, out, _ = self.run_cli("approve", str(path), "--ttl-seconds", "60")
        self.assertEqual(code, 0)
        issued = json.loads(out)
        body = gated_body()
        body["elevation"].update(ticket=issued["ticket"], expires_at=issued["expires_at"])
        self.assertTrue(self.policy.check(self.parse(body)).allowed)
        audit = (self.config.runtime_dir / "approvals" / "issued.jsonl").read_text(encoding="utf-8")
        self.assertIn(body["intent_id"], audit)
        self.assertNotIn(issued["ticket"], audit)

    def test_approve_ohne_schluessel(self):
        with mock.patch.dict(os.environ):
            del os.environ["NIO_APPROVAL_KEY"]
            code, _, _ = self.run_cli("approve", "-", stdin=json.dumps(gated_body()))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
