from src.config import settings
from src.utils.logger import logger
import time
import random
import threading

class JulesClient:
    def __init__(self):
        self.api_key = settings.JULES_API_KEY
        self.active_sessions = 0
        self._lock = threading.Lock()

    def can_start_session(self) -> bool:
        with self._lock:
            return self.active_sessions < settings.JULES_MAX_CONCURRENT_SESSIONS

    def start_session(self, task_description: str, context: str):
        with self._lock:
            if self.active_sessions >= settings.JULES_MAX_CONCURRENT_SESSIONS:
                logger.warning("Max concurrent Jules sessions reached.")
                return None
            self.active_sessions += 1

        logger.info(f"Starting Jules session for task: {task_description[:50]}...")
        session_id = f"sess_{int(time.time())}_{random.randint(100, 999)}"
        return session_id

    def wait_for_completion(self, session_id: str):
        logger.info(f"Waiting for Jules session {session_id} to complete...")
        time.sleep(random.uniform(1, 3))
        logger.info(f"Jules session {session_id} finished successfully.")
        self.complete_session(session_id)
        return True

    def complete_session(self, session_id: str):
        with self._lock:
            if self.active_sessions > 0:
                self.active_sessions -= 1
        logger.info(f"Session {session_id} marked as completed.")
