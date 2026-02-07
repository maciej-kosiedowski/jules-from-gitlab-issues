import subprocess
import tempfile
import shutil
from github import Github
from src.config import settings
from src.utils.logger import logger

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

    def get_pr_diff(self, pr_number: int):
        """Get the files changed in a Pull Request."""
        pr = self.repo.get_pull(pr_number)
        return pr.get_files()

    def add_pr_comment(self, pr_number: int, message: str):
        """Add a comment to a Pull Request."""
        pr = self.repo.get_pull(pr_number)
        pr.create_issue_comment(message)

    def close_pr(self, pr_number: int):
        """Close a Pull Request."""
        pr = self.repo.get_pull(pr_number)
        pr.edit(state="closed")

    def update_branch(self, pr_number: int) -> bool:
        """Update a Pull Request branch with the base branch."""
        pr = self.repo.get_pull(pr_number)
        return pr.update_branch()

    def rebase_pr(self, pr_number: int) -> bool:
        """Rebase a Pull Request branch onto the base branch using Git CLI."""
        try:
            pr = self.repo.get_pull(pr_number)
        except Exception as e:
            logger.error(f"Failed to fetch PR #{pr_number}: {e}")
            return False

        temp_dir = tempfile.mkdtemp()
        try:
            # 1. Prepare Clone URL with Auth
            clone_url = pr.head.repo.clone_url
            if clone_url.startswith("https://"):
                auth_url = clone_url.replace("https://", f"https://x-access-token:{settings.GITHUB_TOKEN}@")
            else:
                logger.error(f"Cannot rebase PR #{pr_number}: Clone URL is not HTTPS.")
                return False

            base_ref = pr.base.ref
            head_ref = pr.head.ref

            # 2. Clone Head Repo
            logger.info(f"Cloning {pr.head.repo.full_name} to temp dir...")
            subprocess.run(["git", "clone", auth_url, temp_dir], check=True, capture_output=True)

            # 3. Configure Git
            subprocess.run(["git", "config", "user.email", "jules@example.com"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Jules AI"], cwd=temp_dir, check=True)

            # 4. Checkout Head Branch
            logger.info(f"Checking out {head_ref}...")
            subprocess.run(["git", "checkout", head_ref], cwd=temp_dir, check=True, capture_output=True)

            # 5. Add Upstream/Base Remote if different
            base_repo_url = pr.base.repo.clone_url
            target_remote = "origin"

            if base_repo_url != pr.head.repo.clone_url:
                if base_repo_url.startswith("https://"):
                    base_auth_url = base_repo_url.replace("https://", f"https://x-access-token:{settings.GITHUB_TOKEN}@")
                    subprocess.run(["git", "remote", "add", "upstream", base_auth_url], cwd=temp_dir, check=True)
                    target_remote = "upstream"
                else:
                    logger.error("Base repo URL is not HTTPS")
                    return False

            # 6. Fetch Base Ref (updates FETCH_HEAD)
            logger.info(f"Fetching {base_ref} from {target_remote}...")
            subprocess.run(["git", "fetch", target_remote, base_ref], cwd=temp_dir, check=True, capture_output=True)

            # 7. Rebase onto FETCH_HEAD
            logger.info(f"Rebasing {head_ref} onto {target_remote}/{base_ref}...")
            rebase_res = subprocess.run(
                ["git", "rebase", "FETCH_HEAD"],
                cwd=temp_dir,
                capture_output=True,
                text=True
            )

            if rebase_res.returncode != 0:
                logger.warning(f"Rebase failed for PR #{pr_number}: {rebase_res.stderr} {rebase_res.stdout}")
                subprocess.run(["git", "rebase", "--abort"], cwd=temp_dir)
                return False

            # 8. Force Push
            logger.info(f"Pushing force to {head_ref}...")
            push_res = subprocess.run(
                ["git", "push", "--force", "origin", head_ref],
                cwd=temp_dir,
                capture_output=True,
                text=True
            )

            if push_res.returncode != 0:
                logger.error(f"Force push failed for PR #{pr_number}: {push_res.stderr}")
                return False

            logger.info(f"Successfully rebased PR #{pr_number}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed for PR #{pr_number}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error rebasing PR #{pr_number}: {e}")
            return False
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
