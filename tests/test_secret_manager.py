"""Contract tests with fixtures only; no claim of external live-provider success."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator.kanban.worker_entry import _live_completion, _redact_output
from orchestrator.secret_manager import llm_worker_environment, secret_environment


class SecretManagerTests(unittest.TestCase):
    def test_missing_credentials_are_not_invented(self) -> None:
        self.assertEqual(llm_worker_environment([], env={}), {"NIO_LLM_ERROR": "no_provider_configured"})
        self.assertEqual(llm_worker_environment([], provider_id="groq", env={}), {"NIO_LLM_ERROR": "missing_secret"})

    def test_injection_requires_explicit_allowlist_and_never_injects_other_keys(self) -> None:
        env = {"GROQ_API_KEY": "groq-fixture", "OPENROUTER_API_KEY": "router-fixture", "NIO_LLM_PROVIDER": "groq"}
        self.assertEqual(llm_worker_environment([], env=env), {"NIO_LLM_ERROR": "provider_secret_not_allowlisted"})
        result = llm_worker_environment(["GROQ_API_KEY"], env=env)
        self.assertEqual(result["NIO_LLM_API_KEY"], "groq-fixture")
        self.assertEqual(result["NIO_LLM_PROVIDER"], "groq")
        self.assertNotIn("router-fixture", result.values())
        self.assertNotIn("NIO_SECRET_FILE", result)

    def test_alias_model_and_gateway_requirements(self) -> None:
        result = llm_worker_environment(["GEMINI_API_KEY"], env={"GEMINI_API_KEY": "fixture"})
        self.assertEqual(result["NIO_LLM_PROVIDER"], "google")
        self.assertEqual(llm_worker_environment(["HF_TOKEN"], env={"HF_TOKEN": "fixture"}), {"NIO_LLM_ERROR": "model_missing"})
        result = llm_worker_environment(["FREELLMAPI_KEY"], env={"FREELLMAPI_KEY": "fixture", "FREELLMAPI_MODEL": "test", "FREELLMAPI_HOST": "gateway.example:9000"})
        self.assertEqual(result["NIO_LLM_ENDPOINT"], "https://gateway.example:9000/v1/chat/completions")

    def test_owner_only_mount_and_env_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "secrets.json"
            file.write_text(json.dumps({"GROQ_API_KEY": "mounted-fixture"}))
            file.chmod(0o600)
            env = {"NIO_SECRET_FILE": str(file)}
            self.assertEqual(secret_environment(env)["GROQ_API_KEY"], "mounted-fixture")
            self.assertEqual(secret_environment({**env, "GROQ_API_KEY": "env-fixture"})["GROQ_API_KEY"], "env-fixture")
            file.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "^secret_store_unavailable_or_invalid$"):
                secret_environment(env)
            file.chmod(0o600)
            file.write_text('{"GROQ_API_KEY": "mounted-fixture" BROKEN')
            with self.assertRaisesRegex(ValueError, "^secret_store_unavailable_or_invalid$"):
                secret_environment(env)
            link = Path(directory) / "link.json"
            link.symlink_to(file)
            with self.assertRaisesRegex(ValueError, "^secret_store_unavailable_or_invalid$"):
                secret_environment({"NIO_SECRET_FILE": str(link)})

    def test_worker_failure_stays_failure_before_network(self) -> None:
        with mock.patch.dict(os.environ, {"NIO_LLM_ERROR": "missing_secret"}, clear=True):
            with self.assertRaisesRegex(ValueError, "missing_secret"):
                _live_completion("no simulation", {"title": "cheap probe"})
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "missing_secret"):
                _live_completion("", {})

    def test_worker_artifacts_redact_injected_keys_and_task_token(self) -> None:
        with mock.patch.dict(os.environ, {"NIO_LLM_API_KEY": "credential-fixture", "NIO_KANBAN_TASK_TOKEN": "token-fixture"}, clear=True):
            result = _redact_output({"text": "credential-fixture", "nested": ["token-fixture"]})
        self.assertEqual(result, {"text": "[REDACTED]", "nested": ["[REDACTED]"]})
