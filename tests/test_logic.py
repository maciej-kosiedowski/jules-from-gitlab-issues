from unittest.mock import MagicMock, patch
from src.logic.task_monitor import TaskMonitor
from src.logic.pr_sync import PRSync

def test_task_monitor_delegation():
    gl_client = MagicMock()
    gh_client = MagicMock()
    jules_client = MagicMock()
    db = MagicMock()

    issue = MagicMock()
    issue.iid = 1
    issue.title = "Test Issue"
    issue.description = "Test Description"
    gl_client.get_open_ai_issues.return_value = [issue]

    db.get_session_by_task.return_value = None
    db.get_active_sessions.return_value = []

    jules_client.create_session.return_value = {"id": "sess_1"}

    monitor = TaskMonitor(gl_client, gh_client, jules_client, db)
    monitor.check_and_delegate_gitlab_tasks()

    jules_client.create_session.assert_called()
    db.add_session.assert_called_with("sess_1", 1, "gitlab_issue")

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

    # Mock MR creation
    mr = MagicMock()
    mr.iid = 101
    gl_client.create_merge_request.return_value = mr

    sync = PRSync(gl_client, gh_client, state_file=str(state_file))
    sync.sync_github_to_gitlab()

    args, kwargs = gl_client.commit_changes.call_args
    assert args[2][0]["action"] == "update"
    assert sync.synced_prs["303"] == 101
