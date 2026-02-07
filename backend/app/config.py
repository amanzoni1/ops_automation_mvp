from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ops_user:localdev@localhost:5432/ops_automation"
    log_level: str = "INFO"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

    todoist_api_token: str | None = None
    n8n_outbound_webhook_url: str | None = None
    debug_echo_outbound: bool = False
    default_reminder_channel: str | None = None
    default_reminder_user_id: str | None = None
    inbound_default_sender: str | None = None
    inbound_default_receiver: str | None = None
    rag_agent_url: str | None = None

    @property
    def mock_mode(self) -> bool:
        return not self.openai_api_key


settings = Settings()
