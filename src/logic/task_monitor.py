import base64
import mimetypes
import re
import concurrent.futures
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.core.database import Database, SessionStatus
from src.utils.logger import logger
from src.config import settings


class TaskMonitor:
    def __init__(
        self,
        gl_client: GitLabClient,
        gh_client: GitHubClient,
        jules_client: JulesClient,
        db: Database,
    ):
        self.gl_client = gl_client
        self.gh_client = gh_client
        self.jules_client = jules_client
        self.db = db

    def _extract_image_urls(self, text: str) -> list:
        if not text:
            return []
        md_pattern = r"!\[.*?\]\((.*?)\)"
        html_pattern = r'<img\s+[^>]*src="([^"]+)"'
        urls = re.findall(md_pattern, text)
        urls.extend(re.findall(html_pattern, text))
        return urls

    def _prepare_attachments_and_history(self, issue):
        notes = self.gl_client.get_issue_notes(issue.iid)

        conversation = []
        all_text_for_images = [issue.description or ""]

        for note in notes:
            # Check if system note
            is_system = getattr(note, "system", False)
            if is_system:
                continue

            author_name = (
                note.author["name"]
                if isinstance(note.author, dict)
                else note.author.name
            )
            body = note.body
            created_at = note.created_at

            conversation.append(
                f"Comment by {author_name} at {created_at}:\n{body}\n---"
            )
            all_text_for_images.append(body or "")

        history_text = "\n".join(conversation)

        image_urls = set()
        for text in all_text_for_images:
            urls = self._extract_image_urls(text)
            for url in urls:
                image_urls.add(url)

        attachments = []
        for url in image_urls:
            content = self.gl_client.download_file(url)
            if content:
                mime_type, _ = mimetypes.guess_type(url)
                if not mime_type:
                    mime_type = "application/octet-stream"

                b64_data = base64.b64encode(content).decode("utf-8")
                attachments.append(
                    {
                        "name": url.split("/")[-1],
                        "mimeType": mime_type,
                        "data": b64_data,
                    }
                )

        return history_text, attachments

    def check_and_delegate_tasks(self):
        """Unified delegation logic for Module A and Module B."""
        active_count = self.jules_client.get_active_sessions_count_from_api()

        logger.info("Checking for new GitLab tasks with 'AI' label...")
        issues = self.gl_client.get_open_ai_issues()
        for issue in issues:
            if active_count >= settings.JULES_MAX_CONCURRENT_SESSIONS:
                logger.warning(
                    f"Max concurrent Jules sessions reached ({active_count})."
                )
                break

            if not self.db.get_session_by_task(issue.iid, "gitlab_issue"):
                if self.gl_client.has_open_mr(issue.iid):
                    logger.info(
                        f"GitLab issue #{issue.iid} already has an open MR. "
                        "Skipping delegation."
                    )
                    continue
                logger.info(f"Delegating GitLab issue #{issue.iid} to Jules")
                guidelines = (
                    self.gl_client.get_file_content("CONTRIBUTING.md")
                    or self.gl_client.get_file_content("GUIDELINES.md")
                    or ""
                )

                history_text, attachments = (
                    self._prepare_attachments_and_history(issue)
                )

                prompt = (
                    f"Task: {issue.title}\n\n"
                    f"Description: {issue.description}\n\n"
                    f"Conversation History:\n{history_text}\n\n"
                    f"Guidelines:\n{guidelines}\n\n"
                    "Instruction: Complete the task according to the attached "
                    "guidelines. Run linters. Self-review."
                )
                session = self.jules_client.create_session(
                    prompt,
                    f"GL Issue #{issue.iid}: {issue.title}",
                    settings.STARTING_BRANCH_NAME,
                    attachments=attachments,
                )
                if session:
                    session_id = session.get("id")
                    self.db.add_session(
                        session_id, str(issue.iid), "gitlab_issue"
                    )
                    active_count += 1

        logger.info("Checking for RED GitHub Pull Requests...")
        prs = self.gh_client.get_pull_requests(state="open")
        for pr in prs:
            if active_count >= settings.JULES_MAX_CONCURRENT_SESSIONS:
                logger.warning(
                    f"Max concurrent Jules sessions reached ({active_count})."
                )
                break

            if not self.db.get_session_by_task(pr.number, "github_pr"):
                status = self.gh_client.get_pr_status(pr.head.sha)
                if status == "failure":
                    logger.info(
                        f"PR #{pr.number} is RED. Delegating fix to Jules."
                    )
                    prompt = (
                        f"Fix PR #{pr.number}: {pr.title}\n\n"
                        "Instruction: Fix logs to make GREEN. Run linters. "
                        "Self-review."
                    )
                    session = self.jules_client.create_session(
                        prompt,
                        f"Fix GH PR #{pr.number}: {pr.title}",
                        branch=pr.head.ref,
                    )
                    if session:
                        session_id = session.get("id")
                        self.db.add_session(
                            session_id,
                            str(pr.number),
                            "github_pr",
                            github_pr_id=pr.number,
                        )
                        self.gh_client.add_pr_comment(
                            pr.number,
                            f"Jules AI has started working on fixing this PR. "
                            f"Session ID: {session_id}",
                        )
                        active_count += 1

    def _process_active_session(self, session_data):
        """Process a single active session."""
        (
            session_id,
            task_id,
            task_type,
            github_pr_id,
            gitlab_mr_id,
        ) = session_data
        logger.info(
            f"Monitoring Jules session {session_id} "
            f"for {task_type} {task_id}"
        )
        session = self.jules_client.get_session(session_id)
        if not session:
            logger.warning(
                f"Session {session_id} not found in API. Marking as FAILED."
            )
            self.db.update_session_status(session_id, SessionStatus.FAILED)
            return

        outputs = session.get("outputs", [])
        pr_generator = (
            o.get("pullRequest") for o in outputs if "pullRequest" in o
        )
        pr_output = next(pr_generator, None)

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
                logger.info(
                    f"Detected GitHub PR #{extracted_pr_id} "
                    f"for session {session_id}"
                )
                self.db.update_session_ids(
                    session_id, github_pr_id=extracted_pr_id
                )

            if task_type == "github_pr":
                self.gh_client.add_pr_comment(
                    int(task_id),
                    "Jules AI has finished working on this PR. "
                    "Please review the changes.",
                )
            return

        # Check activities for failures
        activities = self.jules_client.list_activities(session_id)
        if activities:
            last_activity = activities[0]  # Usually sorted by time descending?
            logger.debug(
                f"Session {session_id} last activity: "
                f"{last_activity.get('type')}"
            )

    def monitor_active_sessions(self):
        """Monitor status of active Jules sessions and update database."""
        active_sessions = self.db.get_active_sessions()

        # Use ThreadPoolExecutor to process sessions in parallel
        # Max workers set to 10 to balance concurrency with system limits
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(
                self._process_active_session, active_sessions
            )
            # Iterate to ensure all tasks are executed and propagate exceptions
            for _ in results:
                pass
