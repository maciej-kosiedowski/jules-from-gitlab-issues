import unittest
from unittest.mock import MagicMock, patch
from src.logic.pr_sync import PRSync

class TestSyncLogic(unittest.TestCase):
    def setUp(self):
        self.mock_gl = MagicMock()
        self.mock_gh = MagicMock()
        # Use a temporary state file
        self.sync = PRSync(self.mock_gl, self.mock_gh, state_file="data/test_sync.json")
        self.sync.synced_prs = {}

    def test_sync_github_to_gitlab_with_issue_id(self):
        # Mock GitHub PR
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.draft = False
        mock_pr.title = "GL Issue #456: Fix bug"
        mock_pr.html_url = "http://github/pr/123"
        mock_pr.head.sha = "abcdef"
        self.mock_gh.get_pull_requests.return_value = [mock_pr]

        # Mock files
        mock_file = MagicMock()
        mock_file.filename = "src/main.py"
        mock_file.status = "modified"
        self.mock_gh.get_pr_diff.return_value = [mock_file]
        self.mock_gh.get_file_content.return_value = "print('hello')"

        # Mock GitLab
        self.mock_gl.has_open_mr.return_value = False
        self.mock_gl.file_exists.return_value = True
        self.mock_gl.create_branch.return_value = True
        self.mock_gl.commit_changes.return_value = True

        mock_mr = MagicMock()
        mock_mr.iid = 789
        self.mock_gl.create_merge_request.return_value = mock_mr

        self.sync.sync_github_to_gitlab()

        # Verify MR creation with "Closes #456"
        self.mock_gl.create_merge_request.assert_called_once()
        args, kwargs = self.mock_gl.create_merge_request.call_args
        self.assertIn("Closes #456", kwargs["description"])
        self.assertEqual(kwargs["title"], "Sync: GL Issue #456: Fix bug")

    def test_skip_sync_if_mr_exists(self):
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.draft = False
        mock_pr.title = "GL Issue #456: Fix bug"
        self.mock_gh.get_pull_requests.return_value = [mock_pr]

        self.mock_gl.has_open_mr.return_value = True

        self.sync.sync_github_to_gitlab()

        self.mock_gl.create_branch.assert_not_called()

    def test_handle_removed_file(self):
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.draft = False
        mock_pr.title = "Test PR"
        mock_pr.head.sha = "abcdef"
        self.mock_gh.get_pull_requests.return_value = [mock_pr]

        mock_file = MagicMock()
        mock_file.filename = "deleted.txt"
        mock_file.status = "removed"
        self.mock_gh.get_pr_diff.return_value = [mock_file]

        self.mock_gl.create_branch.return_value = True
        self.mock_gl.commit_changes.return_value = True
        self.mock_gl.create_merge_request.return_value = MagicMock(iid=1)

        self.sync.sync_github_to_gitlab()

        # Verify commit actions
        self.mock_gl.commit_changes.assert_called_once()
        args = self.mock_gl.commit_changes.call_args[0]
        actions = args[2]
        self.assertEqual(actions[0]["action"], "delete")
        self.assertEqual(actions[0]["file_path"], "deleted.txt")

if __name__ == '__main__':
    unittest.main()
