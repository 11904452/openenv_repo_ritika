import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bankops_chargeback import inference


class InferenceEnvLoadingTest(unittest.TestCase):
    def test_fmt_error_uses_explicit_last_action_error(self):
        self.assertEqual(inference._fmt_error(None), "null")
        self.assertEqual(
            inference._fmt_error("Action requires a value for priority."),
            "Action requires a value for priority.",
        )

    def test_skips_dotenv_when_hf_token_exists_in_os_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "HF_TOKEN=from_dotenv\nAPI_BASE_URL=https://example.invalid/v1\nMODEL_NAME=test-model\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"HF_TOKEN": "from_os"}, clear=True):
                loaded = inference.load_env_file_if_needed(candidates=[env_path])

                self.assertFalse(loaded)
                self.assertEqual(os.environ["HF_TOKEN"], "from_os")
                self.assertNotIn("API_BASE_URL", os.environ)
                self.assertNotIn("MODEL_NAME", os.environ)

    def test_uses_dotenv_when_hf_token_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                (
                    "HF_TOKEN=from_dotenv\n"
                    "API_BASE_URL=https://example.invalid/v1\n"
                    "MODEL_NAME=test-model\n"
                    "OPENENV_BASE_URL=http://127.0.0.1:9999\n"
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                loaded = inference.load_env_file_if_needed(candidates=[env_path])

                self.assertTrue(loaded)
                self.assertEqual(os.environ["HF_TOKEN"], "from_dotenv")
                self.assertEqual(os.environ["API_BASE_URL"], "https://example.invalid/v1")
                self.assertEqual(os.environ["MODEL_NAME"], "test-model")
                self.assertEqual(os.environ["OPENENV_BASE_URL"], "http://127.0.0.1:9999")


if __name__ == "__main__":
    unittest.main()
