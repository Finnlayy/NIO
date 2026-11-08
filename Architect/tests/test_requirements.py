import os
import unittest


class TestRequirements(unittest.TestCase):
    def test_google_genai_is_pinned(self):
        req_file = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        with open(req_file) as f:
            lines = f.readlines()

        google_genai_line = None
        for line in lines:
            if line.strip().startswith("google-genai"):
                google_genai_line = line.strip()
                break

        self.assertIsNotNone(google_genai_line, "google-genai not found in requirements.txt")
        self.assertIn("==", google_genai_line, f"google-genai is not pinned to an exact version: {google_genai_line}")

if __name__ == "__main__":
    unittest.main()
