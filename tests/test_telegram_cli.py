import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator.cli import build_parser, main
from orchestrator.telegram import cli as tg_cli
from orchestrator.telegram.client import FakeTelegramClient
from orchestrator.telegram.models import LoginState, Suggestion, SuggestionStatus


class TestCli(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        env = {
            "NEU_ROOT": self.td.name,
            "NIO_KANBAN_WORKSPACE": str(Path(self.td.name) / "ws"),
            "NIO_OBSIDIAN_VAULT": str(Path(self.td.name) / "v"),
        }
        patcher = mock.patch.dict("os.environ", env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = FakeTelegramClient()
        self.client.fake_names["@bot"] = 20
        self.login = LoginState.AUTHORIZED
        real = tg_cli.build_telegram_runtime

        async def build(config, **kw):
            # Jedes Kommando schliesst seinen Client wieder.
            self.client.state = self.login
            return await real(config, client=self.client, **kw)

        patcher = mock.patch.object(tg_cli, "build_telegram_runtime", build)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--json", "telegram", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_setup_flow(self):
        self.assertEqual(self.run_cli("monitor", "add", "10")[0], 0)
        self.assertEqual(json.loads(self.run_cli("allow", "add", "@bot")[1]), {"peer": 20})
        self.assertEqual(self.run_cli("pair", "10", "@bot")[0], 0)
        self.assertEqual(json.loads(self.run_cli("monitor", "ls")[1]), [10])
        self.assertEqual(json.loads(self.run_cli("allow", "ls")[1]), [20])
        self.assertEqual(json.loads(self.run_cli("pairings")[1]), [{"source": 10, "target": 20}])
        self.assertEqual(self.run_cli("allow", "rm", "20")[0], 0)
        self.assertEqual(json.loads(self.run_cli("allow", "ls")[1]), [])

    def test_gather_and_signals_need_login_only_when_online(self):
        self.login = LoginState.DISCONNECTED
        code, _, err = self.run_cli("gather")
        self.assertEqual(code, 1)
        self.assertIn("telegram login", err)
        self.assertEqual(json.loads(self.run_cli("signals", "ls")[1]), [])

    def test_errors_become_exit_1(self):
        code, _, err = self.run_cli("suggestions", "dismiss", "none")
        self.assertEqual(code, 1)
        self.assertIn("nicht gefunden", err)
        self.assertEqual(self.run_cli("allow", "add", "@nobody")[0], 1)

    def test_suggestion_flow(self):
        self.run_cli("allow", "add", "20")

        async def seed(args, tg):
            await tg.store.add_suggestion(
                Suggestion(
                    "s", 10, 20, "/glint BTC BULLISH 10.0", 1, "rules", SuggestionStatus.PENDING, "2026-01-01T12:00:00.000Z", None, None
                )
            )
            return 0

        tg_cli._run(seed)(mock.Mock())
        self.assertEqual(json.loads(self.run_cli("suggestions", "ls", "--status", "pending")[1])[0]["id"], "s")
        self.assertEqual(json.loads(self.run_cli("suggestions", "approve", "s")[1])["status"], "sent")
        self.assertEqual(self.client.sent, [(20, "/glint BTC BULLISH 10.0")])

    def test_approval_decide(self):
        async def seed(args, tg):
            print((await tg.approvals.request("Deploy?", "")).id)
            return 0

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tg_cli._run(seed)(mock.Mock())
        self.assertEqual(json.loads(self.run_cli("approvals", "decide", out.getvalue().strip(), "reject")[1])["status"], "rejected")
        self.assertEqual(json.loads(self.run_cli("approvals", "ls")[1]), [])

    def test_login_has_no_secret_arguments(self):
        parser = build_parser()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parser.parse_args(["telegram", "login", "--password", "x"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parser.parse_args(["telegram", "login", "+49123"])
