import subprocess
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from orchestrator.telegram.client import (
    FakeTelegramClient,
    TelegramFloodWait,
    TelegramUnavailable,
    TelethonClient,
    _normalize_peer,
)
from orchestrator.telegram.config import TelegramConfig
from orchestrator.telegram.models import LoginState, TgMessage

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestTelegramClient(unittest.IsolatedAsyncioTestCase):
    async def test_fake_client(self):
        c = FakeTelegramClient()
        self.assertEqual(await c.status(), LoginState.AUTHORIZED)

        cb_called = False

        async def cb(msg):
            nonlocal cb_called
            cb_called = True

        c.on_new_message(cb)

        m = TgMessage(1, 1, "S", "T", "2023", False, False)
        await c.push(m)
        self.assertTrue(cb_called)

        msgs = await c.messages_since(1, 0)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].msg_id, 1)

        c.flood_wait_after = 1
        await c.send(1, "1")
        with self.assertRaises(TelegramFloodWait):
            await c.send(1, "2")

    def test_normalize_peer(self):
        self.assertEqual(_normalize_peer(123), 123)
        self.assertEqual(_normalize_peer("123"), 123)
        self.assertEqual(_normalize_peer("@User"), "@user")
        self.assertEqual(_normalize_peer("@username"), "@username")
        self.assertEqual(_normalize_peer("  @Foo  "), "@foo")
        self.assertEqual(_normalize_peer("GlintBot"), "@glintbot")
        self.assertEqual(_normalize_peer("-100123"), -100123)

    async def test_lazy_import(self):
        # Modul-Import ohne telethon klappt; erst der echte Client meldet das fehlende Extra.
        with mock.patch.dict(sys.modules, {"telethon": None}):
            unconfigured = TelethonClient(TelegramConfig.from_env({}))
            self.assertEqual(await unconfigured.status(), LoginState.UNCONFIGURED)

            configured = TelethonClient(TelegramConfig.from_env({"NIO_TELEGRAM_API_ID": "123", "NIO_TELEGRAM_API_HASH": "abc"}))
            with self.assertRaises(TelegramUnavailable) as ctx:
                await configured.status()
            self.assertNotIn("abc", str(ctx.exception))

    def test_import_without_telethon_subprocess(self):
        code = (
            "import sys; sys.modules['telethon'] = None\n"
            "import orchestrator.telegram.client, orchestrator.telegram.store, orchestrator.telegram.symbols\n"
        )
        proc = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    async def test_serialize_message_stub(self):
        utils = types.ModuleType("telethon.utils")
        utils.get_peer_id = lambda peer: peer  # type: ignore[attr-defined]
        tl = types.ModuleType("telethon")
        tl.utils = utils  # type: ignore[attr-defined]
        sender = types.SimpleNamespace(username="glintbot", first_name="Glint", bot=True)
        message = types.SimpleNamespace(
            text="BTC long",
            peer_id=-100123,
            date=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            sender=sender,
            sender_id=42,
            id=7,
            out=False,
        )
        with mock.patch.dict(sys.modules, {"telethon": tl, "telethon.utils": utils}):
            client = TelethonClient(TelegramConfig.from_env({}))
            msg = await client._serialize_message(message)
        assert msg is not None
        self.assertEqual(msg.peer, -100123)
        self.assertEqual(msg.ts, "2026-01-02T03:04:05.000Z")
        self.assertEqual(msg.sender, "glintbot")
        self.assertTrue(msg.is_bot)

    async def test_fake_send_records(self):
        c = FakeTelegramClient()
        sent = await c.send(5, "hi")
        self.assertEqual(c.sent, [(5, "hi")])
        self.assertTrue(sent.outgoing)
        c.flood_wait_after = 1
        with self.assertRaises(TelegramFloodWait) as ctx:
            await c.send(5, "again")
        self.assertEqual(ctx.exception.seconds, 30)


if __name__ == "__main__":
    unittest.main()


class TestTelethonConnectRetry(unittest.IsolatedAsyncioTestCase):
    async def test_failed_connect_is_not_remembered(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest import mock

        from orchestrator.telegram import client as client_module
        from orchestrator.telegram.client import TelethonClient
        from orchestrator.telegram.config import TelegramConfig

        with tempfile.TemporaryDirectory() as td:
            config = TelegramConfig.from_env({"NIO_TELEGRAM_API_ID": "1", "NIO_TELEGRAM_API_HASH": "h"}, repo_root=Path(td))
            broken = mock.Mock(connect=mock.AsyncMock(side_effect=ConnectionError("offline")))
            module = SimpleNamespace(TelegramClient=mock.Mock(return_value=broken))
            with mock.patch.object(client_module, "_import_telethon", return_value=module):
                client = TelethonClient(config)
                with self.assertRaises(ConnectionError):
                    await client.status()
            self.assertIsNone(client._client)
