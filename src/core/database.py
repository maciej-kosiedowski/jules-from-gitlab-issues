import sqlite3
import os
from enum import Enum
from typing import Optional, List, Tuple
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
