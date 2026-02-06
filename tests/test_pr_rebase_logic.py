import unittest
from unittest.mock import MagicMock
from src.logic.pr_sync import PRSync

class TestPRRebaseLogic(unittest.TestCase):
    def setUp(self):
        self.mock_gl = MagicMock()
        self.mock_gh = MagicMock()
        self.mock_db = MagicMock()

        # Mock database return values to avoid errors in init
        self.mock_db.get_all_synced_prs.return_value = {}

        self.sync = PRSync(self.mock_gl, self.mock_gh, self.mock_db, state_file="data/test_rebase_sync.json")

    def test_pr_with_conflicts_gets_comment(self):
        # Mock PR with conflicts
        mock_pr = MagicMock()
        mock_pr.number = 101
        mock_pr.mergeable = False
        mock_pr.draft = False # or True, should not matter
        mock_pr.get_issue_comments.return_value = []

        self.mock_gh.get_pull_requests.return_value = [mock_pr]

        self.sync.check_prs_for_rebase_and_conflicts()

        # Verify comment was created
        mock_pr.create_issue_comment.assert_called_once()
        args = mock_pr.create_issue_comment.call_args[0]
        self.assertIn("Hello @jules!", args[0])
        self.assertIn("merge conflicts", args[0])

    def test_pr_already_commented_no_duplicate(self):
        # Mock PR with conflicts
        mock_pr = MagicMock()
        mock_pr.number = 102
        mock_pr.mergeable = False

        # Mock existing comment
        mock_comment = MagicMock()
        mock_comment.body = "Hello @jules! It looks like this PR has some merge conflicts or needs a rebase. Could you please resolve them, ensure all tests pass, and force push the clean changes? Thank you!"
        mock_pr.get_issue_comments.return_value = [mock_comment]

        self.mock_gh.get_pull_requests.return_value = [mock_pr]

        self.sync.check_prs_for_rebase_and_conflicts()

        # Verify NO new comment
        mock_pr.create_issue_comment.assert_not_called()

    def test_clean_pr_no_comment(self):
        # Mock clean PR
        mock_pr = MagicMock()
        mock_pr.number = 103
        mock_pr.mergeable = True

        self.mock_gh.get_pull_requests.return_value = [mock_pr]

        self.sync.check_prs_for_rebase_and_conflicts()

        mock_pr.create_issue_comment.assert_not_called()

    def test_unknown_mergeable_state_skipped(self):
        # Mock PR with unknown state
        mock_pr = MagicMock()
        mock_pr.number = 104
        mock_pr.mergeable = None

        self.mock_gh.get_pull_requests.return_value = [mock_pr]

        self.sync.check_prs_for_rebase_and_conflicts()

        mock_pr.create_issue_comment.assert_not_called()

if __name__ == '__main__':
    unittest.main()
