import time
from src.config import settings
from src.utils.logger import logger
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.logic.task_monitor import TaskMonitor
from src.logic.pr_sync import PRSync


def main():
    logger.info("Starting AI Task Orchestrator (ATO)...")

    try:
        gl_client = GitLabClient()
        gh_client = GitHubClient()
        jules_client = JulesClient()

        task_monitor = TaskMonitor(gl_client, gh_client, jules_client)
        pr_sync = PRSync(gl_client, gh_client)

        while True:
            logger.info("Starting cycle...")

            # Module A & B
            task_monitor.check_and_delegate_gitlab_tasks()
            task_monitor.check_and_fix_github_prs()

            # New Task: Draft Maintenance
            task_monitor.check_and_fix_draft_prs()

            # Module C
            pr_sync.sync_github_to_gitlab()

            logger.info(
                f"Cycle complete. Sleeping for {settings.POLLING_INTERVAL} seconds."
            )
            time.sleep(settings.POLLING_INTERVAL)

    except Exception as e:
        logger.error(f"Critical error in main loop: {e}", exc_info=True)
        # In Docker, this crash will trigger a restart if configured
        raise


if __name__ == "__main__":  # pragma: no cover
    main()
