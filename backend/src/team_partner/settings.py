import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=os.getenv("ENV_FILE", ".env"))

    http_host: str = "127.0.0.1"
    http_port: int = 8888
    debug: bool = False
    database_url: str = "sqlite:///./team_partner.db"
    nua_api_key: str | None = None
    nua_api_uri: str = "https://aws-us-east-2-1.rag.progress.cloud"
    default_chat_model: str = "chatgpt-5.6-sol"
    # Temporary direct Jira REST access, until the Jira MCP integration replaces it.
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None


env_settings = EnvSettings()
