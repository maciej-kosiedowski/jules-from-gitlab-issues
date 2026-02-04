from unittest.mock import MagicMock, patch
from src.logic.task_monitor import TaskMonitor
from src.logic.pr_sync import PRSync
import time

def test_task_monitor_delegation():
    gl_client = MagicMock()
    gh_client = MagicMock()
    jules_client = MagicMock()

    issue = MagicMock()
    issue.iid = 1
    issue.title = "Test Issue"
    issue.description = "Test Description"
    gl_client.get_open_ai_issues.return_value = [issue]
    jules_client.can_start_session.return_value = True
    jules_client.start_session.return_value = "sess_1"

    monitor = TaskMonitor(gl_client, gh_client, jules_client)
    monitor.check_and_delegate_gitlab_tasks()

    # Give it a moment for the thread to start/finish
    time.sleep(0.1)

    jules_client.start_session.assert_called()
    # Note: wait_for_completion is called in a thread
    # We can check if executor was called or just wait
    jules_client.wait_for_completion.assert_called()

@patch("requests.get")
def test_pr_sync_create_vs_update(mock_get, tmp_path):
    gl_client = MagicMock()
    gh_client = MagicMock()
    state_file = tmp_path / "synced_prs.json"

    pr = MagicMock()
    pr.number = 303
    pr.draft = False
    gh_client.get_pull_requests.return_value = [pr]

    file_mock = MagicMock()
    file_mock.filename = "update.me"
    gh_client.get_pr_diff.return_value = [file_mock]

    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "new content"

    gl_client.file_exists.return_value = True
    gl_client.create_branch.return_value = True
    gl_client.commit_changes.return_value = True

    sync = PRSync(gl_client, gh_client, state_file=str(state_file))
    sync.sync_github_to_gitlab()

    args, kwargs = gl_client.commit_changes.call_args
    assert args[2][0]["action"] == "update"
