import json
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

try:
    import fastapi
    from fastapi.testclient import TestClient
except ImportError:
    fastapi = None  # type: ignore

from orchestrator.kanban.config import KanbanConfig
from orchestrator.kanban.runtime import build_runtime
from orchestrator.telegram.client import FakeTelegramClient, TelegramNotAuthorized
from orchestrator.telegram.config import TelegramConfig
from orchestrator.telegram.models import LoginState, Suggestion, SuggestionStatus, TgDialog, TgMessage
from orchestrator.telegram.runtime import build_telegram_runtime
from orchestrator.telegram.symbols import SymbolIndex

if fastapi is not None:
    from orchestrator.kanban.api import build_app
    from orchestrator.telegram.api import sse_frames

FEED, BOT = 10, 20
T0 = "2026-01-01T12:00:00.000Z"
TOKEN = "operator-token"


def fetcher(_url):
    return {"error": [], "result": {"XBTUSD": {"wsname": "XBT/USD", "status": "online"}}}


@unittest.skipUnless(fastapi is not None, "FastAPI nicht installiert")
class Base(unittest.IsolatedAsyncioTestCase):
    env: ClassVar[dict[str, str]] = {}

    async def asyncSetUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.kanban = await build_runtime(
            KanbanConfig(
                repo_root=self.root,
                store="sqlite",
                sqlite_path=self.root / "kanban.db",
                bus="memory",
                sandbox="subprocess",
                workspace_dir=self.root / "ws",
                vault_dir=self.root / "vault",
                api_token=TOKEN,
            )
        )
        env = {
            "NIO_TELEGRAM_API_ID": "1",
            "NIO_TELEGRAM_API_HASH": "hash-secret",
            "NIO_TELEGRAM_LLM_API_KEY": "llm-secret",
            "NIO_TELEGRAM_SEND_RATE": "1",
            "NIO_TELEGRAM_CALLBACK_ALLOWLIST": "orch.local",
            **self.env,
        }
        self.client = FakeTelegramClient()
        self.client.fake_names["@glint_bot"] = BOT
        self.tg = await build_telegram_runtime(
            TelegramConfig.from_env(env, repo_root=self.root),
            kanban=self.kanban,
            client=self.client,
            symbols=SymbolIndex(self.root / "s.json", fetcher),
        )
        self.kanban.telegram = self.tg
        self.http = TestClient(build_app(self.kanban), raise_server_exceptions=False)
        self.auth = {"Authorization": f"Bearer {TOKEN}"}

    async def asyncTearDown(self):
        await self.kanban.close()
        self.td.cleanup()

    def get(self, path):
        return self.http.get(f"/api/v1/telegram{path}", headers=self.auth)

    def post(self, path, **body):
        return self.http.post(f"/api/v1/telegram{path}", headers=self.auth, json=body)

    def delete(self, path):
        return self.http.delete(f"/api/v1/telegram{path}", headers=self.auth)

    async def suggestion(self, sid="s1", target=BOT):
        await self.tg.store.add_suggestion(
            Suggestion(sid, FEED, target, "/glint BTC BULLISH 10.0", 1, "rules", SuggestionStatus.PENDING, T0, None, None)
        )
        return sid


ROUTES = [
    ("get", "/status"),
    ("get", "/dialogs"),
    ("get", "/messages"),
    ("get", "/monitored"),
    ("post", "/monitored"),
    ("delete", "/monitored/1"),
    ("get", "/pairings"),
    ("post", "/pairings"),
    ("delete", "/pairings/1"),
    ("get", "/allowlist"),
    ("post", "/allowlist"),
    ("delete", "/allowlist/1"),
    ("get", "/suggestions"),
    ("post", "/suggestions/x/approve"),
    ("post", "/suggestions/x/dismiss"),
    ("post", "/suggestions/x/retry"),
    ("get", "/approvals"),
    ("post", "/approvals"),
    ("get", "/approvals/x"),
    ("post", "/approvals/x/decide"),
    ("post", "/ask"),
    ("get", "/signals"),
    ("get", "/gather"),
    ("post", "/gather/run"),
    ("get", "/events"),
]


class TestAuth(Base):
    def test_route_table_is_complete(self):
        paths = {p.removeprefix("/api/v1/telegram") for p in self.http.app.openapi()["paths"] if p.startswith("/api/v1/telegram")}
        normalized = {p.replace("{peer}", "1").replace("{source}", "1").replace("{sid}", "x").replace("{approval_id}", "x") for p in paths}
        self.assertEqual(normalized, {path for _, path in ROUTES})

    def test_every_route_needs_the_operator_token(self):
        for method, path in ROUTES:
            with self.subTest(path=path):
                self.assertEqual(getattr(self.http, method)(f"/api/v1/telegram{path}").status_code, 401)
                bad = {"Authorization": "Bearer nope"}
                self.assertEqual(getattr(self.http, method)(f"/api/v1/telegram{path}", headers=bad).status_code, 401)

    def test_closed_without_configured_token(self):
        self.kanban.config = type(self.kanban.config)(**{**self.kanban.config.__dict__, "api_token": ""})
        self.assertEqual(self.get("/status").status_code, 503)

    def test_no_login_route(self):
        self.assertEqual(self.post("/login", phone="1").status_code, 404)

    def test_status_has_no_secrets(self):
        res = self.get("/status")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["state"], "authorized")
        for secret in ("hash-secret", "llm-secret", "nio.session", "api_hash"):
            self.assertNotIn(secret, res.text)


class TestConfigRoutes(Base):
    def test_monitor_cycle_seeds_cursor(self):
        self.client.fake_messages.append(TgMessage(FEED, 7, "f", "old", T0, False, False))
        self.assertEqual(self.post("/monitored", peer=FEED).json(), {"peer": FEED})
        self.assertEqual(self.get("/monitored").json(), [FEED])
        self.assertEqual(self.post("/gather/run").json()["fetched"], 0)
        self.delete(f"/monitored/{FEED}")
        self.assertEqual(self.get("/monitored").json(), [])

    def test_allow_and_pair_by_name(self):
        self.assertEqual(self.post("/allowlist", peer="@glint_bot").json(), {"peer": BOT})
        self.assertEqual(self.get("/allowlist").json(), {"store": [BOT], "env": []})
        self.assertEqual(self.post("/pairings", source=FEED, target="@glint_bot").json(), {"source": FEED, "target": BOT})
        self.assertEqual(self.get("/pairings").json(), [{"source": FEED, "target": BOT}])
        self.delete(f"/pairings/{FEED}")
        self.delete(f"/allowlist/{BOT}")
        self.assertEqual(self.get("/pairings").json(), [])
        self.assertEqual(self.get("/allowlist").json()["store"], [])

    def test_unknown_name_is_422(self):
        self.assertEqual(self.post("/allowlist", peer="@nobody").status_code, 422)

    def test_not_logged_in_is_409(self):
        self.client.fake_dialogs = []

        async def dialogs():
            raise TelegramNotAuthorized("x")

        self.client.dialogs = dialogs
        self.assertEqual(self.get("/dialogs").status_code, 409)

    def test_dialogs(self):
        self.client.fake_dialogs = [TgDialog(FEED, "Glint", "channel", False, 2)]
        self.assertEqual(self.get("/dialogs").json()[0]["name"], "Glint")

    def test_status_reports_logged_out(self):
        self.client.state = LoginState.DISCONNECTED
        self.assertEqual(self.get("/status").json()["state"], "disconnected")


class TestSuggestionRoutes(Base):
    async def test_approve_sends_once(self):
        await self.tg.store.allow(BOT)
        sid = await self.suggestion()
        res = self.post(f"/suggestions/{sid}/approve")
        self.assertEqual(res.json()["status"], "sent")
        self.assertEqual(self.post(f"/suggestions/{sid}/approve").status_code, 409)
        self.assertEqual(len(self.client.sent), 1)

    async def test_target_outside_allowlist_is_403(self):
        sid = await self.suggestion()
        self.assertEqual(self.post(f"/suggestions/{sid}/approve").status_code, 403)
        self.assertEqual(self.client.sent, [])

    async def test_rate_limit_is_429_with_retry_after(self):
        await self.tg.store.allow(BOT)
        self.post(f"/suggestions/{await self.suggestion('a')}/approve")
        res = self.post(f"/suggestions/{await self.suggestion('b')}/approve")
        self.assertEqual(res.status_code, 429)
        self.assertGreater(int(res.headers["Retry-After"]), 0)
        self.assertEqual(res.json()["retry_after_s"], int(res.headers["Retry-After"]))

    async def test_flood_wait_is_429(self):
        await self.tg.store.allow(BOT)
        self.client.flood_wait_after = 0
        res = self.post(f"/suggestions/{await self.suggestion()}/approve")
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.headers["Retry-After"], "30")

    async def test_dismiss_retry_and_list(self):
        sid = await self.suggestion()
        self.assertEqual(self.get("/suggestions?status=pending").json()[0]["id"], sid)
        self.assertEqual(self.post(f"/suggestions/{sid}/dismiss").json()["status"], "dismissed")
        self.assertEqual(self.post(f"/suggestions/{sid}/retry").status_code, 409)
        self.assertEqual(self.post("/suggestions/none/dismiss").status_code, 404)


class TestApprovalRoutes(Base):
    def test_request_decide_poll(self):
        created = self.post("/approvals", title="Deploy?", request_id="r1").json()
        self.assertEqual(self.get("/approvals?status=pending").json()[0]["id"], created["id"])
        self.assertEqual(self.post(f"/approvals/{created['id']}/decide", approved=True).json()["status"], "approved")
        self.assertEqual(self.get(f"/approvals/{created['id']}").json()["status"], "approved")
        self.assertEqual(self.post(f"/approvals/{created['id']}/decide", approved=False).status_code, 409)

    def test_foreign_callback_is_refused(self):
        self.assertEqual(self.post("/approvals", title="x", callback_url="http://evil.example/x").status_code, 422)

    def test_unknown_field_is_refused(self):
        self.assertEqual(self.post("/approvals", title="x", notify_url="http://evil.example").status_code, 422)

    def test_unknown_approval_is_404(self):
        self.assertEqual(self.get("/approvals/none").status_code, 404)


class TestIntelRoutes(Base):
    async def test_ask_uses_cache_and_signals_list(self):
        await self.tg.store.add_messages([TgMessage(FEED, 1, "f", "BTC bullish", T0, False, False)])
        res = self.post("/ask", question="Wie steht BTC?")
        self.assertEqual(res.json()["source"], "rules")
        self.assertIn("BULLISH", res.json()["answer"])
        self.assertEqual(self.get(f"/messages?peer={FEED}").json()[0]["msg_id"], 1)
        self.assertEqual(self.get("/signals").json(), [])

    def test_gather_status(self):
        self.assertEqual(self.get("/gather").json()["running"], False)

    async def test_sse_frames(self):
        stream = sse_frames(self.tg, keepalive_s=0.01)
        self.assertEqual(await anext(stream), ": keepalive\n\n")
        await self.tg.hub.publish("signal", {"symbol": "BTC"})
        frame = await anext(stream)
        self.assertEqual(frame, f"event: signal\ndata: {json.dumps({'symbol': 'BTC'})}\n\n")
        self.tg.hub.close()
        with self.assertRaises(StopAsyncIteration):
            await anext(stream)


class TestWorkerTools(Base):
    def test_listed_without_any_send_tool(self):
        names = [t["name"] for t in self.http.get("/api/v1/kanban/tools").json()]
        self.assertIn("telegram_feed", names)
        self.assertFalse([n for n in names if n.startswith("telegram_") and "send" in n])

    def test_tool_call_needs_task_token(self):
        res = self.http.post("/api/v1/kanban/tools/telegram_feed", json={"arguments": {}})
        self.assertEqual(res.status_code, 401)
        res = self.http.post("/api/v1/kanban/tools/telegram_feed", json={"arguments": {}}, headers=self.auth)
        self.assertEqual(res.status_code, 401)

    async def test_tool_call_with_task_token(self):
        await self.kanban.tokens.put("tok", {"task_id": "t", "worker_uid": "w"}, 60)
        res = self.http.post("/api/v1/kanban/tools/telegram_signals", json={"arguments": {}}, headers={"Authorization": "Bearer tok"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["untrusted"], [])


class TestUnmounted(Base):
    async def test_not_mounted_without_runtime(self):
        self.kanban.telegram = None
        http = TestClient(build_app(self.kanban))
        self.assertEqual(http.get("/api/v1/telegram/status", headers=self.auth).status_code, 404)
        self.kanban.telegram = self.tg
