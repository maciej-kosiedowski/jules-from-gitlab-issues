from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.core.database import Database
from src.utils.logger import logger
from src.config import settings

class TaskMonitor:
    def __init__(self, gl_client: GitLabClient, gh_client: GitHubClient, jules_client: JulesClient, db: Database):
        self.gl_client = gl_client
        self.gh_client = gh_client
        self.jules_client = jules_client
        self.db = db

    def check_and_delegate_gitlab_tasks(self):
        """Module A: GitLab -> Jules"""
        logger.info("Checking for new GitLab tasks with 'AI' label...")
        issues = self.gl_client.get_open_ai_issues()

        for issue in issues:
            # Check if already delegating
            existing = self.db.get_session_by_task(issue.iid, "gitlab_issue")
            if existing:
                continue

            active_count = len(self.db.get_active_sessions())
            if active_count < settings.JULES_MAX_CONCURRENT_SESSIONS:
                logger.info(f"Delegating GitLab issue #{issue.iid} to Jules")

                guidelines = self.gl_client.get_file_content("CONTRIBUTING.md") or                              self.gl_client.get_file_content("GUIDELINES.md") or ""

                prompt = (
                    f"Task: {issue.title}\n\n"
                    f"Description: {issue.description}\n\n"
                    f"Guidelines:\n{guidelines}\n\n"
                    "Instruction: Complete the task according to the attached guidelines. "
                    "Run linters before finishing. "
                    "Perform a critical self-review of your changes for security and performance before submitting."
                )

                session = self.jules_client.create_session(prompt, f"GitLab Issue #{issue.iid}: {issue.title}")
                if session:
                    session_id = session.get("id")
                    self.db.add_session(session_id, issue.iid, "gitlab_issue")
                    logger.info(f"Started Jules session {session_id} for GitLab issue #{issue.iid}")
            else:
                logger.warning("Max concurrent Jules sessions reached.")
                break

    def check_and_fix_github_prs(self):
        """Module B: GitHub Maintenance (Fixing Red PRs)"""
        logger.info("Checking for RED GitHub Pull Requests...")
        prs = self.gh_client.get_pull_requests(state="open")

        for pr in prs:
            # Check if already delegating
            existing = self.db.get_session_by_task(pr.number, "github_pr")
            if existing:
                continue

            status = self.gh_client.get_pr_status(pr.head.sha)
            if status == "failure":
                active_count = len(self.db.get_active_sessions())
                if active_count < settings.JULES_MAX_CONCURRENT_SESSIONS:
                    logger.info(f"PR #{pr.number} is RED. Delegating fix to Jules.")

                    prompt = (
                        f"Fix PR #{pr.number}: {pr.title}\n\n"
                        f"Current status: RED\n\n"
                        "Instruction: Analyze error logs and implement fixes to make the PR status GREEN. "
                        "Run linters. "
                        "Perform a critical self-review of your changes for security and performance before submitting."
                    )

                    session = self.jules_client.create_session(prompt, f"Fix GH PR #{pr.number}: {pr.title}", branch=pr.head.ref)
                    if session:
                        session_id = session.get("id")
                        self.db.add_session(session_id, pr.number, "github_pr")
                        self.gh_client.add_pr_comment(pr.number, f"Jules AI has started working on fixing this PR. Session ID: {session_id}")
                        logger.info(f"Started Jules session {session_id} for GitHub PR #{pr.number}")
                else:
                    logger.warning("Max concurrent Jules sessions reached.")
                    break

    def monitor_active_sessions(self):
        """Monitor status of active Jules sessions and update database."""
        active_sessions = self.db.get_active_sessions()
        for session_id, task_id, task_type in active_sessions:
            logger.info(f"Monitoring Jules session {session_id} for {task_type} {task_id}")
            session = self.jules_client.get_session(session_id)
            if not session:
                continue

            # Check if session is finished.
            # Based on the API docs, we might need to check activities or outputs.
            # If outputs contains a pullRequest, it's likely finished or progressing.
            outputs = session.get("outputs", [])
            has_pr = any("pullRequest" in o for o in outputs)

            # For simplicity, if it has a PR or some final state, we mark it completed.
            # In a real scenario, we'd check if the activities show 'COMPLETED'.
            if has_pr:
                logger.info(f"Session {session_id} finished (PR created).")
                self.db.update_session_status(session_id, "completed")
                if task_type == "github_pr":
                    self.gh_client.add_pr_comment(int(task_id), "Jules AI has finished working on this PR. Please review the changes.")

            # We could also check for errors in activities
