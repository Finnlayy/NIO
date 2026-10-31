import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.telegram.symbols import SymbolIndex


class TestTelegramSymbols(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.td.name) / "cache.json"

    async def asyncTearDown(self):
        self.td.cleanup()

    async def test_live_fetch(self):
        def fake_fetch(url):
            return {
                "error": [],
                "result": {
                    "XXBTZUSD": {"wsname": "XBT/USD", "status": "online"},
                    "ETHUSD": {"wsname": "ETH/USD", "status": "online"},
                    "XBTUSDT.d": {"wsname": "XBT/USDT.d", "status": "online"},  # derivative
                    "OFFLINE": {"wsname": "OFF/USD", "status": "maintenance"},
                },
            }

        index = SymbolIndex(self.cache_path, fetcher=fake_fetch)
        await index.ensure()

        status = index.status()
        self.assertEqual(status["source"], "live")
        # Bases: XBT, ETH + BTC (alias) -> 3
        self.assertEqual(status["count"], 3)
        self.assertIn("XBT", index.bases)
        self.assertIn("BTC", index.bases)
        self.assertNotIn("OFF", index.bases)

        self.assertTrue(self.cache_path.exists())

    async def test_cache_fallback(self):
        def bad_fetch(url):
            raise ValueError("Network error")

        # Pre-seed cache
        data = {"payload": {"error": [], "result": {"ADAUSD": {"wsname": "ADA/USD", "status": "online"}}}, "ts": "2023-01-01T00:00:00Z"}
        self.cache_path.write_text(json.dumps(data))

        index = SymbolIndex(self.cache_path, fetcher=bad_fetch)
        await index.ensure()

        self.assertEqual(index.source, "cache")
        self.assertIn("ADA", index.bases)

    async def test_hardcoded_fallback(self):
        def bad_fetch(url):
            raise ValueError("Network error")

        index = SymbolIndex(self.cache_path, fetcher=bad_fetch)
        await index.ensure()

        self.assertEqual(index.source, "fallback")
        self.assertIn("PEPE", index.bases)

    async def test_extract(self):
        def fake_fetch(url):
            return {
                "error": [],
                "result": {
                    "PEPEUSD": {"wsname": "PEPE/USD", "status": "online"},
                    "NEARUSD": {"wsname": "NEAR/USD", "status": "online"},
                    "XBTUSD": {"wsname": "XBT/USD", "status": "online"},
                },
            }

        index = SymbolIndex(self.cache_path, fetcher=fake_fetch)
        await index.ensure()

        self.assertEqual(index.extract("buy some pepe"), "PEPE")
        self.assertEqual(index.extract("trade XBT/USD now"), "BTC")  # XBT -> BTC

        # Longest match -> fallback has multiple, let's use a custom index for PEPE vs PE
        index.bases.add("PE")
        self.assertEqual(index.extract("look at PEPE"), "PEPE")

        # False positives
        self.assertEqual(index.extract("it is near the top"), None)
        self.assertEqual(index.extract("buy NEAR"), "NEAR")
        self.assertEqual(index.extract("buy $near"), "NEAR")

    async def test_english_words_in_prose(self):
        index = SymbolIndex(self.cache_path, fetcher=_fail)
        await index.ensure()
        self.assertIsNone(index.extract("click the link, it is near the dot"))
        self.assertEqual(index.extract("$op looks strong"), "OP")
        self.assertEqual(index.extract("OP breaking out"), "OP")
        self.assertEqual(index.extract("LINK and pepe"), "LINK")
        self.assertEqual(index.extract("link and pepe"), "PEPE")
        self.assertEqual(index.extract("watch eth-usd"), "ETH")
        self.assertIsNone(index.extract("BTCUSD"))

    async def test_fallback_retries_after_ttl(self):
        now = [0.0]
        calls: list[str] = []

        def flaky(url: str) -> dict:
            calls.append(url)
            if len(calls) == 1:
                raise OSError("offline")
            return {"error": [], "result": {"SOLUSD": {"wsname": "SOL/USD", "status": "online"}}}

        index = SymbolIndex(self.cache_path, fetcher=flaky, clock=lambda: now[0])
        await index.ensure()
        self.assertEqual(index.source, "fallback")
        await index.ensure()
        self.assertEqual(len(calls), 1)
        now[0] = 10_000.0
        await index.ensure()
        self.assertEqual(index.source, "live")
        self.assertEqual(list(self.cache_path.parent.glob("*.tmp")), [])

    async def test_cache_write_failure_stays_live(self):
        def ok(url: str) -> dict:
            return {"error": [], "result": {"SOLUSD": {"wsname": "SOL/USD", "status": "online"}}}

        blocker = Path(self.td.name) / "file"
        blocker.write_text("x")
        index = SymbolIndex(blocker / "cache.json", fetcher=ok)
        await index.ensure()
        self.assertEqual(index.source, "live")


def _fail(url: str) -> dict:
    raise OSError("offline")


if __name__ == "__main__":
    unittest.main()
