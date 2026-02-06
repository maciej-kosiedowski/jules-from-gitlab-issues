import unittest
from unittest.mock import MagicMock, patch
from src.logic.pr_sync import PRSync

class TestPRSyncReproduction(unittest.TestCase):
    @patch('src.logic.pr_sync.requests.get')
    def test_sync_github_to_gitlab_no_files_retrieved(self, mock_get):
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
        mock_file.raw_url = "http://github/raw/test.txt"
        mock_gh.get_pr_diff.return_value = [mock_file]

        # Mock requests.get to return 404 or something else than 200
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        # Mock GitLab client
        mock_gl = MagicMock()

        sync = PRSync(mock_gl, mock_gh, state_file="data/test_sync.json")
        sync.synced_prs = {}

        with patch('src.logic.pr_sync.logger') as mock_logger:
            sync.sync_github_to_gitlab()
            mock_logger.warning.assert_called_with("No files could be retrieved for PR #1")

if __name__ == '__main__':
    unittest.main()
