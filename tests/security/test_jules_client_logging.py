import logging
import unittest
from unittest.mock import MagicMock, patch
from src.core.jules_client import JulesClient
import requests

class TestSecurityFix(unittest.TestCase):
    def setUp(self):
        # Configure logging to capture output
        self.logger = logging.getLogger("ato")
        self.log_capture = []
        self.logger.addHandler(logging.StreamHandler()) # Ensure we see it

        # Capture logs
        self.handler = logging.Handler()
        self.handler.emit = lambda record: self.log_capture.append(record.getMessage())
        self.logger.addHandler(self.handler)

    def tearDown(self):
        self.logger.removeHandler(self.handler)

    @patch('src.core.jules_client.settings')
    @patch('src.core.jules_client.requests.post')
    @patch('src.core.jules_client.JulesClient.get_source_name')
    def test_create_session_safe_logging(self, mock_get_source, mock_post, mock_settings):
        # Setup mocks
        mock_settings.JULES_API_KEY = "dummy_key"
        mock_settings.GITHUB_REPO = "dummy_repo"
        mock_get_source.return_value = "sources/github/dummy_repo"

        client = JulesClient()

        # Create a mock exception that mimics leaking a header
        sensitive_info = "SECRET_KEY_12345"
        mock_exception = requests.exceptions.RequestException(f"Connection failed. Headers: {sensitive_info}")
        mock_post.side_effect = mock_exception

        # Call the method
        client.create_session("prompt", "title")

        # Check logs
        found_sensitive = False
        found_safe = False

        for log_msg in self.log_capture:
            if sensitive_info in log_msg:
                found_sensitive = True
            if "RequestException" in log_msg:
                found_safe = True

        self.assertFalse(found_sensitive, "Sensitive info found in logs!")
        self.assertTrue(found_safe, "Safe error message not found in logs!")
        print("\nTest passed: Sensitive info not logged.")

if __name__ == "__main__":
    unittest.main()
