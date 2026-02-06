import sqlite3
import os
from src.utils.logger import logger

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
                    status TEXT NOT NULL
                )
            """)
            conn.commit()

    def add_session(self, session_id: str, task_id: str, task_type: str, status: str = "active"):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (session_id, task_id, task_type, status) VALUES (?, ?, ?, ?)",
                    (session_id, str(task_id), task_type, status)
                )
                conn.commit()
        except sqlite3.IntegrityError:
            logger.warning(f"Session {session_id} already exists in database.")

    def update_session_status(self, session_id: str, status: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET status = ? WHERE session_id = ?",
                (status, session_id)
            )
            conn.commit()

    def get_active_sessions(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id, task_id, task_type FROM sessions WHERE status = 'active'")
            return cursor.fetchall()

    def get_session_by_task(self, task_id: str, task_type: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, status FROM sessions WHERE task_id = ? AND task_type = ?",
                (str(task_id), task_type)
            )
            return cursor.fetchone()
