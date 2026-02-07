import time
import sqlite3
import os
import shutil
from src.core.database import Database
from src.core.github_client import GitHubClient
from src.core.gitlab_client import GitLabClient
from src.core.jules_client import JulesClient
from src.logic.task_monitor import TaskMonitor
from unittest.mock import MagicMock

# Setup
DB_PATH = "data/benchmark.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

db = Database(DB_PATH)

# Insert dummy data
NUM_EXISTING_SESSIONS = 500
NUM_PRS = 1000

print(f"Setting up DB with {NUM_EXISTING_SESSIONS} existing sessions...")
for i in range(NUM_EXISTING_SESSIONS):
    db.add_session(f"session_{i}", str(i), "github_pr")

# Mock Clients
gh_client = MagicMock(spec=GitHubClient)
gl_client = MagicMock(spec=GitLabClient)
jules_client = MagicMock(spec=JulesClient)

# Mock PRs
class MockPR:
    def __init__(self, number):
        self.number = number
        self.head = MagicMock()
        self.head.sha = "sha"
        self.head.ref = "ref"
        self.title = f"PR {number}"

prs = [MockPR(i) for i in range(NUM_PRS)]
gh_client.get_pull_requests.return_value = prs
gh_client.get_pr_status.return_value = "success" # To avoid further processing
jules_client.get_active_sessions_count_from_api.return_value = 0

monitor = TaskMonitor(gl_client, gh_client, jules_client, db)

# Measure N+1
print("Benchmarking N+1 approach...")
start_time = time.time()

# Extracting the logic from TaskMonitor to isolate the loop behavior we want to test
# We are simulating the part of check_and_delegate_tasks dealing with GitHub PRs
active_count = 0
for pr in prs:
    # Check if session exists (The N+1 bottleneck)
    if not db.get_session_by_task(pr.number, "github_pr"):
        # Simulate the rest of the logic simply
        pass

end_time = time.time()
n_plus_1_duration = end_time - start_time
print(f"N+1 duration: {n_plus_1_duration:.4f} seconds")

# Measure Batch
print("Benchmarking Batch approach...")
start_time = time.time()

pr_ids = [str(pr.number) for pr in prs]
existing_prs = db.get_existing_tasks(pr_ids, "github_pr")

for pr in prs:
    if str(pr.number) not in existing_prs:
        pass

end_time = time.time()
batch_duration = end_time - start_time
print(f"Batch duration: {batch_duration:.4f} seconds")

improvement = n_plus_1_duration / batch_duration if batch_duration > 0 else 0
print(f"Speedup: {improvement:.2f}x")

# Clean up
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
