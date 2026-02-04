import pytest
from unittest.mock import MagicMock, patch
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.logic.task_monitor import TaskMonitor
from src.logic.pr_sync import PRSync
from src.main import main
from src.config import settings


@patch("src.core.gitlab_client.gitlab.Gitlab")
def test_gitlab_client_all(mock_gitlab):
    mock_project = MagicMock()
    mock_gitlab.return_value.projects.get.return_value = mock_project
    client = GitLabClient()
    client.get_open_ai_issues()
    client.create_merge_request("s", "t", "ti", "d")
    mock_file = MagicMock()
    mock_file.decode.return_value = b"content"
    mock_project.files.get.return_value = mock_file
    assert client.get_file_content("path") == "content"
    mock_project.files.get.side_effect = Exception()
    assert client.get_file_content("path") is None
    mock_project.files.get.side_effect = None
    assert client.file_exists("path") is True
    mock_project.files.get.side_effect = Exception()
    assert client.file_exists("path") is False
    mock_project.branches.create.side_effect = None
    assert client.create_branch("b") is True
    mock_project.branches.create.side_effect = Exception()
    assert client.create_branch("b") is False
    mock_project.commits.create.side_effect = None
    assert client.commit_changes("b", "m", []) is True
    mock_project.commits.create.side_effect = Exception()
    assert client.commit_changes("b", "m", []) is False


@patch("src.core.github_client.Github")
@patch("requests.get")
def test_github_client_all(mock_requests_get, mock_github):
    mock_repo = MagicMock()
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient()
    client.get_pull_requests()
    commit = MagicMock()
    mock_repo.get_commit.return_value = commit
    commit.get_combined_status.return_value.state = "failure"
    commit.get_combined_status.return_value.total_count = 1
    assert client.get_pr_status("sha") == "failure"
    commit.get_combined_status.return_value.state = "success"
    commit.get_combined_status.return_value.total_count = 0
    run_fail = MagicMock()
    run_fail.conclusion = "failure"
    commit.get_check_runs.return_value = [run_fail]
    assert client.get_pr_status("sha") == "failure"
    run_pend = MagicMock()
    run_pend.conclusion = "success"
    run_pend.status = "in_progress"
    commit.get_check_runs.return_value = [run_pend]
    assert client.get_pr_status("sha") == "pending"
    run_succ = MagicMock()
    run_succ.conclusion = "success"
    run_succ.status = "completed"
    commit.get_check_runs.return_value = [run_succ]
    assert client.get_pr_status("sha") == "success"
    client.get_pr_diff(1)
    mock_requests_get.return_value.status_code = 200
    mock_requests_get.return_value.text = "patch"
    assert client.get_pr_patch(1) == "patch"
    mock_requests_get.return_value.status_code = 404
    assert client.get_pr_patch(1) is None


def test_jules_client_misc():
    client = JulesClient()

    client.active_sessions = settings.JULES_MAX_CONCURRENT_SESSIONS
    assert client.start_session("t", "c") is None
    client.active_sessions = 0
    client.complete_session("s")


@patch("requests.get")
def test_pr_sync_all_branches(mock_get, tmp_path):
    gl = MagicMock()
    gh = MagicMock()
    state_file = tmp_path / "synced.json"
    state_file.write_text("invalid")
    sync = PRSync(gl, gh, state_file=str(state_file))
    with patch("os.makedirs", side_effect=Exception()):
        sync._save_state()
    pr = MagicMock()
    pr.draft = False
    pr.number = 1
    gh.get_pull_requests.return_value = [pr]
    file_mock = MagicMock()
    file_mock.raw_url = "http://raw"
    gh.get_pr_diff.return_value = [file_mock]
    mock_get.return_value.status_code = 404
    sync.sync_github_to_gitlab()
    mock_get.return_value.status_code = 200
    gl.create_branch.return_value = True
    gl.commit_changes.return_value = True
    gl.create_merge_request.side_effect = Exception()
    sync.sync_github_to_gitlab()


def test_task_monitor_all():
    gl = MagicMock()
    gh = MagicMock()
    ju = MagicMock()
    mon = TaskMonitor(gl, gh, ju)

    # A Success
    issue = MagicMock()
    gl.get_open_ai_issues.return_value = [issue]
    ju.can_start_session.return_value = True
    ju.start_session.return_value = "s1"
    mon.check_and_delegate_gitlab_tasks()

    # A Max
    ju.can_start_session.return_value = False
    mon.check_and_delegate_gitlab_tasks()

    # B Success
    pr = MagicMock()
    pr.draft = False
    pr.number = 1
    gh.get_pull_requests.return_value = [pr]
    gh.get_pr_status.return_value = "failure"
    ju.can_start_session.return_value = True
    ju.start_session.return_value = "s2"
    mon.check_and_fix_github_prs()

    # B Draft
    pr_draft = MagicMock()
    pr_draft.draft = True
    gh.get_pull_requests.return_value = [pr_draft]
    mon.check_and_fix_github_prs()

    # B Max
    pr.draft = False
    gh.get_pull_requests.return_value = [pr]
    ju.can_start_session.return_value = False
    mon.check_and_fix_github_prs()

    # Draft Success
    draft = MagicMock()
    draft.draft = True
    draft.number = 2
    gh.get_pull_requests.return_value = [draft]
    gh.get_pr_status.return_value = "failure"
    ju.can_start_session.return_value = True
    ju.start_session.return_value = "s3"
    mon.check_and_fix_draft_prs()

    # Draft Not Draft
    draft_not = MagicMock()
    draft_not.draft = False
    gh.get_pull_requests.return_value = [draft_not]
    mon.check_and_fix_draft_prs()

    # Draft Max
    draft.draft = True
    gh.get_pull_requests.return_value = [draft]
    ju.can_start_session.return_value = False
    mon.check_and_fix_draft_prs()


@patch("src.main.GitLabClient")
@patch("src.main.GitHubClient")
@patch("src.main.JulesClient")
@patch("src.main.TaskMonitor")
@patch("src.main.PRSync")
@patch("time.sleep", side_effect=[None, InterruptedError])
def test_main_loop(m_sync, m_monitor, m_jules, m_gh, m_gl, m_sleep):
    with pytest.raises(InterruptedError):
        main()


@patch("src.main.GitLabClient", side_effect=Exception("Fail"))
def test_main_error(m_gl):
    with pytest.raises(Exception):
        main()
