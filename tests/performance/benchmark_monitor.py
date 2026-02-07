import time
import unittest
from unittest.mock import MagicMock
from src.logic.task_monitor import TaskMonitor
from src.core.database import Database
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.config import settings

class BenchmarkTaskMonitor(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock(spec=Database)
        self.mock_gl = MagicMock(spec=GitLabClient)
        self.mock_gh = MagicMock(spec=GitHubClient)
        self.mock_jules = MagicMock(spec=JulesClient)

        # Configure mocks
        self.mock_jules.get_active_sessions_count_from_api.return_value = 0
        settings.JULES_MAX_CONCURRENT_SESSIONS = 1000

        # Setup 100 issues
        self.issues = []
        for i in range(1, 101):
            issue = MagicMock()
            issue.iid = i
            issue.title = f"Issue {i}"
            issue.description = "Description"
            self.issues.append(issue)

        self.mock_gl.get_open_ai_issues.return_value = self.issues
        self.mock_gl.has_open_mr.return_value = False
        self.mock_gh.get_pull_requests.return_value = [] # No GitHub PRs to focus on GL loop

        # Setup DB behavior:
        # get_all_task_ids returns a set of strings "1".."90"
        # Issues 91-100 do not exist in the set

        existing_sessions = {str(i) for i in range(1, 91)}

        def get_all_task_ids_side_effect(task_type):
            if task_type == "gitlab_issue":
                return existing_sessions.copy()
            return set()

        self.mock_db.get_all_task_ids.side_effect = get_all_task_ids_side_effect
        self.mock_db.get_session_by_task.return_value = None # Should not be called in the loop

        self.monitor = TaskMonitor(self.mock_gl, self.mock_gh, self.mock_jules, self.mock_db)

    def test_benchmark_delegation(self):
        start_time = time.time()
        self.monitor.check_and_delegate_tasks()
        end_time = time.time()

        duration = end_time - start_time
        print(f"\nExecution Time: {duration:.4f} seconds")
        print(f"DB get_session_by_task calls: {self.mock_db.get_session_by_task.call_count}")
        print(f"DB get_all_task_ids calls: {self.mock_db.get_all_task_ids.call_count}")
        print(f"GitLab has_open_mr calls: {self.mock_gl.has_open_mr.call_count}")

if __name__ == "__main__":
    unittest.main()
