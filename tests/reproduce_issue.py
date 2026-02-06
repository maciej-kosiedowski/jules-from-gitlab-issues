import unittest
from unittest.mock import MagicMock, patch
from src.logic.pr_sync import PRSync

class TestPRSyncReproduction(unittest.TestCase):
    def test_sync_github_to_gitlab_no_files_retrieved(self):
        # Mock GitHub client
        mock_gh = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 1
        mock_pr.draft = False
        mock_pr.title = "Test PR"
        mock_pr.html_url = "http://github/pr/1"
        mock_gh.get_pull_requests.return_value = [mock_pr]

        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.status = "added"
        mock_gh.get_pr_diff.return_value = [mock_file]

        # Mock get_file_content to raise exception or return None
        mock_gh.get_file_content.side_effect = Exception("Failed to get content")

        # Mock GitLab client
        mock_gl = MagicMock()

        # Mock DB
        mock_db = MagicMock()
        mock_db.get_all_synced_prs.return_value = {}
        mock_db.get_gl_issue_id_by_gh_pr.return_value = None

        sync = PRSync(mock_gl, mock_gh, mock_db, state_file="data/test_sync.json")

        with patch('src.logic.pr_sync.logger') as mock_logger:
            sync.sync_github_to_gitlab()
            mock_logger.warning.assert_called_with("No actions could be generated for PR #1")

if __name__ == '__main__':
    unittest.main()
