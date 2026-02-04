from concurrent.futures import ThreadPoolExecutor
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.utils.logger import logger
from src.config import settings


class TaskMonitor:
    def __init__(
        self,
        gl_client: GitLabClient,
        gh_client: GitHubClient,
        jules_client: JulesClient,
    ):
        self.gl_client = gl_client
        self.gh_client = gh_client
        self.jules_client = jules_client
        self.executor = ThreadPoolExecutor(
            max_workers=settings.JULES_MAX_CONCURRENT_SESSIONS
        )

    def check_and_delegate_gitlab_tasks(self):
        """Module A: GitLab -> Jules"""
        logger.info("Checking for new GitLab tasks with 'AI' label...")
        issues = self.gl_client.get_open_ai_issues()

        for issue in issues:
            if self.jules_client.can_start_session():
                logger.info(f"Delegating GitLab issue #{issue.iid} to Jules")

                guidelines = (
                    self.gl_client.get_file_content("CONTRIBUTING.md")
                    or self.gl_client.get_file_content("GUIDELINES.md")
                    or ""
                )

                prompt = (
                    f"Task: {issue.title}\n\n"
                    f"Description: {issue.description}\n\n"
                    f"Guidelines:\n{guidelines}\n\n"
                    "Instruction: Perform the task according to the attached guidelines. "
                    "Run linters before finishing. "
                    "Perform a critical self-review of your changes for security and performance before approving."
                )

                session_id = self.jules_client.start_session(issue.title, prompt)
                if session_id:
                    self.executor.submit(
                        self.jules_client.wait_for_completion, session_id
                    )
            else:
                logger.warning("No available Jules sessions to delegate GitLab task.")
                break

    def check_and_fix_github_prs(self):
        """Module B: GitHub Maintenance (Fixing Red PRs)"""
        logger.info("Checking for RED GitHub Pull Requests...")
        prs = self.gh_client.get_pull_requests(state="open")

        for pr in prs:
            if pr.draft:
                continue

            status = self.gh_client.get_pr_status(pr.head.sha)
            if status == "failure":
                if self.jules_client.can_start_session():
                    logger.info(f"PR #{pr.number} is RED. Delegating fix to Jules.")

                    prompt = (
                        f"Fix PR #{pr.number}: {pr.title}\n\n"
                        f"Current status: RED\n\n"
                        "Instruction: Analyze error logs and implement fixes to the PR so that the status changes to GREEN. "
                        "Run linters. "
                        "Perform a critical self-review of your changes for security and performance before approving."
                    )

                    session_id = self.jules_client.start_session(
                        f"Fix PR #{pr.number}", prompt
                    )
                    if session_id:
                        self.executor.submit(
                            self.jules_client.wait_for_completion, session_id
                        )
                else:
                    logger.warning("No available Jules sessions to fix PR.")
                    break

    def check_and_fix_draft_prs(self):
        """New Task: Monitor Draft PRs with RED status for self-analysis and fix."""
        logger.info("Checking for RED GitHub Draft Pull Requests...")
        prs = self.gh_client.get_pull_requests(state="open")

        for pr in prs:
            if not pr.draft:
                continue

            status = self.gh_client.get_pr_status(pr.head.sha)
            if status == "failure":
                if self.jules_client.can_start_session():
                    logger.info(
                        f"Draft PR #{pr.number} is RED. Delegating self-analysis and fix to Jules."
                    )

                    prompt = (
                        f"Analyze and Fix Draft PR #{pr.number}: {pr.title}\n\n"
                        f"Current status: RED\n\n"
                        "Instruction: Perform a self-analysis of the problem. "
                        "Try to fix tests or, better yet, introduce a logic change that resolves the issue. "
                        "Run linters. "
                        "Perform a critical self-review of your changes for security and performance before approving."
                    )

                    session_id = self.jules_client.start_session(
                        f"Analyze Draft PR #{pr.number}", prompt
                    )
                    if session_id:
                        self.executor.submit(
                            self.jules_client.wait_for_completion, session_id
                        )
                else:
                    logger.warning("No available Jules sessions to fix Draft PR.")
                    break
