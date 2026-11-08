import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Remove sys.path.append, replace with sys.path.insert for the parent directory, matching other tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from limbs.intelligence.genai_client import GenAIClient


class DummyConfig:
    GEMINI_API_KEY = "dummy_key"
    GEMINI_MODEL_FAST = "gemini-1.5-flash"
    GEMINI_MODEL_DEEP = "gemini-1.5-pro"
    LM_STUDIO_ENABLED = False
    LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
    LM_STUDIO_MODEL = "local-model"
    LM_STUDIO_API_KEY = "not-needed"
    LM_STUDIO_TIMEOUT = 30.0

class TestGenAIClient(unittest.TestCase):
    @patch("google.genai.Client")
    def test_automatic_function_calling_disabled(self, MockClient):
        mock_client_instance = MockClient.return_value

        mock_response = MagicMock()
        mock_response.text = "This is a dummy response."
        mock_client_instance.models.generate_content.return_value = mock_response

        client = GenAIClient(DummyConfig())
        client.generate_journal({"job_id": "test_123", "plan_id": "plan_abc"})

        mock_client_instance.models.generate_content.assert_called_once()
        call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs

        self.assertIn("config", call_kwargs)
        config_obj = call_kwargs["config"]
        self.assertTrue(config_obj.automatic_function_calling.disable)

        mock_client_instance.models.generate_content.reset_mock()
        client.reflect_dsr({"job_id": "test_123", "execution_result": "failed"})

        mock_client_instance.models.generate_content.assert_called_once()
        call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs

        self.assertIn("config", call_kwargs)
        config_obj = call_kwargs["config"]
        self.assertTrue(config_obj.automatic_function_calling.disable)

if __name__ == "__main__":
    unittest.main()
