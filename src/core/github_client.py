from typing import Any
from github import Github
from src.config import settings

class GitHubClient:
    def __init__(self):
        self.gh = Github(settings.GITHUB_TOKEN)
        self.repo = self.gh.get_repo(settings.GITHUB_REPO)

    def get_pull_requests(self, state: str = "open"):
        """Fetch pull requests from GitHub."""
        return self.repo.get_pulls(state=state)

    def get_pr_status(self, sha: str) -> str:
        """
        Get the CI/CD status of a specific commit/PR.
        Checks both Statuses and Check Runs.
        Returns 'success', 'failure', 'pending', etc.
        """
        commit = self.repo.get_commit(sha)

        # 1. Check Statuses (e.g., from external CI)
        combined_status = commit.get_combined_status()
        if combined_status.state != "success" and combined_status.total_count > 0:
            return combined_status.state

        # 2. Check Check Runs (e.g., GitHub Actions)
        check_runs = commit.get_check_runs()
        for run in check_runs:
            if run.conclusion == "failure":
                return "failure"
            if run.status != "completed":
                return "pending"

        # If no failures and everything is completed/success
        return "success"

    def get_file_content(self, path: str, ref: str) -> str | bytes:
        content = self.repo.get_contents(path, ref=ref).decoded_content
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content

    def get_pr_diff(self, pr_number: int, pr: Any = None):
        """Get the files changed in a Pull Request."""
        if not pr:
            pr = self.repo.get_pull(pr_number)
        return pr.get_files()

    def add_pr_comment(self, pr_number: int, message: str, pr: Any = None):
        """Add a comment to a Pull Request."""
        if not pr:
            pr = self.repo.get_pull(pr_number)
        pr.create_issue_comment(message)

    def close_pr(self, pr_number: int, pr: Any = None):
        """Close a Pull Request."""
        if not pr:
            pr = self.repo.get_pull(pr_number)
        pr.edit(state="closed")

    def get_pull_request(self, pr_number: int) -> Any:
        """Get a single Pull Request object."""
        return self.repo.get_pull(pr_number)
