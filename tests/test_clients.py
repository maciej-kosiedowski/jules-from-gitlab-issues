from unittest.mock import MagicMock, patch
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient

@patch("src.core.gitlab_client.gitlab.Gitlab")
def test_gitlab_client_methods(mock_gitlab):
    mock_project = MagicMock()
    mock_gitlab.return_value.projects.get.return_value = mock_project

    client = GitLabClient()

    # Test file_exists
    mock_project.files.get.return_value = MagicMock()
    assert client.file_exists("existing.txt") is True

    mock_project.files.get.side_effect = Exception("Not found")
    assert client.file_exists("missing.txt") is False

@patch("src.core.github_client.Github")
def test_github_client_status(mock_github):
    mock_repo = MagicMock()
    mock_github.return_value.get_repo.return_value = mock_repo
    mock_commit = MagicMock()
    mock_repo.get_commit.return_value = mock_commit

    client = GitHubClient()

    # Test Statuses failure
    mock_commit.get_combined_status.return_value.state = "failure"
    mock_commit.get_combined_status.return_value.total_count = 1
    assert client.get_pr_status("sha123") == "failure"

    # Test Check Runs failure
    mock_commit.get_combined_status.return_value.state = "success"
    mock_commit.get_combined_status.return_value.total_count = 0
    mock_run = MagicMock()
    mock_run.conclusion = "failure"
    mock_commit.get_check_runs.return_value = [mock_run]
    assert client.get_pr_status("sha123") == "failure"

@patch("requests.post")
@patch("requests.get")
def test_jules_client_sessions(mock_get, mock_post):
    # Mock responses first to avoid infinite loops in can_start_session
    mock_get.return_value.json.return_value = {
        "sources": [{"name": "sources/github/owner/repo", "id": "github/owner/repo"}],
        "sessions": [],
        "nextPageToken": None
    }
    mock_get.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"id": "sess_1"}
    mock_post.return_value.status_code = 200

    client = JulesClient()
    assert client.can_start_session() is True

    session = client.create_session("test task", "title")
    assert session["id"] == "sess_1"

@patch("src.core.gitlab_client.gitlab.Gitlab")
@patch("src.core.gitlab_client.settings")
def test_gitlab_client_download(mock_settings, mock_gitlab):
    mock_project = MagicMock()
    mock_gitlab.return_value.projects.get.return_value = mock_project
    mock_project.web_url = "https://gitlab.com/group/project"

    mock_settings.GITLAB_URL = "https://gitlab.com"
    mock_settings.GITLAB_TOKEN = "token"
    mock_settings.GITLAB_PROJECT_ID = 123

    client = GitLabClient()

    # Case 1: Uploads URL
    client.download_file("/uploads/123/image.png")
    args, _ = mock_gitlab.return_value.session.get.call_args
    assert args[0] == "https://gitlab.com/group/project/uploads/123/image.png"

    # Case 2: Other relative path
    client.download_file("/api/v4/users")
    args, _ = mock_gitlab.return_value.session.get.call_args
    assert args[0] == "https://gitlab.com/api/v4/users"
