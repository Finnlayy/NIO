import unittest
from pathlib import Path

from orchestrator.telegram.config import TelegramConfig


class TestTelegramConfig(unittest.TestCase):
    def test_defaults(self):
        c = TelegramConfig.from_env({})
        self.assertFalse(c.configured)
        self.assertEqual(c.api_id, None)
        self.assertEqual(c.api_hash, "")
        self.assertTrue(c.data_dir.is_absolute())
        self.assertTrue(c.data_dir.name == "telegram")
        self.assertEqual(c.send_allowlist, ())
        self.assertEqual(c.send_rate_per_hour, 6)
        self.assertEqual(c.gather_interval_s, 300.0)
        self.assertEqual(c.callback_allowlist, ())
        self.assertEqual(c.kanban_board, "")
        self.assertEqual(c.kanban_min_strength, 7)
        self.assertEqual(c.kanban_cooldown_s, 3600.0)

    def test_configured(self):
        c = TelegramConfig.from_env({"NIO_TELEGRAM_API_ID": "123", "NIO_TELEGRAM_API_HASH": "abc"})
        self.assertTrue(c.configured)
        self.assertEqual(c.api_id, 123)
        self.assertEqual(c.api_hash, "abc")

        rep = repr(c)
        self.assertNotIn("abc", rep)
        self.assertNotIn("api_hash", rep)

    def test_clamping(self):
        c = TelegramConfig.from_env({"NIO_TELEGRAM_SEND_RATE": "0", "NIO_TELEGRAM_GATHER_S": "30"})
        self.assertEqual(c.send_rate_per_hour, 1)
        self.assertEqual(c.gather_interval_s, 60.0)

    def test_allowlist_parsing(self):
        c = TelegramConfig.from_env({"NIO_TELEGRAM_SEND_ALLOWLIST": " 123 , @User , @AnotherUser,456, invalid_string"})
        self.assertEqual(c.send_allowlist, (123, "@user", "@anotheruser", 456, "@invalid_string"))

    def test_invalid_number_raises(self):
        with self.assertRaises(ValueError) as ctx:
            TelegramConfig.from_env({"NIO_TELEGRAM_SEND_RATE": "not_a_number"})
        self.assertIn("NIO_TELEGRAM_SEND_RATE", str(ctx.exception))

    def test_paths(self):
        c = TelegramConfig.from_env({"NIO_TELEGRAM_DATA_DIR": "/tmp/mydata"})
        self.assertEqual(c.data_dir, Path("/tmp/mydata"))
        self.assertEqual(c.session_path, Path("/tmp/mydata/nio.session"))
        self.assertEqual(c.db_path, Path("/tmp/mydata/telegram.db"))
        self.assertEqual(c.symbols_cache, Path("/tmp/mydata/kraken_symbols.json"))

        root = Path("/fake/root")
        c2 = TelegramConfig.from_env({"NIO_TELEGRAM_DATA_DIR": "mydata"}, repo_root=root)
        self.assertEqual(c2.data_dir, root / "mydata")

    def test_llm_prefers_telegram_values(self):
        c = TelegramConfig.from_env(
            {
                "NIO_TELEGRAM_LLM_BASE_URL": "http://tg",
                "NIO_TELEGRAM_LLM_MODEL": "tg-model",
                "NIO_TELEGRAM_LLM_API_KEY": "tg-key",
                "OPENAI_BASE_URL": "http://openai",
                "OPENAI_MODEL": "gpt",
                "OPENAI_API_KEY": "oa-key",
            }
        )
        self.assertEqual((c.llm_base_url, c.llm_model, c.llm_api_key), ("http://tg", "tg-model", "tg-key"))
        self.assertTrue(c.llm_configured)

    def test_llm_falls_back_to_openai(self):
        c = TelegramConfig.from_env({"OPENAI_BASE_URL": "http://openai", "OPENAI_MODEL": "gpt", "OPENAI_API_KEY": "oa-key"})
        self.assertEqual((c.llm_base_url, c.llm_model, c.llm_api_key), ("http://openai", "gpt", "oa-key"))

    def test_llm_needs_all_three(self):
        self.assertFalse(TelegramConfig.from_env({}).llm_configured)
        self.assertFalse(TelegramConfig.from_env({"OPENAI_API_KEY": "k", "OPENAI_MODEL": "m"}).llm_configured)

    def test_repr_hides_llm_key(self):
        self.assertNotIn("my-llm-key", repr(TelegramConfig.from_env({"NIO_TELEGRAM_LLM_API_KEY": "my-llm-key"})))


if __name__ == "__main__":
    unittest.main()
