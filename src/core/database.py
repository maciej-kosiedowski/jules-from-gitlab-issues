import sqlite3
import os
import threading
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
        # Use persistent connection
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._init_db()

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def _init_db(self):
        with self._lock:
            cursor = self.conn.cursor()
            try:
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
                self.conn.commit()
            except:
                self.conn.rollback()
                raise
            finally:
                cursor.close()

    def add_session(self, session_id: str, task_id: str, task_type: str,
                    github_pr_id: Optional[int] = None,
                    gitlab_mr_id: Optional[int] = None,
                    status: SessionStatus = SessionStatus.ACTIVE):
        with self._lock:
            try:
                cursor = self.conn.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO sessions (session_id, task_id, task_type, github_pr_id, gitlab_mr_id, status) VALUES (?, ?, ?, ?, ?, ?)",
                        (session_id, str(task_id), task_type, github_pr_id, gitlab_mr_id, status.value)
                    )
                    self.conn.commit()
                except:
                    self.conn.rollback()
                    raise
                finally:
                    cursor.close()
            except sqlite3.IntegrityError:
                logger.warning(f"Session {session_id} already exists in database.")

    def update_session_status(self, session_id: str, status: SessionStatus):
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    "UPDATE sessions SET status = ? WHERE session_id = ?",
                    (status.value, session_id)
                )
                self.conn.commit()
            except:
                self.conn.rollback()
                raise
            finally:
                cursor.close()

    def update_session_ids(self, session_id: str, github_pr_id: Optional[int] = None, gitlab_mr_id: Optional[int] = None):
        with self._lock:
            cursor = self.conn.cursor()
            try:
                if github_pr_id is not None:
                    cursor.execute("UPDATE sessions SET github_pr_id = ? WHERE session_id = ?", (github_pr_id, session_id))
                if gitlab_mr_id is not None:
                    cursor.execute("UPDATE sessions SET gitlab_mr_id = ? WHERE session_id = ?", (gitlab_mr_id, session_id))
                self.conn.commit()
            except:
                self.conn.rollback()
                raise
            finally:
                cursor.close()

    def get_active_sessions(self) -> List[Tuple]:
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute("SELECT session_id, task_id, task_type, github_pr_id, gitlab_mr_id FROM sessions WHERE status = ?", (SessionStatus.ACTIVE.value,))
                return cursor.fetchall()
            finally:
                cursor.close()

    def get_session_by_task(self, task_id: str, task_type: str):
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    "SELECT session_id, status FROM sessions WHERE task_id = ? AND task_type = ?",
                    (str(task_id), task_type)
                )
                return cursor.fetchone()
            finally:
                cursor.close()

    # Methods for synced_prs

    def add_synced_pr(self, github_pr_id: int, gitlab_mr_iid: int, gitlab_issue_id: Optional[int] = None):
        with self._lock:
            try:
                cursor = self.conn.cursor()
                try:
                    cursor.execute(
                        "INSERT OR REPLACE INTO synced_prs (github_pr_id, gitlab_mr_iid, gitlab_issue_id) VALUES (?, ?, ?)",
                        (github_pr_id, gitlab_mr_iid, gitlab_issue_id)
                    )
                    self.conn.commit()
                except:
                    self.conn.rollback()
                    raise
                finally:
                    cursor.close()
            except Exception as e:
                logger.error(f"Error adding synced PR to database: {e}")

    def get_synced_pr(self, github_pr_id: int) -> Optional[Tuple]:
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute("SELECT gitlab_mr_iid, gitlab_issue_id FROM synced_prs WHERE github_pr_id = ?", (github_pr_id,))
                return cursor.fetchone()
            finally:
                cursor.close()

    def get_all_synced_prs(self) -> Dict[int, int]:
        """Returns a dict mapping GitHub PR IDs to GitLab MR IIDs."""
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute("SELECT github_pr_id, gitlab_mr_iid FROM synced_prs")
                return {row[0]: row[1] for row in cursor.fetchall()}
            finally:
                cursor.close()

    def delete_synced_pr(self, github_pr_id: int):
        with self._lock:
            cursor = self.conn.cursor()
            try:
                cursor.execute("DELETE FROM synced_prs WHERE github_pr_id = ?", (github_pr_id,))
                self.conn.commit()
            except:
                self.conn.rollback()
                raise
            finally:
                cursor.close()

    def get_gl_issue_id_by_gh_pr(self, github_pr_id: int) -> Optional[int]:
        """Try to find the GitLab issue ID associated with a GitHub PR ID."""
        with self._lock:
            # First check synced_prs table
            cursor = self.conn.cursor()
            try:
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
            finally:
                cursor.close()
