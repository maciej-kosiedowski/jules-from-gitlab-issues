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
    gl_client.has_open_mr.return_value = False

    db.get_session_by_task.return_value = None
    db.get_active_sessions.return_value = []

    jules_client.create_session.return_value = {"id": "sess_1"}
    jules_client.get_active_sessions_count_from_api.return_value = 0

    monitor = TaskMonitor(gl_client, gh_client, jules_client, db)
    monitor.check_and_delegate_tasks()

    jules_client.create_session.assert_called()
    db.add_session.assert_called_with("sess_1", "1", "gitlab_issue")

def test_pr_sync_create_vs_update(tmp_path):
    gl_client = MagicMock()
    gh_client = MagicMock()
    db = MagicMock()
    db.get_all_synced_prs.return_value = {}
    db.get_gl_issue_id_by_gh_pr.return_value = None
    state_file = tmp_path / "synced_prs.json"

    pr = MagicMock()
    pr.number = 303
    pr.draft = False
    pr.title = "Test PR"
    gh_client.get_pull_requests.return_value = [pr]

    file_mock = MagicMock()
    file_mock.filename = "update.me"
    file_mock.status = "modified"
    gh_client.get_pr_diff.return_value = [file_mock]

    gh_client.get_file_content.return_value = "new content"

    gl_client.has_open_mr.return_value = False
    gl_client.file_exists.return_value = True
    gl_client.create_branch.return_value = True
    gl_client.commit_changes.return_value = True

    # Mock MR creation
    mr = MagicMock()
    mr.iid = 101
    gl_client.create_merge_request.return_value = mr

    sync = PRSync(gl_client, gh_client, db, state_file=str(state_file))
    sync.sync_github_to_gitlab()

    args, kwargs = gl_client.commit_changes.call_args
    assert args[2][0]["action"] == "update"
    db.add_synced_pr.assert_called_with(303, 101, None)
