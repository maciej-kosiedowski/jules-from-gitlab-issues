import time
import tempfile
import shutil
import os
import sys
import logging
from unittest.mock import MagicMock
from src.core.database import Database, SessionStatus
from src.logic.pr_sync import PRSync

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

# Disable logging
logging.getLogger("ato").setLevel(logging.CRITICAL)

def benchmark():
    # Setup temporary directory for DB
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    try:
        # Initialize Database
        db = Database(db_path)

        # Data sizes
        NUM_SYNCED = 1000
        NUM_WITH_SESSION = 1000
        NUM_NO_SESSION = 1000
        TOTAL_PRS = NUM_SYNCED + NUM_WITH_SESSION + NUM_NO_SESSION

        print(f"Setting up DB with {NUM_SYNCED} synced PRs and {NUM_WITH_SESSION} sessions...")

        # Populate DB
        # 1. Synced PRs (IDs 1 to 1000)
        for i in range(1, NUM_SYNCED + 1):
            db.add_synced_pr(i, i + 10000, i + 5000)

        # 2. Sessions (IDs 1001 to 2000) - These have a GitHub PR ID associated
        for i in range(NUM_SYNCED + 1, NUM_SYNCED + NUM_WITH_SESSION + 1):
            db.add_session(
                session_id=f"session_{i}",
                task_id=str(i + 5000),
                task_type="gitlab_issue",
                github_pr_id=i,
                status=SessionStatus.ACTIVE
            )

        # Mock GitHub Client
        gh_client = MagicMock()
        prs = []
        for i in range(1, TOTAL_PRS + 1):
            pr = MagicMock()
            pr.number = i
            pr.title = f"Test PR {i}"
            pr.draft = False
            pr.html_url = f"http://github.com/org/repo/pull/{i}"
            prs.append(pr)

        gh_client.get_pull_requests.return_value = prs
        # Return empty list for diff to avoid processing
        gh_client.get_pr_diff.return_value = []

        # Mock GitLab Client
        gl_client = MagicMock()
        gl_client.has_open_mr.return_value = True
        gl_client.file_exists.return_value = False

        # Initialize PRSync
        pr_sync = PRSync(gl_client, gh_client, db, state_file=os.path.join(temp_dir, "synced_prs.json"))

        print("Starting benchmark...")
        start_time = time.time()

        pr_sync.sync_github_to_gitlab()

        end_time = time.time()
        duration = end_time - start_time

        print(f"Processed {TOTAL_PRS} PRs in {duration:.4f} seconds")
        print(f"Throughput: {TOTAL_PRS / duration:.2f} PRs/sec")

        return duration

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    benchmark()
