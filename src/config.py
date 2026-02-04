from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # GitLab Config
    GITLAB_URL: str = "https://gitlab.com"
    GITLAB_TOKEN: str
    GITLAB_PROJECT_ID: str

    # GitHub Config
    GITHUB_TOKEN: str
    GITHUB_REPO: str

    # Jules AI Config
    JULES_API_KEY: str
    JULES_MAX_CONCURRENT_SESSIONS: int = 3

    # App Config
    LOG_LEVEL: str = "INFO"
    POLLING_INTERVAL: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()  # type: ignore
