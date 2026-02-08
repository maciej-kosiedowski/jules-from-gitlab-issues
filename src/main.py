import time
from src.config import settings
from src.utils.logger import logger
from src.core.gitlab_client import GitLabClient
from src.core.github_client import GitHubClient
from src.core.jules_client import JulesClient
from src.core.database import Database
from src.logic.task_monitor import TaskMonitor
from src.logic.pr_sync import PRSync

def main():
    logger.info("Starting AI Task Orchestrator (ATO)...")

    try:
        db = Database()
        gl_client = GitLabClient()
        gh_client = GitHubClient()
        jules_client = JulesClient()

        task_monitor = TaskMonitor(gl_client, gh_client, jules_client, db)
        pr_sync = PRSync(gl_client, gh_client, db)

        while True:
            logger.info("Starting cycle...")

            # Monitor existing sessions
            task_monitor.monitor_active_sessions()

            # Delegate new tasks (Module A & B)
            task_monitor.check_and_delegate_tasks()

            # Module C
            pr_sync.sync_github_to_gitlab()
            pr_sync.sync_gitlab_closures_to_github()
            pr_sync.sync_github_merges_to_gitlab()
            pr_sync.check_prs_for_rebase_and_conflicts()

            logger.info(f"Cycle complete. Sleeping for {settings.POLLING_INTERVAL} seconds.")
            time.sleep(settings.POLLING_INTERVAL)

    except Exception as e:
        logger.error(f"Critical error in main loop: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
