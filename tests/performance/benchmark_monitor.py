import time
import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to python path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
)

from src.logic.task_monitor import TaskMonitor  # noqa: E402


class BenchmarkMonitor(unittest.TestCase):
    def setUp(self):
        self.num_sessions = 50
        self.latency = 0.05  # 50ms simulated latency per call

        # Mock dependencies
        self.mock_db = MagicMock()
        # Mock active sessions: list of
        # (session_id, task_id, task_type, github_pr_id, gitlab_mr_id)
        self.mock_db.get_active_sessions.return_value = [
            (f"session_{i}", f"task_{i}", "github_pr", None, None)
            for i in range(self.num_sessions)
        ]

        self.mock_jules_client = MagicMock()

        # Simulate network delay in get_session
        def get_session_side_effect(session_id):
            time.sleep(self.latency)
            return {"id": session_id, "state": "IN_PROGRESS", "outputs": []}

        self.mock_jules_client.get_session.side_effect = (
            get_session_side_effect
        )

        # Simulate delay in list_activities as well
        def list_activities_side_effect(session_id):
            time.sleep(self.latency)
            return [{"type": "INFO", "message": "Working..."}]

        self.mock_jules_client.list_activities.side_effect = (
            list_activities_side_effect
        )

        self.mock_gh_client = MagicMock()
        self.mock_gl_client = MagicMock()

        # Instantiate TaskMonitor with mocks
        self.monitor = TaskMonitor(
            gl_client=self.mock_gl_client,
            gh_client=self.mock_gh_client,
            jules_client=self.mock_jules_client,
            db=self.mock_db
        )

    def test_performance(self):
        print(
            f"\nBenchmarking monitor_active_sessions with "
            f"{self.num_sessions} sessions and {self.latency*1000:.0f}ms "
            "latency..."
        )

        start_time = time.time()
        self.monitor.monitor_active_sessions()
        end_time = time.time()

        duration = end_time - start_time
        print(f"Total time: {duration:.4f} seconds")
        print(
            f"Average time per session: "
            f"{duration / self.num_sessions:.4f} seconds"
        )

        # We expect sequential execution to take roughly
        # num_sessions * (latency * 2)
        # (since get_session + list_activities are called)
        expected_sequential = self.num_sessions * (self.latency * 2)
        print(
            f"Expected sequential time (approx): "
            f"{expected_sequential:.4f} seconds"
        )


if __name__ == '__main__':
    unittest.main()
