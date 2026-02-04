from src.config import Settings
from src.utils.logger import logger
import logging

def test_settings_load():
    settings = Settings(
        GITLAB_TOKEN="test_token",
        GITLAB_PROJECT_ID="123",
        GITHUB_TOKEN="gh_token",
        GITHUB_REPO="org/repo",
        JULES_API_KEY="jules_key"
    )
    assert settings.GITLAB_TOKEN == "test_token"
    assert settings.GITHUB_REPO == "org/repo"

def test_logger_setup():
    assert logger.name == "ato"
    # settings.LOG_LEVEL is INFO by default in our dummy .env or class
    assert logger.level == logging.INFO
