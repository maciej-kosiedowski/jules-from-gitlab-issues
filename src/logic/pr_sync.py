import json
import os
import re
from src.config import settings
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.database import Database
from src.utils.logger import logger

class PRSync:
    def __init__(self, gl_client: GitLabClient, gh_client: GitHubClient, db: Database, state_file: str = "data/synced_prs.json"):
        self.gl_client = gl_client
        self.gh_client = gh_client
        self.db = db
        self.state_file = state_file
        self._migrate_from_json()

    def _migrate_from_json(self):
        if os.path.exists(self.state_file):
            try:
                logger.info(f"Migrating state from {self.state_file} to database...")
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for pr_num in data:
                            self.db.add_synced_pr(int(pr_num), 0)
                    elif isinstance(data, dict):
                        for gh_pr_id, gl_mr_iid in data.items():
                            self.db.add_synced_pr(int(gh_pr_id), int(gl_mr_iid))

                # Rename file instead of deleting to be safe
                os.rename(self.state_file, f"{self.state_file}.bak")
                logger.info(f"Migration complete. Original file renamed to {self.state_file}.bak")
            except Exception as e:
                logger.error(f"Error during migration from {self.state_file}: {e}")

    def sync_github_to_gitlab(self):
        """Module C: GitHub -> GitLab Sync"""
        logger.info("Checking for GitHub PRs to sync to GitLab...")
        prs = self.gh_client.get_pull_requests(state="open")
        synced_prs = self.db.get_all_synced_prs()

        for pr in prs:
            if pr.draft:
                continue

            if pr.number in synced_prs:
                continue

            # Detect GitLab Issue ID
            # Priority 1: Check database (sessions or synced_prs)
            gl_issue_id = self.db.get_gl_issue_id_by_gh_pr(pr.number)

            # Priority 2: Regex on title
            if not gl_issue_id:
                issue_match = re.search(r"GL Issue #(\d+)", pr.title)
                gl_issue_id = int(issue_match.group(1)) if issue_match else None

            if gl_issue_id and self.gl_client.has_open_mr(gl_issue_id):
                logger.info(f"GitLab issue #{gl_issue_id} already has an open MR. Skipping sync for GH PR #{pr.number}")
                continue

            logger.info(f"Syncing GitHub PR #{pr.number} to GitLab MR")

            files = self.gh_client.get_pr_diff(pr.number)
            actions = []

            for f in files:
                try:
                    if f.status == "removed":
                        actions.append({
                            "action": "delete",
                            "file_path": f.filename
                        })
                    elif f.status == "renamed":
                        content = self.gh_client.get_file_content(f.filename, pr.head.sha)
                        actions.append({
                            "action": "move",
                            "file_path": f.filename,
                            "previous_path": f.previous_filename,
                            "content": content
                        })
                    else: # added or modified
                        content = self.gh_client.get_file_content(f.filename, pr.head.sha)
                        action = "update" if self.gl_client.file_exists(f.filename) else "create"
                        actions.append({
                            "action": action,
                            "file_path": f.filename,
                            "content": content
                        })
                except Exception as e:
                    logger.error(f"Error retrieving content for file {f.filename} in PR #{pr.number}: {e}")

            if not actions:
                logger.warning(f"No actions could be generated for PR #{pr.number}")
                continue

            source_branch = f"sync-gh-{pr.number}"
            if self.gl_client.create_branch(source_branch):
                if self.gl_client.commit_changes(source_branch, f"Sync from GH PR #{pr.number}", actions):
                    try:
                        description = f"Synchronized from GitHub PR #{pr.number}\n\nOriginal link: {pr.html_url}"
                        if gl_issue_id:
                            # Use gl_issue_id which we ensured is the GitLab task number
                            description = f"Closes #{gl_issue_id}\n\n" + description

                        mr = self.gl_client.create_merge_request(
                            source_branch=source_branch,
                            target_branch=settings.STARTING_BRANCH_NAME,
                            title=f"Sync: {pr.title}",
                            description=description
                        )
                        self.db.add_synced_pr(pr.number, mr.iid, gl_issue_id)
                        logger.info(f"Successfully created GitLab MR !{mr.iid} for GitHub PR #{pr.number}")
                    except Exception as e:
                        logger.error(f"Failed to create GitLab MR for PR #{pr.number}: {e}")

    def sync_gitlab_closures_to_github(self):
        """Track GitLab MR status and close corresponding GitHub PR if GitLab MR is closed/merged."""
        logger.info("Checking for GitLab MR closures to sync back to GitHub...")
        synced_prs = self.db.get_all_synced_prs()
        for gh_pr_id, gl_mr_iid in synced_prs.items():
            if gl_mr_iid == 0:
                continue # Skip old format entries we can't track

            mr = self.gl_client.get_merge_request(gl_mr_iid)
            if mr and mr.state in ["closed", "merged"]:
                logger.info(f"GitLab MR !{gl_mr_iid} is {mr.state}. Closing GitHub PR #{gh_pr_id}")
                try:
                    self.gh_client.close_pr(gh_pr_id)
                    # Remove from synced_prs so we don't keep checking it
                    self.db.delete_synced_pr(gh_pr_id)
                except Exception as e:
                    logger.error(f"Failed to close GitHub PR #{gh_pr_id}: {e}")

    def check_prs_for_rebase_and_conflicts(self):
        """Check all open PRs (including drafts) for merge conflicts and request fixes."""
        logger.info("Checking for PRs with merge conflicts...")
        prs = self.gh_client.get_pull_requests(state="open")

        request_message = (
            "Hello @jules! It looks like this PR has some merge conflicts or needs a rebase. "
            "Could you please resolve them, ensure all tests pass, and force push the clean changes? "
            "Thank you!"
        )

        for pr in prs:
            # Skip if mergeable state is unknown (being computed)
            if pr.mergeable is None:
                continue

            if pr.mergeable is False:
                logger.info(f"PR #{pr.number} has merge conflicts. Checking if we already commented...")
                comments = list(pr.get_issue_comments())
                last_comment = comments[-1] if comments else None

                # Check if the last comment is already our request
                if last_comment and request_message in last_comment.body:
                    logger.info(f"Already requested fixes for PR #{pr.number}. Skipping.")
                    continue

                logger.info(f"Posting comment on PR #{pr.number} requesting fixes from @jules.")
                try:
                    pr.create_issue_comment(request_message)
                except Exception as e:
                    logger.error(f"Failed to post comment on PR #{pr.number}: {e}")

    def process_flow_e(self):
        """Flow E: Check if GitHub PRs can be updated (merged from base) and do so if no conflicts."""
        logger.info("Executing Flow E: Checking for outdated PRs...")
        prs = self.gh_client.get_pull_requests(state="open")

        for pr in prs:
            if pr.mergeable_state == 'behind':
                logger.info(f"PR #{pr.number} is behind base branch. Attempting update via API...")
                try:
                    if self.gh_client.update_branch(pr.number):
                        logger.info(f"Successfully updated PR #{pr.number}.")
                    else:
                        logger.error(f"Failed to update PR #{pr.number}.")
                except Exception as e:
                    logger.error(f"Error updating PR #{pr.number}: {e}")
            elif pr.mergeable_state == 'dirty':
                logger.info(f"PR #{pr.number} has conflicts. Skipping update.")
