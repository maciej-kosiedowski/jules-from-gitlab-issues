import re
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.core.database import Database, SessionStatus
from src.utils.logger import logger
from src.config import settings

class TaskMonitor:
    def __init__(self, gl_client: GitLabClient, gh_client: GitHubClient, jules_client: JulesClient, db: Database):
        self.gl_client = gl_client
        self.gh_client = gh_client
        self.jules_client = jules_client
        self.db = db

    def check_and_delegate_tasks(self):
        """Unified delegation logic for Module A and Module B."""
        active_count = self.jules_client.get_active_sessions_count_from_api()

        logger.info("Checking for new GitLab tasks with 'AI' label...")
        issues = self.gl_client.get_open_ai_issues()
        for issue in issues:
            if active_count >= settings.JULES_MAX_CONCURRENT_SESSIONS:
                logger.warning(f"Max concurrent Jules sessions reached ({active_count}).")
                break

            if not self.db.get_session_by_task(issue.iid, "gitlab_issue"):
                if self.gl_client.has_open_mr(issue.iid):
                    logger.info(f"GitLab issue #{issue.iid} already has an open MR. Skipping delegation.")
                    continue
                logger.info(f"Delegating GitLab issue #{issue.iid} to Jules")
                guidelines = self.gl_client.get_file_content("CONTRIBUTING.md") or \
                             self.gl_client.get_file_content("GUIDELINES.md") or ""
                prompt = (
                    f"Task: {issue.title}\n\nDescription: {issue.description}\n\nGuidelines:\n{guidelines}\n\n"
                    "Instruction: Complete the task according to the attached guidelines. Run linters. Self-review."
                )
                session = self.jules_client.create_session(
                    prompt,
                    f"GL Issue #{issue.iid}: {issue.title}",
                    settings.STARTING_BRANCH_NAME,
                )
                if session:
                    session_id = session.get("id")
                    self.db.add_session(session_id, str(issue.iid), "gitlab_issue")
                    active_count += 1

        logger.info("Checking for RED GitHub Pull Requests...")
        prs = self.gh_client.get_pull_requests(state="open")
        for pr in prs:
            if active_count >= settings.JULES_MAX_CONCURRENT_SESSIONS:
                logger.warning(f"Max concurrent Jules sessions reached ({active_count}).")
                break

            if not self.db.get_session_by_task(pr.number, "github_pr"):
                status = self.gh_client.get_pr_status(pr.head.sha)
                if status == "failure":
                    logger.info(f"PR #{pr.number} is RED. Delegating fix to Jules.")
                    prompt = (
                        f"Fix PR #{pr.number}: {pr.title}\n\nInstruction: Fix logs to make GREEN. Run linters. Self-review."
                    )
                    session = self.jules_client.create_session(prompt, f"Fix GH PR #{pr.number}: {pr.title}", branch=pr.head.ref)
                    if session:
                        session_id = session.get("id")
                        self.db.add_session(session_id, str(pr.number), "github_pr", github_pr_id=pr.number)
                        self.gh_client.add_pr_comment(pr.number, f"Jules AI has started working on fixing this PR. Session ID: {session_id}")
                        active_count += 1

    def monitor_active_sessions(self):
        """Monitor status of active Jules sessions and update database."""
        active_sessions = self.db.get_active_sessions()
        for session_id, task_id, task_type, github_pr_id, gitlab_mr_id in active_sessions:
            logger.info(f"Monitoring Jules session {session_id} for {task_type} {task_id}")
            session = self.jules_client.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found in API. Marking as FAILED.")
                self.db.update_session_status(session_id, SessionStatus.FAILED)
                continue

            outputs = session.get("outputs", [])
            pr_output = next((o.get("pullRequest") for o in outputs if "pullRequest" in o), None)

            if pr_output:
                logger.info(f"Session {session_id} finished (PR created).")
                self.db.update_session_status(session_id, SessionStatus.COMPLETED)

                # Extract PR number from pr_output if possible
                extracted_pr_id = None
                if isinstance(pr_output, dict):
                    extracted_pr_id = pr_output.get("number")
                    if not extracted_pr_id and "url" in pr_output:
                        match = re.search(r"/pull/(\d+)", pr_output["url"])
                        if match:
                            extracted_pr_id = int(match.group(1))

                if extracted_pr_id:
                    logger.info(f"Detected GitHub PR #{extracted_pr_id} for session {session_id}")
                    self.db.update_session_ids(session_id, github_pr_id=extracted_pr_id)

                if task_type == "github_pr":
                    self.gh_client.add_pr_comment(int(task_id), "Jules AI has finished working on this PR. Please review the changes.")
                continue

            # Check activities for failures
            activities = self.jules_client.list_activities(session_id)
            # If we see any activity indicating failure or if no activity for a long time
            # For simplicity, we'll just check if there's an activity of type 'ERROR' if it existed
            # But the API docs didn't specify error types clearly.
            # We'll just log progress.
            if activities:
                last_activity = activities[0] # Usually sorted by time descending?
                logger.debug(f"Session {session_id} last activity: {last_activity.get('type')}")
