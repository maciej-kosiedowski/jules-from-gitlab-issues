import unittest
from unittest.mock import MagicMock, patch
from src.core.github_client import GitHubClient

class TestGitHubClientOptimization(unittest.TestCase):
    def test_optimization(self):
        # Mock settings to avoid actual API connection during init
        with patch('src.core.github_client.Github') as MockGithub:
            client = GitHubClient()
            # Reset mock to clear init calls
            client.repo = MagicMock()

            # Simulate a PR object
            mock_pr = MagicMock()
            client.repo.get_pull.return_value = mock_pr

            # Test add_pr_comment optimization
            client.repo.get_pull.reset_mock()
            client.add_pr_comment(123, "Test comment", pr=mock_pr)
            self.assertEqual(client.repo.get_pull.call_count, 0, "add_pr_comment called get_pull when pr object was provided")

            # Test close_pr optimization
            client.repo.get_pull.reset_mock()
            client.close_pr(123, pr=mock_pr)
            self.assertEqual(client.repo.get_pull.call_count, 0, "close_pr called get_pull when pr object was provided")

            # Test get_pr_diff optimization
            client.repo.get_pull.reset_mock()
            client.get_pr_diff(123, pr=mock_pr)
            self.assertEqual(client.repo.get_pull.call_count, 0, "get_pr_diff called get_pull when pr object was provided")

if __name__ == "__main__":
    unittest.main()
