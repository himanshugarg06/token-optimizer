"""Application settings using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Core Authentication
    middleware_api_key: str = "dev-key-12345"

    # LLM Provider API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Dashboard Integration
    dashboard_base_url: Optional[str] = None
    dashboard_api_key: Optional[str] = None
    dashboard_enabled: bool = False
    mock_dashboard: bool = True

    # Infrastructure
    redis_url: str = "redis://localhost:6379"
    postgres_url: Optional[str] = None

    # Feature Flags
    enable_semantic_retrieval: bool = False
    enable_toon_compression: bool = False

    # Optimization Parameters
    max_input_tokens: int = 8000
    keep_last_n_turns: int = 4
    safety_margin_tokens: int = 300

    # Observability
    log_level: str = "INFO"

    def get_dashboard_api_key(self) -> str:
        """Get dashboard API key, fallback to middleware key."""
        return self.dashboard_api_key or self.middleware_api_key


# Global settings instance
settings = Settings()
