import unittest
from unittest.mock import MagicMock, patch
from src.logic.pr_sync import PRSync

class TestFlowE(unittest.TestCase):
    def setUp(self):
        self.mock_gl_client = MagicMock()
        self.mock_gh_client = MagicMock()
        self.mock_db = MagicMock()
        # Mocking the _migrate_from_json method which is called in __init__
        with patch('src.logic.pr_sync.PRSync._migrate_from_json'):
            self.pr_sync = PRSync(self.mock_gl_client, self.mock_gh_client, self.mock_db)

    def test_process_flow_e_update_needed(self):
        # Setup mock PR that is behind
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.mergeable_state = 'behind'

        self.mock_gh_client.get_pull_requests.return_value = [mock_pr]
        self.mock_gh_client.rebase_pr.return_value = True

        # Execute
        self.pr_sync.process_flow_e()

        # Assert rebase_pr was called
        self.mock_gh_client.rebase_pr.assert_called_once_with(123)

    def test_process_flow_e_no_update_needed(self):
        # Setup mock PR that is clean
        mock_pr = MagicMock()
        mock_pr.number = 124
        mock_pr.mergeable_state = 'clean'

        self.mock_gh_client.get_pull_requests.return_value = [mock_pr]

        # Execute
        self.pr_sync.process_flow_e()

        # Assert rebase_pr was NOT called
        self.mock_gh_client.rebase_pr.assert_not_called()

    def test_process_flow_e_conflict(self):
        # Setup mock PR that has conflicts
        mock_pr = MagicMock()
        mock_pr.number = 125
        mock_pr.mergeable_state = 'dirty'

        self.mock_gh_client.get_pull_requests.return_value = [mock_pr]

        # Execute
        self.pr_sync.process_flow_e()

        # Assert rebase_pr was NOT called
        self.mock_gh_client.rebase_pr.assert_not_called()
