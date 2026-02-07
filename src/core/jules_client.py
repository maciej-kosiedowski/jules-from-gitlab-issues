import requests
from src.config import settings
from src.utils.logger import logger
import threading
from typing import Optional, List, Dict
import json

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

    def _get(self, endpoint: str, params: Optional[Dict] = None):
        response = requests.get(f"{self.BASE_URL}/{endpoint}", headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: Optional[Dict] = None):
        response = requests.post(f"{self.BASE_URL}/{endpoint}", headers=self.headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()

    def _log_error(self, message_prefix: str, error: Exception):
        """Log errors safely without exposing sensitive information."""
        if isinstance(error, requests.exceptions.HTTPError):
            status = error.response.status_code if error.response else "Unknown"
            logger.error(f"{message_prefix}: HTTP {status}")
        elif isinstance(error, requests.exceptions.RequestException):
            logger.error(f"{message_prefix}: {type(error).__name__}")
        else:
            logger.error(f"{message_prefix}: Unexpected {type(error).__name__}")

    def get_source_name(self) -> Optional[str]:
        """Find the source name for the configured GitHub repo."""
        try:
            sources = self._get("sources").get("sources", [])
            owner_repo = settings.GITHUB_REPO.lower()
            for source in sources:
                if source.get("id", "").lower() == f"github/{owner_repo}":
                    return source.get("name")
        except Exception as e:
            self._log_error("Error fetching sources", e)
        return f"sources/github/{settings.GITHUB_REPO}"

    def create_session(self, prompt: str, title: str, branch: str = "main", attachments: Optional[List[Dict]] = None) -> Optional[Dict]:
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
        if attachments:
            data["attachments"] = attachments
        try:
            return self._post("sessions", data)
        except Exception as e:
            self._log_error("Error creating Jules session", e)
            return None

    def get_session(self, session_id: str) -> Optional[Dict]:
        try:
            name = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
            return self._get(name)
        except Exception as e:
            self._log_error(f"Error getting Jules session {session_id}", e)
            return None

    def list_sessions(self, page_size: int = 100, page_token: Optional[str] = None) -> Dict:
        """List sessions with pagination."""
        params = {"pageSize": page_size}
        if page_token:
            params["pageToken"] = page_token
        try:
            return self._get("sessions", params=params)
        except Exception as e:
            self._log_error("Error listing Jules sessions", e)
            return {}

    def get_active_sessions_count_from_api(self) -> int:
        """
        Count active sessions on Jules by iterating through all sessions.
        Note: The API doesn't seem to have a filter for 'active',
        so we might need to check if they have outputs/PRs or use our local DB.
        But the user specifically asked to track active sessions via list_sessions.
        """
        count = 0
        page_token = None
        while True:
            data = self.list_sessions(page_size=100, page_token=page_token)
            sessions = data.get("sessions", [])
            for s in sessions:
                if s.get("state", False) == 'IN_PROGRESS':
                    count += 1

            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return count

    def list_activities(self, session_id: str) -> List[Dict]:
        try:
            name = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
            return self._get(f"{name}/activities").get("activities", [])
        except Exception as e:
            self._log_error(f"Error listing activities for session {session_id}", e)
            return []

    def send_message(self, session_id: str, prompt: str):
        try:
            name = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
            return self._post(f"{name}:sendMessage", {"prompt": prompt})
        except Exception as e:
            self._log_error(f"Error sending message to session {session_id}", e)
            return None

    def can_start_session(self) -> bool:
        # We'll use the API count if possible
        try:
            active_count = self.get_active_sessions_count_from_api()
            return active_count < settings.JULES_MAX_CONCURRENT_SESSIONS
        except Exception:
            return True
