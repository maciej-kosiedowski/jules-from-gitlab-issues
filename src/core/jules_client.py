import requests
from src.config import settings
from src.utils.logger import logger
import threading
from typing import Optional, List, Dict

class JulesClient:
    BASE_URL = "https://jules.googleapis.com/v1alpha"

    def __init__(self):
        self.api_key = settings.JULES_API_KEY
        self.headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        self.active_sessions_count = 0
        self._lock = threading.Lock()

    def _get(self, endpoint: str):
        response = requests.get(f"{self.BASE_URL}/{endpoint}", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: Optional[Dict] = None):
        response = requests.post(f"{self.BASE_URL}/{endpoint}", headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def get_source_name(self) -> Optional[str]:
        """Find the source name for the configured GitHub repo."""
        try:
            sources = self._get("sources").get("sources", [])
            owner_repo = settings.GITHUB_REPO.lower()
            for source in sources:
                if source.get("id", "").lower() == f"github/{owner_repo}":
                    return source.get("name")
        except Exception as e:
            logger.error(f"Error fetching sources: {e}")
        return f"sources/github/{settings.GITHUB_REPO}"

    def create_session(self, prompt: str, title: str, branch: str = "main") -> Optional[Dict]:
        source_name = self.get_source_name()
        if not source_name:
            logger.error("Could not determine Jules source name.")
            return None

        data = {
            "prompt": prompt,
            "sourceContext": {
                "source": source_name,
                "githubRepoContext": {
                    "startingBranch": branch
                }
            },
            "automationMode": "AUTO_CREATE_PR",
            "title": title
        }
        try:
            return self._post("sessions", data)
        except Exception as e:
            logger.error(f"Error creating Jules session: {e}")
            return None

    def get_session(self, session_id: str) -> Optional[Dict]:
        try:
            # Use name if it's already full path, else construct it
            name = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
            return self._get(name)
        except Exception as e:
            logger.error(f"Error getting Jules session {session_id}: {e}")
            return None

    def list_activities(self, session_id: str) -> List[Dict]:
        try:
            name = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
            return self._get(f"{name}/activities").get("activities", [])
        except Exception as e:
            logger.error(f"Error listing activities for session {session_id}: {e}")
            return []

    def send_message(self, session_id: str, prompt: str):
        try:
            name = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
            return self._post(f"{name}:sendMessage", {"prompt": prompt})
        except Exception as e:
            logger.error(f"Error sending message to session {session_id}: {e}")
            return None

    def can_start_session(self) -> bool:
        # Note: This is now just a local check.
        # In a real scenario, we might want to check the database for active sessions.
        # But for now, we'll keep the simple counter or rely on the TaskMonitor.
        return True

