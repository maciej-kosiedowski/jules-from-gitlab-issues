import sqlite3
import os
from enum import Enum
from typing import Optional, List, Tuple, Dict
from src.utils.logger import logger

class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"

class Database:
    def __init__(self, db_path: str = "data/ato.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    github_pr_id INTEGER,
                    gitlab_mr_id INTEGER,
                    status TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS synced_prs (
                    github_pr_id INTEGER PRIMARY KEY,
                    gitlab_mr_iid INTEGER NOT NULL,
                    gitlab_issue_id INTEGER
                )
            """)
            conn.commit()

    def add_session(self, session_id: str, task_id: str, task_type: str,
                    github_pr_id: Optional[int] = None,
                    gitlab_mr_id: Optional[int] = None,
                    status: SessionStatus = SessionStatus.ACTIVE):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (session_id, task_id, task_type, github_pr_id, gitlab_mr_id, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, str(task_id), task_type, github_pr_id, gitlab_mr_id, status.value)
                )
                conn.commit()
        except sqlite3.IntegrityError:
            logger.warning(f"Session {session_id} already exists in database.")

    def update_session_status(self, session_id: str, status: SessionStatus):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET status = ? WHERE session_id = ?",
                (status.value, session_id)
            )
            conn.commit()

    def update_session_ids(self, session_id: str, github_pr_id: Optional[int] = None, gitlab_mr_id: Optional[int] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if github_pr_id is not None:
                cursor.execute("UPDATE sessions SET github_pr_id = ? WHERE session_id = ?", (github_pr_id, session_id))
            if gitlab_mr_id is not None:
                cursor.execute("UPDATE sessions SET gitlab_mr_id = ? WHERE session_id = ?", (gitlab_mr_id, session_id))
            conn.commit()

    def get_active_sessions(self) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, task_id, task_type, github_pr_id, gitlab_mr_id FROM sessions WHERE status = ?", (SessionStatus.ACTIVE.value,))
            return cursor.fetchall()

    def get_session_by_task(self, task_id: str, task_type: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, status FROM sessions WHERE task_id = ? AND task_type = ?",
                (str(task_id), task_type)
            )
            return cursor.fetchone()

    # Methods for synced_prs

    def add_synced_pr(self, github_pr_id: int, gitlab_mr_iid: int, gitlab_issue_id: Optional[int] = None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO synced_prs (github_pr_id, gitlab_mr_iid, gitlab_issue_id) VALUES (?, ?, ?)",
                    (github_pr_id, gitlab_mr_iid, gitlab_issue_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error adding synced PR to database: {e}")

    def get_synced_pr(self, github_pr_id: int) -> Optional[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT gitlab_mr_iid, gitlab_issue_id FROM synced_prs WHERE github_pr_id = ?", (github_pr_id,))
            return cursor.fetchone()

    def get_all_synced_prs(self) -> Dict[int, int]:
        """Returns a dict mapping GitHub PR IDs to GitLab MR IIDs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT github_pr_id, gitlab_mr_iid FROM synced_prs")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def delete_synced_pr(self, github_pr_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM synced_prs WHERE github_pr_id = ?", (github_pr_id,))
            conn.commit()

    def get_all_session_issue_ids(self) -> Dict[int, int]:
        """Returns a dict mapping GitHub PR IDs to GitLab Issue IDs from sessions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Select task_id (which is issue_id for gitlab_issue task type)
            cursor.execute(
                "SELECT github_pr_id, task_id FROM sessions WHERE task_type = 'gitlab_issue' AND github_pr_id IS NOT NULL"
            )
            result = {}
            for row in cursor.fetchall():
                try:
                    result[row[0]] = int(row[1])
                except ValueError:
                    continue
            return result

    def get_gl_issue_id_by_gh_pr(self, github_pr_id: int) -> Optional[int]:
        """Try to find the GitLab issue ID associated with a GitHub PR ID."""
        # First check synced_prs table
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT gitlab_issue_id FROM synced_prs WHERE github_pr_id = ?", (github_pr_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]

            # Then check sessions table
            cursor.execute("SELECT task_id FROM sessions WHERE github_pr_id = ? AND task_type = 'gitlab_issue'", (github_pr_id,))
            row = cursor.fetchone()
            if row:
                try:
                    return int(row[0])
                except ValueError:
                    return None
        return None
