import unittest
import base64
from unittest.mock import MagicMock
from src.logic.task_monitor import TaskMonitor

class TestFeatureAttachments(unittest.TestCase):
    def test_delegation_with_attachments(self):
        # Mocks
        gl_client = MagicMock()
        gh_client = MagicMock()
        jules_client = MagicMock()
        db = MagicMock()

        # Setup TaskMonitor
        monitor = TaskMonitor(gl_client, gh_client, jules_client, db)

        # Mock API responses
        jules_client.get_active_sessions_count_from_api.return_value = 0

        # Mock Issue
        mock_issue = MagicMock()
        mock_issue.iid = 123
        mock_issue.title = "Test Issue"
        mock_issue.description = "Here is a pic ![alt](/uploads/img.png)"

        gl_client.get_open_ai_issues.return_value = [mock_issue]
        db.get_session_by_task.return_value = None # Not delegated yet
        gl_client.has_open_mr.return_value = False
        gl_client.get_file_content.return_value = "Guideline Content"

        # Mock Notes
        mock_note = MagicMock()
        # Handle attribute access for author if logic uses note.author['name'] or note.author.name
        # The code uses: author_name = note.author['name'] if isinstance(note.author, dict) else note.author.name
        # We'll make it a dict to be safe and easy
        mock_note.author = {"name": "User"}
        mock_note.created_at = "2023-01-01"
        mock_note.body = "Note content"
        mock_note.system = False

        gl_client.get_issue_notes.return_value = [mock_note]

        # Mock Download
        gl_client.download_file.return_value = b"fake_image_bytes"

        # Mock Session Creation
        jules_client.create_session.return_value = {"id": "sess_1"}

        # Run
        monitor.check_and_delegate_tasks()

        # Verify
        gl_client.get_issue_notes.assert_called_with(123)
        gl_client.download_file.assert_called()

        # Check create_session call
        args, kwargs = jules_client.create_session.call_args
        prompt = args[0]
        attachments = kwargs.get("attachments")

        print(f"Prompt: {prompt}")

        self.assertIn("Conversation History:", prompt)
        self.assertIn("Comment by User", prompt)
        self.assertIsNotNone(attachments)
        self.assertEqual(len(attachments), 1)

        expected_b64 = base64.b64encode(b"fake_image_bytes").decode("utf-8")
        self.assertEqual(attachments[0]["data"], expected_b64)

if __name__ == "__main__":
    unittest.main()
