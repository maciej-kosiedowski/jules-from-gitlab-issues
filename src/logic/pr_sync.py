import json
import os
import requests
from src.config import settings
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.utils.logger import logger

class PRSync:
    def __init__(self, gl_client: GitLabClient, gh_client: GitHubClient, state_file: str = "data/synced_prs.json"):
        self.gl_client = gl_client
        self.gh_client = gh_client
        self.state_file = state_file
        self.synced_prs: dict[str, int] = self._load_state()

    def _load_state(self) -> dict[str, int]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # Convert old list format to dict (we don't know the GL MR IID, so we'll use 0)
                        return {str(pr_num): 0 for pr_num in data}
                    return data
            except Exception as e:
                logger.error(f"Error loading state from {self.state_file}: {e}")
        return {}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.synced_prs, f)
        except Exception as e:
            logger.error(f"Error saving state to {self.state_file}: {e}")

    def sync_github_to_gitlab(self):
        """Module C: GitHub -> GitLab Sync"""
        logger.info("Checking for GitHub PRs to sync to GitLab...")
        prs = self.gh_client.get_pull_requests(state="open")

        for pr in prs:
            if not pr.draft and str(pr.number) not in self.synced_prs:
                logger.info(f"Syncing GitHub PR #{pr.number} to GitLab MR")

                files = self.gh_client.get_pr_diff(pr.number)
                actions = []
                headers = {"Authorization": f"token {settings.GITHUB_TOKEN}"}

                for f in files:
                    content_resp = requests.get(f.raw_url, headers=headers)
                    if content_resp.status_code == 200:
                        action = "update" if self.gl_client.file_exists(f.filename) else "create"
                        actions.append({
                            "action": action,
                            "file_path": f.filename,
                            "content": content_resp.text
                        })

                if not actions:
                    logger.warning(f"No files could be retrieved for PR #{pr.number}")
                    continue

                source_branch = f"sync-gh-{pr.number}"
                if self.gl_client.create_branch(source_branch):
                    if self.gl_client.commit_changes(source_branch, f"Sync from GH PR #{pr.number}", actions):
                        try:
                            mr = self.gl_client.create_merge_request(
                                source_branch=source_branch,
                                target_branch="main",
                                title=f"Sync: {pr.title}",
                                description=f"Synchronized from GitHub PR #{pr.number}\n\nOriginal link: {pr.html_url}"
                            )
                            self.synced_prs[str(pr.number)] = mr.iid
                            self._save_state()
                            logger.info(f"Successfully created GitLab MR !{mr.iid} for GitHub PR #{pr.number}")
                        except Exception as e:
                            logger.error(f"Failed to create GitLab MR for PR #{pr.number}: {e}")

    def sync_gitlab_closures_to_github(self):
        """Track GitLab MR status and close corresponding GitHub PR if GitLab MR is closed/merged."""
        logger.info("Checking for GitLab MR closures to sync back to GitHub...")
        for gh_pr_num_str, gl_mr_iid in list(self.synced_prs.items()):
            if gl_mr_iid == 0:
                continue # Skip old format entries we can't track

            mr = self.gl_client.get_merge_request(gl_mr_iid)
            if mr and mr.state in ["closed", "merged"]:
                logger.info(f"GitLab MR !{gl_mr_iid} is {mr.state}. Closing GitHub PR #{gh_pr_num_str}")
                try:
                    self.gh_client.close_pr(int(gh_pr_num_str))
                    # Remove from synced_prs so we don't keep checking it
                    del self.synced_prs[gh_pr_num_str]
                    self._save_state()
                except Exception as e:
                    logger.error(f"Failed to close GitHub PR #{gh_pr_num_str}: {e}")
