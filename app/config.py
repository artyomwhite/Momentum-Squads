from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://momentum:momentum@localhost:5432/momentum"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    operator_username: str = "operator"
    operator_password: str = "change-me"
    session_secret: str = "development-only-change-this-secret"
    helpdesk_allowed_hosts: str = "localhost,127.0.0.1,mock-helpdesk"
    helpdesk_mock_url: str = "http://localhost:8001"
    fallback_delay_seconds: int = 5
    max_llm_requests_per_minute: int = 60
    worker_poll_seconds: float = 1
    worker_concurrency: int = 10
    worker_lease_seconds: int = 120
    worker_max_attempts: int = 5
    @property
    def allowed_helpdesk_hosts(self) -> set[str]:
        return {host.strip().lower() for host in self.helpdesk_allowed_hosts.split(",") if host.strip()}
@lru_cache
def get_settings() -> Settings:
    return Settings()
