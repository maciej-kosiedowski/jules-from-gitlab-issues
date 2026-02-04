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

    def get_pr_diff(self, pr_number: int):
        """Get the files changed in a Pull Request."""
        pr = self.repo.get_pull(pr_number)
        return pr.get_files()

    def get_pr_patch(self, pr_number: int):
        """Get the patch format of a PR."""
        import requests
        url = f"https://api.github.com/repos/{settings.GITHUB_REPO}/pulls/{pr_number}"
        headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.patch"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
